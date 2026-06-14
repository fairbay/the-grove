"""
grove.py — Claude-side client for grove-api v1 (Step 4).

Seven operations exposed:
    grove.create(entity_type, title, ...)        → POST   /api/{tasks,ideas}
    grove.list_items(entity_type, q=None, ...)   → GET    /api/{tasks,ideas}
    grove.get(entity_type, id)                   → GET    /api/{tasks,ideas}/:id
    grove.update(entity_type, id, **patch)       → PATCH  /api/{tasks,ideas}/:id
    grove.complete(id, source=...)               → POST   /api/tasks/:id/complete
    grove.drop(id, source=...)                   → POST   /api/tasks/:id/drop
    grove.events(entity_type=None, ...)          → GET    /api/events

`complete` and `drop` are task-only ergonomic sugar over PATCH — same
underlying write path (RPC wraps mutation + event insert atomically, FR-005
strict). Event kind is `task.completed` / `task.dropped` so the audit log
carries the semantic intent rather than a generic `task.updated`.

Auth: opaque Bearer token seeded into public.token. Token resolution:
1. $GROVE_TOKEN env var (set from Claude memory edit in chat)
2. ops/secrets/grove.env (for Routines / Claude Code)
3. SECRET.txt next to this script (legacy fallback)
The API hashes the value and looks it up;
owner_id is resolved server-side.

Transient edge 503s ("DNS cache overflow" body) are retried with exponential
backoff; observed on *.supabase.co and occasionally *.vercel.app from
Claude's container egress.
"""

from __future__ import annotations
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Iterable

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------

VALID_SOURCES = {
    "claude-windows", "claude-web", "claude-ios",
    "web", "ios-app", "ios-widget",
    "siri-shortcut", "migration",
    "skill-worker-r", "grove-prune-r",  # routine surfaces (grove migration 0008)
}
VALID_TASK_STATUSES = {"open", "done", "dropped"}
VALID_IDEA_STATUSES = {
    "raw", "scouted", "in_dev", "shipped", "shelved", "gifted", "killed",
}
VALID_IDEA_VERDICTS = {
    "greenlight", "overreach", "public_good", "mirage",
    "workhorse", "fools_gold", "lark", "pass",
}
VALID_ENTITIES = {"task", "idea"}

# Default source tag for calls made from Claude.ai web chat. Override per-call.
DEFAULT_SOURCE = "claude-web"

# Exposed for callers that want to know where requests go.
DEFAULT_BASE_URL = "https://grove-woad-phi.vercel.app"


# ----------------------------------------------------------------------------
# Config resolution (token + base URL) — unchanged from v0
# ----------------------------------------------------------------------------

def _load_config() -> tuple[str, str]:
    env_token = os.environ.get("GROVE_TOKEN")
    env_base = os.environ.get("GROVE_BASE_URL")
    if env_token:
        return env_token.strip(), (env_base or DEFAULT_BASE_URL).strip()

    # Routine/Claude Code fallback: check cloned ops repo
    for candidate in [
        Path.home() / "ops" / "secrets" / "grove.env",
        Path("/home/user/ops/secrets/grove.env"),
    ]:
        if candidate.is_file():
            token, base_url = _parse_env_file(candidate)
            if token:
                return token, base_url or DEFAULT_BASE_URL

    # Legacy fallback: SECRET.txt next to this script
    secret_path = os.environ.get("GROVE_SECRET_PATH")
    if not secret_path:
        here = Path(__file__).resolve().parent
        secret_path = str(here.parent / "SECRET.txt")

    if os.path.exists(secret_path):
        token, base_url = _parse_env_file(Path(secret_path))
        if token:
            return token, base_url or DEFAULT_BASE_URL

    raise RuntimeError(
        "Grove token not found. In chat: set GROVE_TOKEN env var from memory. "
        "In Routines: ensure secrets/grove.env exists in ops repo."
    )


def _parse_env_file(path: Path) -> tuple[str | None, str | None]:
    """Parse a key=value env file, returning (token, base_url)."""
    token = None
    base_url = None
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    kl = k.lower()
                    if kl in ("token", "grove_token"):
                        token = v
                    elif kl in ("base_url", "base", "url", "grove_base_url"):
                        base_url = v
                else:
                    token = line
    except FileNotFoundError:
        pass
    return token, base_url

    if not token:
        raise RuntimeError(f"Grove token not found in {secret_path}")
    return token, base_url


# ----------------------------------------------------------------------------
# HTTP core — transient-503 retry
# ----------------------------------------------------------------------------

class GroveError(Exception):
    """Raised when grove-api returns a non-success status."""

    def __init__(self, status: int, payload: Any):
        self.status = status
        self.payload = payload
        message = payload.get("message") if isinstance(payload, dict) else str(payload)
        super().__init__(f"grove-api HTTP {status}: {message}")


def _request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    query: dict | None = None,
    max_retries: int = 4,
) -> Any:
    token, base_url = _load_config()

    url = base_url.rstrip("/") + path
    if query:
        from urllib.parse import urlencode
        pairs = {k: v for k, v in query.items() if v is not None}
        if pairs:
            url = f"{url}?{urlencode(pairs)}"

    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read()
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            raw = e.read()
            if e.code == 503 and b"DNS cache overflow" in raw:
                last_err = e
                time.sleep(2 ** attempt)
                continue
            try:
                payload = json.loads(raw) if raw else {"message": e.reason}
            except json.JSONDecodeError:
                payload = {"message": raw.decode(errors="replace")[:500]}
            raise GroveError(e.code, payload) from None
        except urllib.error.URLError as e:
            last_err = e
            time.sleep(2 ** attempt)

    raise RuntimeError(f"grove-api unreachable after {max_retries} attempts: {last_err}")


# ----------------------------------------------------------------------------
# Validation helpers
# ----------------------------------------------------------------------------

def _check_entity(entity_type: str) -> None:
    if entity_type not in VALID_ENTITIES:
        raise ValueError(
            f"Unknown entity_type {entity_type!r}. Expected 'task' or 'idea'."
        )


def _route(entity_type: str) -> str:
    """'task' → '/api/tasks', 'idea' → '/api/ideas'."""
    return f"/api/{entity_type}s"


# ----------------------------------------------------------------------------
# create
# ----------------------------------------------------------------------------

def create(
    entity_type: str,
    title: str,
    *,
    # Shared
    notes: str | None = None,
    tags: Iterable[str] | None = None,
    metadata: dict | None = None,
    source: str = DEFAULT_SOURCE,
    # Task-only
    list: str = "inbox",             # noqa: A002 — matches API field name
    status: str | None = None,
    due_at: str | None = None,
    project_ref: str | None = None,
    priority: int | None = None,
    # Idea-only
    scores: dict | None = None,
    verdict: str | None = None,
) -> dict:
    """
    Create a task or idea. Returns the created row (unwrapped from the
    API's `{task: {...}}` or `{idea: {...}}` envelope).

    Task example:
        grove.create("task", "Ship Step 4", list="grove", priority=2)

    Idea example:
        grove.create("idea", "Tactile hex game board", status="raw",
                     tags=["toy","research"])
    """
    _check_entity(entity_type)
    if source not in VALID_SOURCES:
        raise ValueError(f"source must be one of {sorted(VALID_SOURCES)}")
    if not (1 <= len(title) <= 500):
        raise ValueError("title must be 1–500 chars")

    body: dict[str, Any] = {
        "title": title,
        "tags": sorted(set(tags)) if tags else [],
        "metadata": metadata or {},
        "source": source,
    }

    if entity_type == "task":
        if status is None:
            status = "open"
        if status not in VALID_TASK_STATUSES:
            raise ValueError(f"task status must be one of {sorted(VALID_TASK_STATUSES)}")
        body["list"] = list
        body["status"] = status
        body["priority"] = priority if priority is not None else 0
        if notes is not None:
            body["notes"] = notes
        if due_at is not None:
            body["due_at"] = due_at
        if project_ref is not None:
            body["project_ref"] = project_ref
    else:  # idea
        if status is None:
            status = "raw"
        if status not in VALID_IDEA_STATUSES:
            raise ValueError(f"idea status must be one of {sorted(VALID_IDEA_STATUSES)}")
        if verdict is not None and verdict not in VALID_IDEA_VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(VALID_IDEA_VERDICTS)}")
        body["status"] = status
        body["scores"] = scores or {}
        body["notes"] = notes if notes is not None else ""
        if verdict is not None:
            body["verdict"] = verdict

    result = _request("POST", _route(entity_type), body=body)
    return result[entity_type]  # unwrap envelope


# ----------------------------------------------------------------------------
# list_items — renamed to dodge the built-in `list` shadowing
# ----------------------------------------------------------------------------

def list_items(
    entity_type: str,
    *,
    q: str | None = None,
    status: str | None = None,
    list: str | None = None,      # noqa: A002 — task filter
    verdict: str | None = None,   # idea filter
    tag: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """
    List this owner's tasks or ideas, newest first. All filters optional.

    Task filters:   q, status, list, tag, limit
    Idea filters:   q, status, verdict, tag, limit

    `q` runs full-text search over title + notes (Postgres FTS, English).
    """
    _check_entity(entity_type)
    if not (1 <= limit <= 200):
        raise ValueError("limit must be 1–200")

    query: dict[str, Any] = {"limit": limit}
    if q is not None:
        query["q"] = q
    if tag is not None:
        query["tag"] = tag

    if entity_type == "task":
        if status is not None and status not in VALID_TASK_STATUSES:
            raise ValueError(f"task status must be one of {sorted(VALID_TASK_STATUSES)}")
        if verdict is not None:
            raise ValueError("verdict filter is idea-only")
        if status is not None:
            query["status"] = status
        if list is not None:
            query["list"] = list
        envelope_key = "tasks"
    else:  # idea
        if status is not None and status not in VALID_IDEA_STATUSES:
            raise ValueError(f"idea status must be one of {sorted(VALID_IDEA_STATUSES)}")
        if verdict is not None and verdict not in VALID_IDEA_VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(VALID_IDEA_VERDICTS)}")
        if list is not None:
            raise ValueError("list filter is task-only")
        if status is not None:
            query["status"] = status
        if verdict is not None:
            query["verdict"] = verdict
        envelope_key = "ideas"

    result = _request("GET", _route(entity_type), query=query)
    return result[envelope_key]


# ----------------------------------------------------------------------------
# get
# ----------------------------------------------------------------------------

def get(entity_type: str, id: str) -> dict:
    """Fetch one task or idea by UUID. Raises GroveError(404) if not found."""
    _check_entity(entity_type)
    if not id:
        raise ValueError("id is required")
    result = _request("GET", f"{_route(entity_type)}/{id}")
    return result[entity_type]


# ----------------------------------------------------------------------------
# update — generic patch
# ----------------------------------------------------------------------------

def update(
    entity_type: str,
    id: str,
    *,
    source: str = DEFAULT_SOURCE,
    **patch: Any,
) -> dict:
    """
    Partial update via PATCH. Only fields present in `patch` are touched;
    passing `field=None` clears nullable columns (notes, due_at, etc.).

    Task:   grove.update("task", task_id, priority=3, tags=["dev","urgent"])
    Idea:   grove.update("idea", idea_id, status="scouted", verdict="greenlight")

    `source` defaults to 'claude-web' and is always stamped on the emitted
    event row.
    """
    _check_entity(entity_type)
    if source not in VALID_SOURCES:
        raise ValueError(f"source must be one of {sorted(VALID_SOURCES)}")
    if not id:
        raise ValueError("id is required")
    if not patch:
        raise ValueError("patch must include at least one field")

    # Validate enum-typed fields the caller might pass
    if "status" in patch and patch["status"] is not None:
        valid = VALID_TASK_STATUSES if entity_type == "task" else VALID_IDEA_STATUSES
        if patch["status"] not in valid:
            raise ValueError(f"status must be one of {sorted(valid)}")
    if entity_type == "idea" and "verdict" in patch and patch["verdict"] is not None:
        if patch["verdict"] not in VALID_IDEA_VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(VALID_IDEA_VERDICTS)}")

    body = dict(patch)
    body["source"] = source
    result = _request("PATCH", f"{_route(entity_type)}/{id}", body=body)
    return result[entity_type]


# ----------------------------------------------------------------------------
# complete / drop — task-only shortcuts
# ----------------------------------------------------------------------------

def complete(id: str, *, source: str = DEFAULT_SOURCE) -> dict:
    """Mark a task done. Sets status=done + completed_at=now().
    Event kind is `task.completed`."""
    if not id:
        raise ValueError("id is required")
    if source not in VALID_SOURCES:
        raise ValueError(f"source must be one of {sorted(VALID_SOURCES)}")
    result = _request(
        "POST",
        f"/api/tasks/{id}/complete",
        body={"source": source},
    )
    return result["task"]


def drop(id: str, *, source: str = DEFAULT_SOURCE) -> dict:
    """Drop a task (abandon, not complete). Sets status=dropped.
    Event kind is `task.dropped`."""
    if not id:
        raise ValueError("id is required")
    if source not in VALID_SOURCES:
        raise ValueError(f"source must be one of {sorted(VALID_SOURCES)}")
    result = _request(
        "POST",
        f"/api/tasks/{id}/drop",
        body={"source": source},
    )
    return result["task"]


# ----------------------------------------------------------------------------
# events — audit log read
# ----------------------------------------------------------------------------

def events(
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    kind: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """
    Read the owner-scoped audit log, newest first. All filters optional.

    Useful to answer "what happened to this idea recently?"
    (pass entity_type='idea', entity_id=...) or to show recent activity
    across the vault.
    """
    if entity_type is not None and entity_type not in VALID_ENTITIES:
        raise ValueError(f"entity_type must be one of {sorted(VALID_ENTITIES)}")
    if not (1 <= limit <= 200):
        raise ValueError("limit must be 1–200")

    query: dict[str, Any] = {"limit": limit}
    if entity_type is not None:
        query["entity_type"] = entity_type
    if entity_id is not None:
        query["entity_id"] = entity_id
    if kind is not None:
        query["kind"] = kind

    result = _request("GET", "/api/events", query=query)
    return result["events"]


# ----------------------------------------------------------------------------
# CLI — python -m grove <op> ...
# ----------------------------------------------------------------------------

def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="grove", description="Grove v1 client")
    sub = parser.add_subparsers(dest="op", required=True)

    p_create = sub.add_parser("create", help="Create a task or idea")
    p_create.add_argument("entity_type", choices=["task", "idea"])
    p_create.add_argument("title")
    p_create.add_argument("--notes")
    p_create.add_argument("--list", default="inbox")
    p_create.add_argument("--priority", type=int, default=0)
    p_create.add_argument("--tag", action="append", dest="tags")
    p_create.add_argument("--source", default=DEFAULT_SOURCE)
    p_create.add_argument("--status")
    p_create.add_argument("--verdict")

    p_list = sub.add_parser("list", help="List tasks or ideas")
    p_list.add_argument("entity_type", choices=["task", "idea"])
    p_list.add_argument("--q")
    p_list.add_argument("--status")
    p_list.add_argument("--list", dest="list_name")
    p_list.add_argument("--verdict")
    p_list.add_argument("--tag")
    p_list.add_argument("--limit", type=int, default=50)

    p_get = sub.add_parser("get", help="Get one entity by id")
    p_get.add_argument("entity_type", choices=["task", "idea"])
    p_get.add_argument("id")

    p_complete = sub.add_parser("complete", help="Mark a task done")
    p_complete.add_argument("id")
    p_complete.add_argument("--source", default=DEFAULT_SOURCE)

    p_drop = sub.add_parser("drop", help="Drop a task")
    p_drop.add_argument("id")
    p_drop.add_argument("--source", default=DEFAULT_SOURCE)

    p_events = sub.add_parser("events", help="Read audit log")
    p_events.add_argument("--entity-type", choices=["task", "idea"])
    p_events.add_argument("--entity-id")
    p_events.add_argument("--kind")
    p_events.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()
    if args.op == "create":
        row = create(
            args.entity_type, args.title,
            notes=args.notes, list=args.list,
            priority=args.priority, tags=args.tags,
            source=args.source, status=args.status,
            verdict=args.verdict,
        )
        print(json.dumps(row, indent=2))
    elif args.op == "list":
        rows = list_items(
            args.entity_type,
            q=args.q, status=args.status,
            list=args.list_name, verdict=args.verdict,
            tag=args.tag, limit=args.limit,
        )
        print(f"{len(rows)} {args.entity_type}(s)")
        for r in rows:
            if args.entity_type == "task":
                flag = "✓" if r["status"] == "done" else ("…" if r["status"] == "dropped" else " ")
                print(f"  [{flag}] {r['list']:12s} {r['title']}  ({r['id'][:8]})")
            else:
                v = r.get("verdict") or "—"
                print(f"  [{r['status']:8s}] {v:12s} {r['title']}  ({r['id'][:8]})")
    elif args.op == "get":
        print(json.dumps(get(args.entity_type, args.id), indent=2))
    elif args.op == "complete":
        print(json.dumps(complete(args.id, source=args.source), indent=2))
    elif args.op == "drop":
        print(json.dumps(drop(args.id, source=args.source), indent=2))
    elif args.op == "events":
        rows = events(
            entity_type=args.entity_type,
            entity_id=args.entity_id,
            kind=args.kind,
            limit=args.limit,
        )
        print(f"{len(rows)} event(s)")
        for r in rows:
            print(f"  {r['created_at'][:19]}  {r['kind']:18s} {r['entity_type']}:{r['entity_id'][:8]} ({r['source']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
