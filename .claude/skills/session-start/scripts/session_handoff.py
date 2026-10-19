"""
session_handoff.py — cross-surface session-continuity helper.

Synced into every repo with the session-start skill. The SessionStart hook entry
that runs it is managed by fairbay/ops (docs/hook-delivery/DESIGN.md).

Commands:

    inject   The ENTRY gate (SessionStart hook). Emits one JSON payload
             (hookSpecificOutput.additionalContext), shaped by the hook input's
             `source`:
               startup / clear / fork / none: header, notes, the open-PR gate table
                 (pr_state.py report --table, at most 15 rows), and HANDOFF.yaml's
                 meta, next and carried_forward;
               compact / resume: notes and next + carried_forward, no network.
             The whole payload stays under Claude Code's 10,000-character cap,
             measured on the serialized JSON. It never blocks: a failure becomes
             a note line ("PR gate unavailable", "Entry gate error", ...) and the
             command exits 0. It also makes sure the capture queue is git-ignored
             (chat-archive's capture_corrections.ensure_excluded).

    write    EXIT-gate helper. Reads a handoff body as JSON on stdin, stamps
             meta.surface / meta.generated / meta.project, carries unfinished
             `next:` items forward, and writes <repo>/HANDOFF.yaml. Session state
             lives in Grove; there is no session-handoff path any more.

Stdlib only, except that `write` uses PyYAML when present (JSON otherwise, which
is valid YAML).
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_CONTEXT_CHARS = 10000  # Claude Code's additionalContext cap (hooks reference)
RESERVE = 300              # room for the closing line and JSON overhead drift
GIT_TIMEOUT = 5
PR_STATE_TIMEOUT = 20
PR_TABLE_ROWS = 15
PR_STATE = Path(".claude/skills/session-start/scripts/pr_state.py")
CAPTURE = Path(".claude/skills/chat-archive/scripts/capture_corrections.py")
FULL_SOURCES = (None, "startup", "clear", "fork")
INJECTED_KEYS = ("meta", "next", "carried_forward")
SECTION_START = re.compile(r"^([a-z_]+):")


def _run(cmd: list[str], cwd: str | None = None, timeout: int = GIT_TIMEOUT) -> str:
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip()
    except Exception:
        return ""


def _repo_root(cwd: str | None = None) -> Path:
    """$CLAUDE_PROJECT_DIR, else the git top level of cwd, else cwd."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    cwd = cwd or os.getcwd()
    top = _run(["git", "-C", cwd, "rev-parse", "--show-toplevel"])
    return Path(top) if top else Path(cwd)


def _repo_slug(root: Path) -> str:
    url = _run(["git", "config", "--get", "remote.origin.url"], cwd=str(root))
    if url:
        u = url.rstrip("/")
        if u.endswith(".git"):
            u = u[:-4]
        parts = u.replace(":", "/").split("/")
        if parts and parts[-1]:
            return parts[-1]
    return root.name


def _read_handoff(root: Path):
    for name in ("HANDOFF.yaml", "HANDOFF.yml", "HANDOFF.md"):
        p = root / name
        if p.is_file():
            return name, p.read_text(encoding="utf-8", errors="replace")
    return None


def _pr_gate_table(root: Path, slug: str):
    """(table or None, note or None). The table is capped at PR_TABLE_ROWS rows."""
    script = root / PR_STATE
    if not script.is_file():
        return None, f"PR gate unavailable: {PR_STATE} missing"
    try:
        out = subprocess.run(
            [sys.executable, str(script), "report", "--repo", f"fairbay/{slug}", "--table"],
            cwd=str(root), capture_output=True, text=True, timeout=PR_STATE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return None, f"PR gate unavailable: pr_state.py took over {PR_STATE_TIMEOUT} s"
    except Exception as e:
        return None, f"PR gate unavailable: {type(e).__name__}"
    table = out.stdout.strip()
    if out.returncode != 0 or not table:
        return None, f"PR gate unavailable: pr_state.py exit {out.returncode}"
    return _cap_table(table), None


def _cap_table(table: str) -> str:
    """At most PR_TABLE_ROWS PR rows, then a line saying how many were left out."""
    lines = table.splitlines()
    rows = [i for i, l in enumerate(lines) if re.match(r"^\| \d", l)]
    if len(rows) > PR_TABLE_ROWS:
        keep = rows[PR_TABLE_ROWS - 1] + 1
        lines = lines[:keep] + [f"… {len(rows) - PR_TABLE_ROWS} more open PRs: run pr_state.py report"]
    return "\n".join(lines)


def _capture_note(root: Path):
    """None when the capture gate can work here; otherwise one note line.
    Runs the capture script's own exclude steps (idempotent), so a fresh clone
    gets its exclude line now rather than reporting a false failure."""
    path = root / CAPTURE
    if not path.is_file():
        return f"Capture gate inactive: {CAPTURE} missing"
    try:
        spec = importlib.util.spec_from_file_location("capture_corrections", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ok, reason = mod.ensure_excluded(str(root))
    except Exception as e:
        return f"Capture gate inactive: {type(e).__name__} loading it"
    return None if ok else f"Capture queue could not be excluded: {reason}"


def _sections(text: str) -> dict:
    """Top-level sections of a YAML handoff, by column-0 `key:` lines. Comments,
    the `# Handoff:` title and column-0 `- ` items stay with the current section."""
    out, current = {}, None
    for line in text.splitlines():
        m = SECTION_START.match(line)
        if m:
            current = m.group(1)
            out[current] = [line]
        elif current:
            out[current].append(line)
    return {k: "\n".join(v).rstrip() for k, v in out.items()}


def _handoff_sections(name: str, text: str) -> dict | None:
    """{key: text} for the injected keys, or None when the file gives no `next`
    (then the caller falls back to head truncation)."""
    if name.endswith(".md"):
        return None
    secs = _sections(text)
    if "next" in secs:
        return {k: secs[k] for k in INJECTED_KEYS if k in secs}
    obj = _parse_existing_text(text)  # JSON form, as cmd_write emits without PyYAML
    if isinstance(obj, dict) and "next" in obj:
        return {k: json.dumps({k: obj[k]}, indent=2, ensure_ascii=False) for k in INJECTED_KEYS if k in obj}
    return None


def _size(context: str) -> int:
    return len(json.dumps(context, ensure_ascii=False))


def _fit(parts: list[str], extra: str, limit: int) -> tuple[str, bool]:
    """Append `extra` to the joined parts if it fits; otherwise cut it at the last
    list-item boundary that fits. Returns (text added, whether it was cut)."""
    base = "\n\n".join(parts)
    if _size(base + "\n\n" + extra) <= limit:
        return extra, False
    lines = extra.splitlines()
    for end in range(len(lines) - 1, 0, -1):
        if not re.match(r"^\s*- ", lines[end]):
            continue
        candidate = "\n".join(lines[:end]) + "\n  (cut; read HANDOFF.yaml)"
        if _size(base + "\n\n" + candidate) <= limit:
            return candidate, True
    return "", True


def _compose(slug: str, source, notes: list[str], table, handoff) -> str:
    limit = MAX_CONTEXT_CHARS - RESERVE
    full = source in FULL_SOURCES
    if full:
        head = (
            f"Open handoff for repo '{slug}'. Review it before designing, building, or "
            f"editing files, and acknowledge the `next:` items first (read-back) before "
            f"starting work.\n`carried_forward:` items are unfinished work from earlier "
            f"sessions that no session has done or explicitly dropped. Treat them as part "
            f"of `next:`: they are queued work, not history. If you are not going to do "
            f"one, say so and record it under `dropped:` in your exit handoff."
        )
    else:
        head = f"Still queued in '{slug}' (session {source}; no read-back needed, carry on):"
    parts = [head] + [f"Note: {n}" for n in notes]
    if full and table:
        parts.append(table)
    omitted = []
    if handoff:
        name, text = handoff
        secs = _handoff_sections(name, text)
        if secs is None:  # no `next` to find: head truncation, as before the redesign
            block = f"### {name}\n{text}"
            while block and _size("\n\n".join(parts + [block])) > limit:
                block = block[: int(len(block) * 0.9)]
            if block != f"### {name}\n{text}":
                block += "\n[truncated: read the file]"
            parts.append(block)
        else:
            keys = INJECTED_KEYS if full else ("next", "carried_forward")
            for k in keys:
                if k not in secs:
                    continue
                added, cut = _fit(parts, secs[k], limit)
                if added:
                    parts.append(added)
                else:
                    omitted.append(k)
            if full:
                parts.append(f"Other sections (done, decisions_made, context, …): read {name}.")
    elif full:
        parts.append("No HANDOFF.yaml in this repo.")
    if omitted:
        parts.append(f"Omitted for space: {', '.join(omitted)}; read the handoff file.")
    return "\n\n".join(parts)


def _emit(context: str) -> None:
    payload = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    # UTF-8 bytes: a non-UTF-8 stdout must not crash the gate.
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.flush()


def _hook_input() -> dict:
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
        obj = json.loads(raw) if raw.strip() else {}
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def cmd_inject() -> int:
    """Prints exactly one JSON payload, as its last act, and returns 0."""
    try:
        hook = _hook_input()
        source = hook.get("source")
        root = _repo_root(hook.get("cwd"))
        slug = _repo_slug(root)
        notes = []
        capture = _capture_note(root)
        if capture:
            notes.append(capture)
        table = None
        if source in FULL_SOURCES:
            table, note = _pr_gate_table(root, slug)
            if note:
                notes.append(note)
        context = _compose(slug, source, notes, table, _read_handoff(root))
    except Exception as e:
        context = f"Note: Entry gate error: {type(e).__name__}. Run the session-start skill."
    _emit(context)
    return 0


def _to_yaml(obj) -> str:
    try:
        import yaml  # type: ignore

        return yaml.safe_dump(
            obj, sort_keys=False, default_flow_style=False, allow_unicode=True
        )
    except Exception:
        # JSON is valid YAML — safe fallback when PyYAML is unavailable.
        return json.dumps(obj, indent=2, ensure_ascii=False)


def _parse_existing_text(text: str):
    """Parse handoff text (YAML or JSON) after stripping the '# Handoff:' title
    line cmd_write emits. Returns a dict or None; never raises."""
    payload = "\n".join(l for l in text.splitlines() if not l.startswith("# Handoff:"))
    try:
        import yaml  # type: ignore

        obj = yaml.safe_load(payload)
    except Exception:
        try:
            obj = json.loads(payload)
        except Exception:
            return None
    return obj if isinstance(obj, dict) else None


def _parse_existing(dest: Path):
    """Read the handoff we're about to overwrite. Returns a dict or None.
    Never raises — a malformed prior handoff must not block the exit gate."""
    if not dest.is_file():
        return None
    try:
        return _parse_existing_text(dest.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _norm(item) -> str:
    """Stable identity for a next-item so carry-forward can dedupe."""
    if isinstance(item, dict):
        s = item.get("item") or item.get("task") or json.dumps(item, sort_keys=True)
    else:
        s = str(item)
    return " ".join(s.split()).lower()


def _carry_forward(body: dict, dest: Path) -> dict:
    """Preserve unfinished work from the handoff being replaced.

    The exit gate previously did a blind overwrite: whatever the prior session
    queued in `next:` was destroyed even if nothing had been done about it.
    Any prior `next:` item the incoming handoff neither repeats nor explicitly
    resolves is carried into `carried_forward:` so it survives the write.

    A session resolves an item by listing it (verbatim or near-verbatim) in
    `done:` or `dropped:`. Otherwise it persists.
    """
    prior = _parse_existing(dest)
    if not prior:
        return body

    # Prior `next:` AND prior `carried_forward:` are both live queues — an item
    # already carried once must keep surviving until it's done or dropped.
    prior_next = []
    for key in ("next", "carried_forward"):
        vals = prior.get(key) or []
        if isinstance(vals, list):
            prior_next.extend(vals)
    if not prior_next:
        return body

    # Everything the incoming handoff accounts for.
    resolved = set()
    for key in ("done", "dropped", "next", "carried_forward"):
        vals = body.get(key) or []
        if isinstance(vals, list):
            for v in vals:
                resolved.add(_norm(v))

    # Words too common to signal that two items are the same work.
    _STOP = {
        "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "at",
        "is", "are", "be", "with", "from", "into", "task", "grove", "check",
        "add", "fix", "update", "run", "do", "this", "that", "it", "not",
        "p0", "p1", "p2", "p3", "standing", "new", "all", "per", "via",
    }

    def _tokens(s: str) -> set:
        out = set()
        for raw in s.split():
            t = raw.strip("[]()<>.,:;'\"—-%").lower()
            # 2 chars is the floor: state codes (VT, RI, TX) are among the most
            # distinctive tokens a handoff item carries.
            if len(t) < 2 or t in _STOP:
                continue
            out.add(t)
        return out

    def _ids(s: str) -> set:
        # Grove/commit ids: long hex-ish tokens. Strongest possible signal.
        out = set()
        for raw in s.split():
            t = raw.strip("[]()<>.,:;'\"")
            if len(t) >= 8 and all(c in "0123456789abcdef" for c in t.lower()):
                out.add(t.lower())
        return out

    def _claimed(needle: str) -> bool:
        n_ids, n_tok = _ids(needle), _tokens(needle)
        for r in resolved:
            if not r or not needle:
                continue
            # 1. Exact / containment of the full normalized string.
            if needle == r or needle in r or r in needle:
                return True
            # 2. Shared Grove task id — unambiguous.
            if n_ids and (n_ids & _ids(r)):
                return True
            # 3. Strong token overlap on distinctive words.
            r_tok = _tokens(r)
            if not n_tok or not r_tok:
                continue
            shared = n_tok & r_tok
            if len(shared) >= 2 and len(shared) >= 0.6 * min(len(n_tok), len(r_tok)):
                return True
        return False

    carried = [i for i in prior_next if not _claimed(_norm(i))]
    if not carried:
        return body

    existing = body.get("carried_forward") or []
    if not isinstance(existing, list):
        existing = [existing]
    seen = {_norm(x) for x in existing}
    for c in carried:
        if _norm(c) not in seen:
            existing.append(c)
            seen.add(_norm(c))
    body["carried_forward"] = existing
    return body


def cmd_write() -> int:
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        body = json.loads(raw) if raw.strip() else {}
    except Exception:
        body = {}

    root = _repo_root()
    meta = dict(body.get("meta", {}))
    htype = meta.get("type") or body.get("type") or "build"
    slug = meta.get("project") or _repo_slug(root)
    meta["project"] = slug
    meta["type"] = htype
    meta["surface"] = meta.get("surface", "claude-code")
    meta["generated"] = meta.get("generated") or _dt.datetime.now(
        _dt.timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    body["meta"] = meta
    body.pop("type", None)
    title = body.pop("title", None) or f"{slug} {htype} handoff"

    text = f"# Handoff: {title}\n\n{_to_yaml(body)}"

    dest = root / "HANDOFF.yaml"

    # Exit gate: never destroy unfinished work. Anything the prior handoff
    # queued in `next:` that this session didn't do or explicitly drop gets
    # carried into `carried_forward:` rather than silently overwritten.
    body = _carry_forward(body, dest)
    text = f"# Handoff: {title}\n\n{_to_yaml(body)}"

    dest.write_text(text, encoding="utf-8")
    print(str(dest))
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "inject":
        return cmd_inject()
    if cmd == "write":
        return cmd_write()
    sys.stderr.write("usage: session_handoff.py <inject|write>\n")
    return 0  # never non-zero — callable from a hook context


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
