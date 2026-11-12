#!/usr/bin/env python3
"""The infrastructure queue: lane H's next item from the open Grove tasks of lists ops and grove.

Dispatch (session-start references/dispatch.md, Step 1 read 7, second paragraph) runs this for a
lane whose row line names another repo (MBN's lane H); the pick, the notes and the skips go to the
record's cleanup list ("H: queue pick 0eeb2807; START HERE e6a91e53"), never to the screen. A lane
H archive runs it before writing START HERE (chat-archive references/lanes.md, Exit). The design
and its rules: fairbay/ops docs/infra-queue/DESIGN.md §4.1, §4.2.

  infra_queue.py [--fetch] [--lists ops,grove] [--owned ops#139,grove#24,…] [--cards-open 1a2b3c4d,…] [--json]
  infra_queue.py --tasks OPS.json [GROVE.json …] [--now 2026-11-09T19:00Z] …     (tests only)

`--fetch` is the default and the production path: grove.py (the grove skill's client, loaded by
path) reads each list with `$GROVE_TOKEN`, so no bulk rows ride in the dispatcher's tool
arguments (`.claude/global/delegation.md` "Efficiency rules"). `--tasks` takes JSON arrays of task rows as
grove_list_tasks(compact=false) returns them, for tests.

Out (the first rule that matches names the skip): status not open; tagged `ledger` (the weekly
read encodes it, process-governance DESIGN.md §4.3); tagged `adjudication` (his card); a tag
starting `routine:` (a routine's work order); tagged `lane-<x>` for x other than h (another
lane's); tagged `direction` (waits on his card; `design` and `design-run` stay in: design runs are
lane H work); tagged `ios` or `daily-os` (Earmark work: an interim rule until Baylee's prune card
e9159cc8 is answered and moves it to list earmark); tagged `blocked`, `parked` or `post-v1`;
tagged `card-open`; a notes line `card: <8 hex>` (with `--cards-open`, only a card in that set:
another is answered and the task gets a note "card <id8> answered, not landed"); a notes line
`owns: fairbay/<repo>#<n>` (with `--owned repo#n,…`, only a PR in that set: another is merged or
closed and the task gets a note "owns a PR not open"); a `due_at` after now; a project_ref that is
null or neither fairbay/ops nor fairbay/grove (a filing fault). A list/project_ref mismatch
between the two (list grove with fairbay/ops, or the reverse) is not a skip: the repo is the
project_ref's and a note names it.

Order: the ruled tier first (tagged `baylee-ruling` or `ready-for-code`), then the rest; inside a
tier priority high to low, then `from-mbn` first, then oldest `created_at`. Priority defaults to 0
at filing and is set unevenly, so it is a weak signal: that is why a ruled item comes first.

Exit 0; 2 (no pick: `pick: queue unread (<reason>)` on stdout, the reason on stderr) when the read
fails (no token, an HTTP error), a list returns as many rows as the read asked for (it may be
truncated), a file cannot be read or parsed or is not an array, or a row lacks id, list, tags,
priority or created_at. Python 3.11, stdlib only.
"""
import argparse
import datetime
import importlib.util
import json
import os
import re
import sys

REQUIRED = ("id", "list", "tags", "priority", "created_at")
REPOS = {"ops": "fairbay/ops", "grove": "fairbay/grove"}
CARD_LINE = re.compile(r"^\s*card: ([0-9a-f]{8})", re.M)
OWNS_ANY = re.compile(r"^\s*owns:\s*\S", re.M)
OWNS = re.compile(r"^\s*owns:\s*fairbay/([a-z0-9-]+)#(\d+)", re.M)
LANE_TAG = re.compile(r"lane-([a-z][a-z0-9]*)")
HOLD_TAGS = ("blocked", "parked", "post-v1")
EARMARK_TAGS = ("ios", "daily-os")
RULED_TAGS = ("baylee-ruling", "ready-for-code")
ORDER = "order: ruled, then priority, then from-mbn, then oldest"
FETCH_LIMIT = 200  # grove.py list_items' ceiling for tasks
GROVE_PY = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "grove", "scripts", "grove.py"))


class InputError(Exception):
    pass


def parse_time(s, what):
    """An ISO-8601 time as an aware UTC datetime (a date alone is midnight UTC)."""
    if not isinstance(s, str) or not s.strip():
        raise InputError(f"{what} is not a time: {s!r}")
    try:
        t = datetime.datetime.fromisoformat(s.strip())
    except ValueError:
        raise InputError(f"{what} is not an ISO-8601 time: {s!r}")
    return t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)


def check_rows(rows, where):
    """The rows as given, refusing a row the queue cannot judge (fail safe: never a pick from a partial read)."""
    if not isinstance(rows, list):
        raise InputError(f"{where}: want a JSON array of task rows, got {type(rows).__name__}")
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            raise InputError(f"{where}: row {i} is not an object")
        missing = [k for k in REQUIRED if r.get(k) is None]
        if missing:
            raise InputError(f"{where}: row {i} ({str(r.get('id') or '?')[:8]}) lacks {', '.join(missing)}")
        if not isinstance(r["tags"], list):
            raise InputError(f"{where}: row {i} ({r['id'][:8]}) tags is not a list")
        if not isinstance(r["priority"], int) or isinstance(r["priority"], bool):
            raise InputError(f"{where}: row {i} ({r['id'][:8]}) priority is not an integer")
        parse_time(r["created_at"], f"{where}: row {i} ({r['id'][:8]}) created_at")
    return rows


def parse_owned(s):
    """'ops#139,fairbay/grove#24,medicaid-benefits-navigator#491' -> {('ops', 139), ('grove', 24), …}."""
    out = set()
    for tok in (s or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        m = re.fullmatch(r"(?:fairbay/)?([a-z0-9-]+)#(\d+)", tok)
        if not m:
            raise InputError(f"--owned: {tok!r} is not repo#n (ops#139, grove#24, medicaid-benefits-navigator#491)")
        out.add((m.group(1), int(m.group(2))))
    return out


def parse_cards(s):
    out = set()
    for tok in (s or "").split(","):
        tok = tok.strip().lower()
        if not tok:
            continue
        if not re.fullmatch(r"[0-9a-f]{8}", tok[:8]):
            raise InputError(f"--cards-open: {tok!r} is not a card id (8 hex)")
        out.add(tok[:8])
    return out


def mismatch(r):
    """The list/project_ref note for a task filed on one infrastructure list with the other's repo, or None."""
    ref, lst = r.get("project_ref"), r["list"]
    if ref in REPOS.values() and lst in REPOS and REPOS[lst] != ref:
        return f"list {lst} but project_ref {ref}"
    return None


def judge(r, owned, cards_open, now):
    """(the rule that skips the task or None, the notes the cleanup needs)."""
    tags = [str(t) for t in r["tags"]]
    tagset = set(tags)
    notes_text = r.get("notes") or ""
    notes = []
    cards = CARD_LINE.findall(notes_text)
    card_held = bool(cards) if cards_open is None else any(c in cards_open for c in cards)
    if cards_open is not None:
        notes += [f"card {c} answered, not landed" for c in cards if c not in cards_open]
    owns = [(repo, int(n)) for repo, n in OWNS.findall(notes_text)]
    if owned is None:
        owns_held = bool(OWNS_ANY.search(notes_text))
    else:
        owns_held = any(o in owned for o in owns)
        notes += [f"owns a PR not open: {repo}#{n}" for repo, n in owns if (repo, n) not in owned]

    status = r.get("status", "open")
    rule = None
    lanes = [m.group(1) for t in tags for m in [LANE_TAG.fullmatch(t)] if m and m.group(1) != "h"]
    if status != "open":
        rule = f"status {status}"
    elif "ledger" in tagset:
        rule = "ledger (the weekly read encodes it)"
    elif "adjudication" in tagset:
        rule = "an adjudication card (his)"
    elif any(t.startswith("routine:") for t in tags):
        rule = "a routine's work order"
    elif lanes:
        rule = f"another lane's: lane {lanes[0]}"
    elif "direction" in tagset:
        rule = "direction: waits on his card"
    elif tagset & set(EARMARK_TAGS):
        rule = "Earmark work; card e9159cc8 moves it"
    elif tagset & set(HOLD_TAGS):
        rule = "tagged " + next(t for t in HOLD_TAGS if t in tagset)
    elif "card-open" in tagset:
        rule = "tagged card-open (waits on his card)"
    elif card_held:
        held = [c for c in cards if cards_open is None or c in cards_open]
        rule = f"notes carry 'card: {held[0]}' (waits on his card)"
    elif owns_held:
        if owned is None:
            m = OWNS_ANY.search(notes_text)
            rule = notes_text[m.start():].splitlines()[0].strip() + " (in progress; no --owned given)"
        else:
            repo, n = next(o for o in owns if o in owned)
            rule = f"owns {repo}#{n}, open (in progress)"
    else:
        due = r.get("due_at")
        ref = r.get("project_ref")
        if due:
            try:
                if parse_time(due, "due_at") > now:
                    rule = f"due_at {due[:10]} (a wait until then)"
            except InputError:
                rule = f"due_at {due!r} unreadable (fail safe)"
        if rule is None and ref not in REPOS.values():
            rule = f"filing fault: project_ref {ref or 'null'}"
    return rule, notes


def entry(r):
    return {"id": r["id"], "id8": r["id"][:8], "list": r["list"], "project_ref": r.get("project_ref"),
            "priority": r["priority"], "created": parse_time(r["created_at"], "created_at").date().isoformat(),
            "title": r.get("title") or "", "ruled": any(t in r["tags"] for t in RULED_TAGS),
            "from_mbn": "from-mbn" in r["tags"], "note": mismatch(r)}


def compute(rows, owned=None, cards_open=None, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    seen, skipped, eligible, notes = set(), [], [], []
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        rule, task_notes = judge(r, owned, cards_open, now)
        notes += [f"{r['id'][:8]} — {n}" for n in task_notes]
        if rule:
            s = {"id8": r["id"][:8], "list": r["list"], "rule": rule}
            if mismatch(r):
                s["note"] = mismatch(r)
            skipped.append(s)
        else:
            eligible.append(r)
    eligible.sort(key=lambda r: (0 if any(t in r["tags"] for t in RULED_TAGS) else 1, -r["priority"],
                                 0 if "from-mbn" in r["tags"] else 1, parse_time(r["created_at"], "created_at"), r["id"]))
    pick = None
    if eligible:
        pick = entry(eligible[0])
        pick["repo"] = eligible[0]["project_ref"]
    return {"pick": pick, "order": ORDER, "notes": notes, "skipped": skipped, "queued": [entry(r) for r in eligible[1:]]}


def render(res):
    p = res["pick"]
    if p:
        L = [f"pick: {p['id8']} {p['list']} {p['project_ref']} p{p['priority']} {p['created']} — {p['title'][:100]}"]
        if p["note"]:
            L.append(f"note: {p['note']}")
    else:
        L = ["pick: nothing queued"]
    L.append(res["order"])
    L += [f"notes: {n}" for n in res["notes"]]
    L.append(f"skipped ({len(res['skipped'])}):")
    L += [f"  {s['id8']} {s['list']} — {s['rule']}" + (f"; note: {s['note']}" if s.get("note") else "") for s in res["skipped"]]
    L.append(f"queued behind the pick ({len(res['queued'])}):")
    L += [f"  {q['id8']} {q['list']} p{q['priority']} {q['created']} — {q['title'][:80]}" + (f"; note: {q['note']}" if q["note"] else "")
          for q in res["queued"]]
    return "\n".join(L)


def read_files(paths):
    rows = []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
        except OSError as e:
            raise InputError(f"cannot read {p}: {e.strerror or e}")
        except ValueError as e:
            raise InputError(f"{p} is not JSON: {e}")
        rows += check_rows(data, p)
    return rows


def fetch(lists):
    if not os.environ.get("GROVE_TOKEN", "").strip():
        raise InputError("GROVE_TOKEN is not set (Code sessions and routines have it)")
    if not os.path.exists(GROVE_PY):
        raise InputError(f"no grove.py at {GROVE_PY}")
    spec = importlib.util.spec_from_file_location("grove_client", GROVE_PY)
    grove = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(grove)
    rows = []
    for lst in lists:
        try:
            got = grove.list_items("task", status="open", list=lst, limit=FETCH_LIMIT)
        except Exception as e:  # GroveError, network, config: nothing picked from a failed read
            raise InputError(f"list {lst}: {e}")
        if len(got) >= FETCH_LIMIT:
            raise InputError(f"list {lst} returned the cap ({len(got)}): page past it (Grove task 963701ad) before trusting the pick")
        rows += check_rows(got, f"list {lst}")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fetch", action="store_true", help="read the lists through grove.py with $GROVE_TOKEN (the default)")
    ap.add_argument("--tasks", nargs="+", metavar="FILE", help="tests only: JSON arrays of open task rows instead of --fetch")
    ap.add_argument("--lists", default="ops,grove", help="lists --fetch reads (default ops,grove)")
    ap.add_argument("--owned", help="open PRs as repo#n, comma-separated (ops#139,grove#24,medicaid-benefits-navigator#491)")
    ap.add_argument("--cards-open", help="open card ids (8 hex), comma-separated")
    ap.add_argument("--now", help="the time due_at is judged against (default: UTC now)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.fetch and a.tasks:
            raise InputError("--fetch and --tasks together: give one")
        owned = parse_owned(a.owned) if a.owned is not None else None
        cards = parse_cards(a.cards_open) if a.cards_open is not None else None
        now = parse_time(a.now, "--now") if a.now else None
        rows = read_files(a.tasks) if a.tasks else fetch([x.strip() for x in a.lists.split(",") if x.strip()])
        res = compute(rows, owned, cards, now)
    except InputError as e:
        print(f"infra_queue.py: {e}", file=sys.stderr)
        print(json.dumps({"pick": None, "unread": str(e)}) if a.json else f"pick: queue unread ({e})")
        return 2
    print(json.dumps(res, indent=1) if a.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
