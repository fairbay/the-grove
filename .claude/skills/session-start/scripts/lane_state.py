#!/usr/bin/env python3
"""Lane state by script: the mechanical rows of dispatch's state table, and the one data slot by
rank across lanes (Grove 6c8059b0 items 3 and 6; 02411f97; ruling eaa8913f; fairbay/ops
docs/lane-state/DESIGN.md).

For each declared lane it reads the evidence dispatch reads (the project row's lane line, the
lane's baton, its PRs, the decisions and session records, open cards, the last dispatch block,
the list) and prints a state with the evidence that set it:

  merge     a ready PR of the lane at gate row G3 (close-at-land commit, checks green) whose head
            is 10 minutes old or more: its session finished and waits on the merge (aaf31319)
  running   a draft PR of the lane whose head is under 6 hours old and newer than the lane's last
            record; or a lane decision (tagged lane-<x>, not a session record, not a Baylee
            ruling, not logged by a dispatch session) under 6 hours old and newer than both the
            lane's last record and its baton (02411f97: a PR is a lane's only by its baton file,
            its title or its branch; an owns: task's tag never makes one)
  prompted  the last dispatch block (not this session's) printed the lane's prompt under 2 hours
            ago and no record of the lane came after
  held      a HOLD row line names the lane (its release is the dispatcher's to read)
  call      an open card tagged lane-<x>, or a CARD row line naming the lane
  waiting   a data lane while another data lane is running or prompted, or ranks below the data
            lane given the slot
  ready     none of the above
Every state is printed with `check:` flags for what only a reader can settle: a START HERE that
waits on something (its wait phrases), a step of Baylee's, a time not yet reached, a hold's
scope and release, a ready PR outside G3, the data runner's open draft, a lane with no START
HERE. The escape (a later item that does not depend on the wait) stays the dispatcher's.
Approximations, stated: "merge" reads the head's age, not the checks' finish time (the report
carries no completed_at); "prompted" does not see a lane PR merged after the prompt (the report
lists open PRs only); a draft counts as running only when pushed after the lane's last record
(a session that archived after its last push is not running: #607, 2026-11-11).
A lane whose START HERE is timed for later does not take the slot. Lanes are ordered as the
row's lane lines are.

The row line against the baton (Grove d9692d9f; ledger 56d5da42, seen twice): a lane's row line
is in step with its baton when it names the session that wrote the baton (`meta.session`); a
line that names no session at all is in step when it names the baton's landing PR
(`meta.landing`). A PR number alone never makes a line that names another session current (a
continued draft keeps its number). Otherwise the direction is read from evidence, strongest
first: the lane's session records (a record of the row's session after the baton's
`meta.generated`: `newer`, the row line of an archive with no work PR, lanes.md "No archive-only
PR"; only records before it: `older`); a "Last done" date after the baton's: `newer`; the
baton's landing PR later than every PR of this repo the line cites: `older` (an archive that
landed its baton and left the row line: lane A, 2026-11-12); none of these: `differs`. An older
row line is not the lane's START HERE: the baton's first item is read instead, and a
`row-line:` check prints the sentence for the lane's prompt. Residual, stated: a row-only
archive written the same day as the baton, citing only earlier PRs, reads `older` until its
session record is logged. `--row-check <lane>` is the strict test for one lane at close-at-land
(step 7): exit 0 only when the row line names the session of the baton in --batons, 1 when it
does not, 2 when the row or the baton cannot be read.

The Go (Grove 89437cec; MBN trust chain G12): the one Go a prompt may carry is printed as `go:`.
It is read only from the Opening line of the lane's baton START HERE (`Opening line: "lane A:
Go: …"`), the place policy-check (f) holds to the repo's `harness.go`, and held to it here again
(`--policy`, default `.claude/policy.json` beside --batons): the sentence with only mNNNN filled,
after the same normalising (NFKC, zero-width characters out, straight quotes). A Go in the row's
lane line is never copied. No `go:` line means no Go, with a `no Go copied:` check that says why:
the baton carries none, harness.go could not be read, its Go is not harness.go, or the row line
is newer than (or not shown older than) a baton whose Go it does not repeat. A data lane whose
last archive wrote only the row line therefore asks for its Go: nothing checks a row line.

The data slot (eaa8913f, 1eb2c1f1): a lane is a data lane when its START HERE (up to the first
"Then") names an mNNNN batch it drafts, applies or publishes, or its row line or baton carries a
Go sentence, unless the START HERE says "data-free" or "No data batch". Among data lanes that are
otherwise ready the slot goes to the best key: an ISSUES rank (the START HERE's own "rank N" in
its opening parentheses, else the lane's list entry that names one of its ids or batches), then
a health red ("health red" in that header), then off-list; ties by row order. A lane whose list
pick is a better rank than its START HERE's data item is flagged `rank-order` (eaa8913f: a baton
may not put a lower-ranked or off-list data item ahead of a ranked one because it is cheap).

  lane_state.py --issues ISSUES.md --batons handoffs --prs PRS.json --fetch [--head-batons DIR]
                [--repo fairbay/<repo>] [--lanes a,b,c] [--session URL] [--now ISO] [--json]
                [--policy POLICY.json]
  lane_state.py ... --row ROW.json --decisions DEC.json --cards CARDS.json [--pr-files F.json]
  lane_state.py --row-check a --batons handoffs (--fetch | --row ROW.json) [--repo fairbay/<repo>]

PRS.json is pr_state.py's `report` JSON (its `prs` list). --head-batons is a directory of
lane-<x>.yaml files read from open PR heads: the newer `meta.generated` wins over --batons.
--fetch reads the row, every decision (paged) and the open cards of the slug with $GROVE_TOKEN,
and each lane-candidate PR's files with gh when --repo is given. Exit 0, 2 when an input cannot
be read. Python 3.11, stdlib only.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, name + ".py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


deps = _load("deps_check")
inext = _load("issues_next")
InputError = deps.InputError

ID = re.compile(r"\b[0-9a-f]{8}\b")
BATCH = re.compile(r"\bm1\d{3}\b")
# A verb of its own, not part of a name ("data-apply-r", "data-draft-r").
# Not another lane's ("once lane A applies m1388"), not a PR ("review draft PR #612 for m1391").
DATA_VERB = re.compile(r"(?<!lane [A-Za-z] )(?<![\w-])(?:apply|applies|applied|draft|drafts|publish|publishes)(?![\w-])(?! PR)"
                       r"[^.;()]{0,25}?\bm1\d{3}\b", re.I)
HOLD_DATA = re.compile(r"\(data\)|every data batch|data (?:batches|work)", re.I)
SLOT_WAIT = re.compile(r"data slot", re.I)
NOT_DATA = re.compile(r"data-free|no data batch", re.I)
GO = re.compile(r"\bGo:\s")
FRESH = timedelta(hours=6)
PROMPTED = timedelta(hours=2)
MERGE_SETTLE = timedelta(minutes=10)
DRAFTED_BY_RUNNER = "(drafted by data-draft-r)"
SESSION_ID = re.compile(r"\bsession_[0-9A-Za-z]{8,}\b")
# "#618", "written by #613", "MBN #621" are this repo's; "ops #159", "grove#40", "fairbay/ops#155" are not
PR_REF = re.compile(r"(?:\b(?:fairbay/)?([A-Za-z][\w.-]*))? ?#(\d+)\b")
OTHER_REPOS = {"ops", "grove"}  # the infrastructure repos a lane line cites beside its own (infra_queue.REPOS)
OPENING = re.compile(r"opening line[^:\n]{0,40}:[ \t]*", re.I)
LAST_DONE = re.compile(r"\bLast done (20\d\d-\d\d-\d\d)\b")


def when(s):
    return deps._when(s)


# ---------------------------------------------------------------- parsing

def lane_lines(row, lanes):
    out, holds, cards = {}, [], []
    for line in row:
        m = deps.LANE_LINE.match(line)
        if m and m.group(1).lower() in lanes:
            out[m.group(1).lower()] = line
        elif line.startswith("HOLD ("):
            holds.append(line)
        elif line.startswith("CARD "):
            cards.append(line)
    return out, holds, cards


def start_here(text):
    """(header, body): the START HERE's opening parentheses and its text up to the first Then."""
    i = text.find("START HERE")
    if i < 0:
        return "", ""
    rest = text[i + len("START HERE"):].lstrip()
    header = ""
    if rest.startswith("("):
        depth = 0
        for j, ch in enumerate(rest):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0:
                header, rest = rest[1:j], rest[j + 1:]
                break
    body = re.split(r"(?:\.|;)\s+Then\b|\bOpening line:", rest, maxsplit=1)[0]
    return header, body.lstrip(":. ").strip()


def baton(path):
    """{generated, first, landing, landing_repo, sessions}: a baton's meta.generated, its first
    next: item's text, and what its meta block says landed it (the PR of meta.landing, the
    session ids of meta.session)."""
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    g = re.search(r"^\s+generated:\s*'?\"?([0-9T:\-.Z+]+)", text, re.M)
    nxt = deps.baton_next(text)
    items = re.split(r"^- ", nxt, flags=re.M)
    raw = re.sub(r"\s+", " ", items[1]).strip() if len(items) > 1 else ""
    if len(raw) > 1 and raw[0] == raw[-1] == '"':  # YAML's two quote styles, each with its own escape
        first = raw[1:-1].replace('\\"', '"')
    elif len(raw) > 1 and raw[0] == raw[-1] == "'":
        first = raw[1:-1].replace("''", "'")
    else:
        first = raw.strip(" '\"").replace("''", "'")
    meta = re.search(r"^meta:[ \t]*\n((?:[ \t]+.*\n?|[ \t]*\n)*)", text, re.M)
    mtxt = meta.group(1) if meta else ""
    land = re.search(r"^[ \t]+landing:[ \t]*['\"]?(?:fairbay/)?([\w.-]+)#(\d+)", mtxt, re.M)
    # the session that wrote the baton: the first id in meta.session's own value (a prose value
    # may name an earlier session after it; review finding 1)
    ses = re.search(r"^([ \t]+)session:(.*(?:\n\1[ \t]+.*)*)", mtxt, re.M)
    return {"generated": g.group(1) if g else None, "first": first,
            "landing": int(land.group(2)) if land else None, "landing_repo": land.group(1) if land else None,
            "sessions": SESSION_ID.findall(ses.group(2))[:1] if ses else []}


def own_prs(line, repo=None):
    """The PR numbers a row line cites for its own repo: a `#n` of up to six digits, but not
    another repo's (`ops #159`, `ops PR #700`, `grove#40`, `fairbay/ops#155`, `anthropics/x#9`)."""
    out = set()
    for m in PR_REF.finditer(line):
        word = (m.group(1) or "").lower()
        before = line[:m.start(1)] if m.group(1) else ""
        owner = re.search(r"([\w.-]+)/$", before)
        if owner and (owner.group(1).lower() != "fairbay" or (repo and word != repo.lower())):
            continue
        if word == "pr":  # "ops PR #700": the repo is the word before
            prev = re.search(r"([\w.-]+)\s+$", before)
            word = prev.group(1).lower().split("/")[-1] if prev else word
        if word in OTHER_REPOS or len(m.group(2)) > 6:
            continue
        out.add(int(m.group(2)))
    return out


def row_step(line, bat, repo=None, records=(), strict=False):
    """(step, detail): how the row's lane line stands against the lane's baton.
    'in': the line names the session that wrote the baton; a line that names no session at all
    is in step when it names the baton's landing PR. A PR number alone does not make a line that
    names another session current: a continued draft keeps its number (review finding 1).
    Otherwise the direction comes from evidence, strongest first: the lane's session records (a
    record of the row's session after the baton was generated: 'newer', the row line of an
    archive with no work PR, lanes.md; only records before it: 'older'); a "Last done" date
    after the baton's: 'newer'; the baton's landing PR later than every PR of this repo the line
    cites: 'older'. No evidence: 'differs'. None: nothing to compare (no line, no baton, or a
    baton whose meta names no session and no landing PR).
    records: (time, session text) of the lane's session records. strict (close-at-land): the
    line must name the baton's session when the baton names one."""
    if not line or not bat:
        return None, ""
    b_sess, b_pr = set(bat.get("sessions") or []), bat.get("landing")
    if not b_sess and not b_pr:
        return None, ""
    r_sess, r_prs = set(SESSION_ID.findall(line)), own_prs(line, repo)
    same_repo = not (repo and bat.get("landing_repo")) or bat["landing_repo"].lower() == repo.lower()
    b_pr = b_pr if same_repo else None
    short = lambda s: "…" + s[-6:]  # noqa: E731
    detail = ("row names " + (", ".join([f"#{n}" for n in sorted(r_prs)[-3:]] + [short(s) for s in sorted(r_sess)]) or "no PR and no session")
              + "; baton " + ", ".join(([f"#{b_pr}"] if b_pr else []) + [short(s) for s in sorted(b_sess)]))
    if b_sess & r_sess:
        return "in", detail
    if b_pr and b_pr in r_prs and not (b_sess and (r_sess or strict)):
        return "in", detail
    if strict:
        return "differs", detail
    t_bat = when(bat["generated"]) if bat.get("generated") else None
    t_row = max((t for t, s in records if any(x in (s or "") for x in r_sess)), default=None)
    if t_bat and t_row:
        return ("newer" if t_row > t_bat else "older"), detail + f"; the row's session last recorded {t_row:%m-%d %H:%MZ}"
    done = LAST_DONE.search(line)
    if t_bat and done and done.group(1) > t_bat.strftime("%Y-%m-%d"):
        return "newer", detail + f"; Last done {done.group(1)}"
    if b_pr and r_prs and b_pr > max(r_prs):
        return "older", detail
    return "differs", detail


def stale_sentence(lane, bat, head=False):
    """The line dispatch puts on a lane's prompt when its row line is older than its baton."""
    where = f"#{bat['landing']}'s head" if head else f"main (#{bat['landing']})"
    return (f"The baton on {where} is newer than the row's lane {lane.upper()} line: "
            "follow the baton, and write the row line at the archive.")


# ---------------------------------------------------------------- the Go

def norm(text):
    """Text as a reader sees it, as policy-check.mjs normalizeBaton: NFKC, zero-width characters
    dropped, curly quotes straight."""
    t = unicodedata.normalize("NFKC", text or "")
    t = re.sub("[\u200b-\u200d\u2060\ufeff]", "", t)
    return re.sub("[\u2018-\u201b\u2032]", "'", re.sub("[\u201c-\u201f\u2033]", '"', t))


def opening_go(text, lane):
    """The lane's Opening-line Go in a START HERE text or a row line, as `lane X: Go: …`, or None.
    An Opening line that names another lane is not this lane's; one that names none is."""
    flat = norm(text)
    for m in OPENING.finditer(flat):
        rest = flat[m.end():]
        if rest[:1] == '"':
            body = rest[1:].split('"', 1)[0]
        elif rest[:1] == "'":
            close = re.search(r"'(?![A-Za-z])", rest[1:])
            body = rest[1:1 + close.start()] if close else rest[1:]
        else:
            body = rest.rstrip("'\" ")
        body = re.sub(r"\s+", " ", body).strip()
        named = re.match(r"lane\s+([a-z][a-z0-9]*)\s*:\s*", body, re.I)
        if named and named.group(1).lower() != lane:
            continue
        sentence = body[named.end():] if named else body
        if re.match(r"go\s*:", sentence, re.I):
            return f"lane {lane.upper()}: {sentence}"
    return None


def harness_go(path):
    """The repo's Go sentence (policy.json harness.go), or None when the file has none or cannot be read."""
    try:
        with open(path, encoding="utf-8") as fh:
            g = (json.load(fh).get("harness") or {}).get("go")
    except (OSError, ValueError, AttributeError):
        return None
    return g.strip() if isinstance(g, str) and g.strip() else None


def go_exact(go, harness):
    """True when `lane X: Go: …` is harness.go with only mNNNN filled (policy-check (f)'s test)."""
    want = re.sub(r"\s+", " ", re.sub(r"^Go:\s*", "", harness.strip(), flags=re.I))
    pat = re.escape(want).replace("mNNNN", "m[0-9]{4}")  # ASCII digits only, as the JS \d
    return re.fullmatch(r"lane [A-Z][A-Z0-9]*: Go: " + pat, go) is not None


def tags(d):
    return [t.lower() for t in d.get("tags") or []]


def ctx(d):
    c = d.get("context")
    if isinstance(c, dict):
        return c
    try:
        v = json.loads(c or "")
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def pr_lane(pr, files, lanes):
    """The lane a PR belongs to: its baton file, else 'lane X' in its title or branch (02411f97)."""
    hit = set()
    for f in files or []:
        m = re.fullmatch(r"handoffs/lane-([a-z])\.yaml", f)
        if m and m.group(1) in lanes:
            hit.add(m.group(1))
    if len(hit) == 1:
        return hit.pop()
    for s in (pr.get("title") or "", pr.get("head_ref") or ""):
        m = re.search(r"\blane[ _-]?([a-z])\b", s, re.I)
        if m and m.group(1).lower() in lanes:
            return m.group(1).lower()
    return None


# ---------------------------------------------------------------- ranking

def rank_key(lane, header, body, list_entries, list_pick):
    """(key, label): (0, n) a list rank, (1, 0) a health red, (2, 0) off-list."""
    # the first of the two the header names: lane E's "a health red, after …; rank 29 waits on
    # that slot too" is a health red (review finding 3)
    m = re.search(r"\brank (\d+)\b", header, re.I)
    r = re.search(r"health[- ]red", header, re.I)
    if r and (not m or r.start() < m.start()):
        return (1, 0), "health red"
    if m:
        return (0, int(m.group(1))), f"rank {m.group(1)}"
    toks = set(ID.findall(body)) | set(BATCH.findall(body))
    for e in list_entries.get(lane.upper(), []):
        if toks & (set(ID.findall(e["text"])) | set(BATCH.findall(e["text"]))):
            return (0, e["ranks"][0]), f"rank {e['ranks'][0]} (list entry)"
    if re.search(r"health[- ]red", body, re.I):
        return (1, 0), "health red"
    return (2, 0), "off-list"


# ---------------------------------------------------------------- the state

def compute(row, decisions, cards, prs, pr_files, batons_main, batons_head, issues_text, lanes, now, session=None,
            harness=None, repo=None):
    """harness: the repo's harness.go (None: no Go is printed, since none can be held to it).
    repo: the dispatched repo's short name, to tell its PR numbers from another repo's in a row line."""
    decisions = [d for d in decisions if when(d["created_at"]) <= now]  # a backtest reads the past as it was
    lines, holds, card_lines = lane_lines(row, lanes)
    try:
        lst = inext.compute(issues_text, [l.upper() for l in lanes])["lanes"]
        entries = inext.parse_lanes(issues_text)
    except inext.InputError as e:
        lst, entries = {}, {}
        list_error = str(e)
    else:
        list_error = None

    runner = [p for p in prs if DRAFTED_BY_RUNNER in (p.get("title") or "")]
    row_order = [m.group(1).lower() for l in row if (m := deps.LANE_LINE.match(l)) and m.group(1).lower() in lanes]
    order = row_order + [l for l in lanes if l not in row_order]
    last_block, last_block_at = None, None
    for d in sorted(decisions, key=lambda d: d["created_at"], reverse=True):
        c = ctx(d)
        if ("dispatch" in tags(d) and not d.get("superseded_by") and isinstance(c.get("dispatch"), dict)
                and c["dispatch"].get("lanes") and c.get("session") != session):
            last_block, last_block_at = c["dispatch"], d["created_at"]
            break

    out = {}
    for lane in lanes:
        line = lines.get(lane, "")
        bm, bh = batons_main.get(lane), batons_head.get(lane)
        bat = bm
        if bh and bh.get("generated") and (not bm or not bm.get("generated") or when(bh["generated"]) > when(bm["generated"])):
            bat = bh
        # the newer of the two is the lane's START HERE (lanes.md Layout): the row line, unless it
        # has none or is shown older than the baton (d9692d9f)
        lt = f"lane-{lane}"
        recs = [d for d in decisions if lt in tags(d) and "session-record" in tags(d)]
        step, step_detail = row_step(line, bat, repo, [(when(d["created_at"]), str(ctx(d).get("session") or "")) for d in recs])
        stale_row = step == "older" and bool((bat or {}).get("first"))
        source = line if "START HERE" in line and not stale_row else (bat or {}).get("first", "")
        header, body = start_here(source if "START HERE" in source else "START HERE " + source)
        ev, checks = [], []
        if stale_row:
            checks.append(f"row-line: older than the baton ({step_detail}): START HERE is read from the baton; "
                          f"on the lane's prompt: \"{stale_sentence(lane, bat, bat is bh)}\"")
        elif step == "newer":
            checks.append(f"row-line: newer than the baton ({step_detail}): the row line is the lane's START HERE "
                          "(an archive with no work PR, lanes.md)")
        elif step == "differs":
            checks.append(f"row-line: names another session than the baton ({step_detail}): the newer wins (lanes.md Layout); read both")
        # the Go: from the baton's Opening line only, held to harness.go (89437cec; G12)
        bgo, rgo = opening_go((bat or {}).get("first", ""), lane), opening_go(line, lane)
        go = None
        ids = lambda g: ", ".join(BATCH.findall(g or "")) or "no batch id"  # noqa: E731
        if bgo and not harness:
            checks.append("no Go copied: harness.go unread (no policy.json beside --batons, or --policy), so the baton's Go "
                          "cannot be held to it: the lane asks for a Go")
        elif bgo and not go_exact(bgo, harness):
            checks.append("no Go copied: the baton's Go is not the policy's harness.go with only mNNNN filled "
                          "(policy-check (f)); the lane's archive rewrites it, and the lane asks for a Go")
        elif bgo and step in ("newer", "differs") and rgo != bgo:
            checks.append(f"no Go copied: the row line is {'newer than' if step == 'newer' else 'not shown older than'} "
                          f"its baton and does not repeat the baton's Go (row {ids(rgo)}, baton {ids(bgo)}): the lane asks for a Go")
        elif bgo:
            go = bgo
            if rgo and rgo != bgo:
                checks.append(f"row Go differs from the baton's (row {ids(rgo)}, baton {ids(bgo)}): the baton's is the Go; "
                              "the lane's archive rewrites the row line")
        elif rgo:
            checks.append("no Go copied: the row line carries a Go its baton does not (a Go is read from the baton only): "
                          "the lane asks for a Go")
        last_rec = max((when(d["created_at"]) for d in recs), default=None)
        bat_at = when(bat["generated"]) if bat and bat.get("generated") else None
        floor = max([t for t in (last_rec, bat_at) if t] or [datetime.min.replace(tzinfo=timezone.utc)])
        ev.append(f"last record {last_rec:%m-%d %H:%MZ}" if last_rec else "no record")
        if bat_at:
            ev.append(f"baton {bat_at:%m-%d %H:%MZ}{' (PR head)' if bat is bh else ''}")

        state, why = None, None
        mine = [p for p in prs if pr_lane(p, pr_files.get(p["number"]), lanes) == lane
                and DRAFTED_BY_RUNNER not in (p.get("title") or "")]
        for p in mine:
            age = timedelta(days=float(p.get("head_age_days") or 0))
            head_at = now - age
            if not p.get("draft") and str(p.get("row", "")).startswith("G3") and age >= MERGE_SETTLE:
                state, why = "merge", f"#{p['number']} ready, G3 green, no push for {int(age.total_seconds() // 60)} min"
                break
            if not p.get("draft"):  # a ready PR in any other row: Step 2's or his (review finding 2)
                checks.append(f"ready PR #{p['number']} ({str(p.get('row', ''))[:40]}): the ready-PR rows (Step 2, or your step)")
            if p.get("draft") and age < FRESH and (last_rec is None or head_at > last_rec):
                state, why = "running", f"draft #{p['number']} pushed {head_at:%H:%MZ}"
        if not state:
            fresh = [d for d in decisions if lt in tags(d) and "session-record" not in tags(d)
                     and "baylee-ruling" not in tags(d) and "dispatch" not in tags(d)
                     and when(d["created_at"]) > floor and now - when(d["created_at"]) < FRESH]
            if fresh:
                d = max(fresh, key=lambda d: d["created_at"])
                state, why = "running", f"decision {d['id'][:8]} at {when(d['created_at']):%H:%MZ}, after the last record and baton"
        if not state and last_block and lane in (last_block.get("prompts") or {}):
            p = last_block["prompts"][lane]
            first = when(p["first"])
            if now - first < PROMPTED and not (last_rec and last_rec > first):
                state, why = "prompted", f"printed {first:%H:%MZ} (offered {p.get('offered')})"
        if not state:
            gate = [c for c in cards if lt in tags(c)] + [c for c in card_lines if re.search(rf"\blane {lane}\b", c, re.I)]
            if gate:
                state = "call"
                why = "open card " + ", ".join((c["id"][:8] if isinstance(c, dict) else c[:40]) for c in gate)
        # a Go makes a data lane; the Go of the START HERE in use (an older row line's does not count: review finding 4)
        has_go = bool(bgo) if stale_row else bool(go or GO.search(line))
        is_data = bool(not NOT_DATA.search(header + " " + body) and (DATA_VERB.search(body) or has_go))
        if state == "prompted":  # the prompt it was given decides, not START HERE (an escape is no data)
            txt = last_block["prompts"][lane].get("text") or ""
            is_data = bool(GO.search(txt) or DATA_VERB.search(txt)) and not NOT_DATA.search(txt)
        if not state:
            L = lane.upper()
            for h in holds:
                if re.search(rf"\b(?:lane )?{L} is not held\b", h):
                    continue
                named = re.search(rf"\blanes?\b[^.;]*\b{L}\b", h)
                if named or (is_data and HOLD_DATA.search(h) and not re.search(r"\blanes?\s+[A-H]\b", h)):
                    state, why = "held", h[:120]
                    checks.append("hold: does it cover this lane's work (its kind, its escape), and has its release happened?")
                    break
        if not line and not bat:
            checks.append("no START HERE read (no row line, no baton): the waiting row")
        if is_data and runner:
            checks.append(f"the runner's draft #{runner[0]['number']} is open: the runner rows decide the slot")
        key, key_label = rank_key(lane, header, body, entries, (lst.get(lane.upper()) or {}).get("next"))
        pick = (lst.get(lane.upper()) or {}).get("next")
        if is_data and pick and key[0] == 0 and key[1] != pick["rank"] and pick["rank"] < key[1]:
            checks.append(f"rank-order: START HERE is rank {key[1]}, the list's free pick is rank {pick['rank']}")
        if is_data and pick and key[0] > 0:
            checks.append(f"rank-order: START HERE is {key_label}, the list's free pick is rank {pick['rank']}")
        # whatever row set the state, the reader still needs these (review finding 9)
        checks += [f"waits: {ph.strip()[:100]}" for ph in deps.wait_phrases(body)]
        if re.search(r"\bBaylee\b", body):
            checks.append("his step: START HERE names Baylee")
        t = re.search(r"on or after (20\d\d-\d\d-\d\d)(?:[ T](\d\d:\d\d))?", body)
        if t and when(f"{t.group(1)}T{t.group(2) or '00:00'}:00Z") > now:
            checks.append(f"timed: on or after {t.group(1)[5:]} {t.group(2) or '00:00'}Z")
        out[lane] = {"state": state or "ready", "why": why, "data": is_data, "key": list(key), "rank": key_label,
                     "start_here": body[:160], "evidence": ev, "checks": checks, "go": go, "row_step": step}

    # the data slot (eaa8913f): running or prompted data lanes hold it; else the best key among
    # data lanes that can start now (a START HERE timed for later cannot: review finding 1)
    holder = next((l for l in order if out[l]["data"] and out[l]["state"] in ("running", "prompted")), None)
    ready = [l for l in order if out[l]["data"] and out[l]["state"] == "ready"]
    candidates = [l for l in ready if not any(c.startswith("timed:") for c in out[l]["checks"])]
    if not holder and candidates:
        holder = min(candidates, key=lambda l: (tuple(out[l]["key"]), order.index(l)))
        out[holder]["why"] = f"takes the data slot ({out[holder]['rank']})"
    # the holder's own waits that are not the slot itself make every demotion contingent
    other = [c for c in (out[holder]["checks"] if holder else [])
             if (c.startswith("waits: ") and not SLOT_WAIT.search(c) and "other batch" not in c) or c.startswith("his step")]
    for l in ready:
        if l != holder and holder:
            out[l]["state"] = "waiting"
            out[l]["why"] = (f"data slot: lane {holder.upper()} ({out[holder]['rank']}) before this lane ({out[l]['rank']})"
                             + (f"; contingent on lane {holder.upper()}'s checks" if other else "")
                             + "; escape to a non-data item if one is free")
    # a lane that is not a data lane but whose START HERE waits for the slot (lane D's "once the
    # data slot is free") waits while any lane holds it
    if holder:
        for l in order:
            s = out[l]
            if l != holder and not s["data"] and s["state"] == "ready" and any(
                    SLOT_WAIT.search(c) for c in s["checks"] if c.startswith("waits: ")):
                s["state"] = "waiting"
                s["why"] = f"its START HERE waits for the data slot, which lane {holder.upper()} takes; escape to an item that does not"
    return {"now": now.strftime("%Y-%m-%dT%H:%MZ"), "slot": holder, "order": order, "last_dispatch": last_block_at,
            "runner": [p["number"] for p in runner], "list_error": list_error, "lanes": {l: out[l] for l in order}}


def render(res):
    lines = [f"lane state {res['now']} (last dispatch {str(res['last_dispatch'])[:16] or 'none'}); data slot: "
             + (f"lane {res['slot'].upper()}" if res["slot"] else "free")
             + f"; row order {' '.join(l.upper() for l in res['order'])}"
             + (f"; runner drafts open: {', '.join('#' + str(n) for n in res['runner'])}" if res["runner"] else "")]
    if res["list_error"]:
        lines.append(f"  list unread: {res['list_error']}")
    for lane, s in res["lanes"].items():
        tag = " data" if s["data"] else ""
        lines.append(f"{lane.upper()}: {s['state']}{tag} [{s['rank']}]" + (f" — {s['why']}" if s["why"] else ""))
        lines.append(f"   evidence: {'; '.join(s['evidence'])}")
        if s.get("go"):
            lines.append(f"   go: {s['go']}")
        for c in s["checks"]:
            lines.append(f"   check: {c}")
    return "\n".join(lines)


# ---------------------------------------------------------------- inputs

def fetch_row(slug, g=None):
    g = g or deps._grove()
    try:
        rows = g.list_items("project", slug=slug, limit=1)
        if not rows:
            raise InputError(f"no project {slug}")
        return g.get("project", rows[0]["id"]).get("next_actions") or []
    except g.GroveError as e:
        raise InputError(f"Grove read failed: {e}")


def fetch(slug):
    g = deps._grove()
    row = fetch_row(slug, g)
    try:
        decisions, off = [], 0
        while off is not None:
            page = g._request("GET", "/api/decisions", query={"limit": 500, "offset": off, "project_ref": f"fairbay/{slug}"})
            decisions += page["decisions"]
            off = page.get("next_offset")
        cards = g._request("GET", "/api/adjudications", query={"list": slug, "status": "open", "limit": 500})["adjudications"]
    except g.GroveError as e:
        raise InputError(f"Grove read failed: {e}")
    return row, decisions, cards


def pr_files_gh(repo, numbers):
    out = {}
    for n in numbers:
        try:
            r = subprocess.run(["gh", "api", f"repos/{repo}/pulls/{n}/files", "--paginate", "--jq", ".[].filename"],
                               capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise InputError(f"gh: {e}")
        if r.returncode:
            raise InputError(f"gh pulls/{n}/files: {r.stderr.strip()[:200]}")
        out[n] = r.stdout.split()
    return out


def read_batons(d, lanes):
    if not d:
        return {}
    return {l: b for l in lanes if (b := baton(os.path.join(d, f"lane-{l}.yaml")))}


def row_check(lane, row, batons_dir, repo):
    """close-at-land step 7 in a lanes repo: 0 when the row's lane line is in step with the baton
    in batons_dir (it names the baton's session or its landing PR), else 1 with what to do."""
    line = lane_lines(row, [lane])[0].get(lane, "")
    bat = baton(os.path.join(batons_dir, f"lane-{lane}.yaml"))
    if not bat:  # a wrong directory, not a stale line: unread, exit 2
        raise InputError(f"no baton at {batons_dir}/lane-{lane}.yaml (run from the repo root, --batons handoffs)")
    step, detail = row_step(line, bat, repo, strict=True)
    L = lane.upper()
    if step == "in":
        print(f"row line: lane {L}'s line is in step with its baton ({detail})")
        return 0
    why = ("no row line begins 'Lane %s,'" % L if not line
           else "the baton's meta names no session and no landing PR" if step is None else detail)
    print(f"row line: lane {L}'s line is not in step with its baton ({why}). Rewrite the line so it names the session "
          f"that wrote the baton (meta.session; close-at-land step 4: grove.py lines <project id> --replace \"Lane {L}, \" <file>), "
          "then run this again: dispatch and the data runner read the row line as the lane's START HERE.")
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--issues", help="the repo's docs/ISSUES.md (not needed with --row-check)")
    ap.add_argument("--batons", required=True, help="the repo's handoffs/ directory (main)")
    ap.add_argument("--head-batons", help="lane-<x>.yaml files read from open PR heads")
    ap.add_argument("--prs", help="pr_state.py report JSON (not needed with --row-check)")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--slug", default="medicaid-benefits-navigator")
    ap.add_argument("--repo", help="fairbay/<repo>: read PR files with gh; its name tells its PR numbers from another repo's")
    ap.add_argument("--policy", help="the repo's policy.json (harness.go); default: .claude/policy.json beside --batons")
    ap.add_argument("--row-check", metavar="LANE", help="only test that this lane's row line is in step with its baton: exit 0 or 1")
    ap.add_argument("--row"), ap.add_argument("--decisions"), ap.add_argument("--cards")
    ap.add_argument("--pr-files", help="tests: JSON {number: [files]}")
    ap.add_argument("--lanes", default="a,b,c,d,e,h")
    ap.add_argument("--session", help="this session's URL: its own dispatch block is not the last one")
    ap.add_argument("--now")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    lanes = [l.strip().lower() for l in a.lanes.split(",") if l.strip()]
    repo = (a.repo or a.slug).split("/")[-1]
    try:
        if a.row_check:
            if not (a.fetch or a.row):
                raise InputError("--row-check needs --fetch or --row")
            return row_check(a.row_check.strip().lower(), fetch_row(a.slug) if a.fetch else deps.load_json(a.row), a.batons, repo)
        if not (a.issues and a.prs):
            raise InputError("--issues and --prs are required")
        now = when(a.now) if a.now else datetime.now(timezone.utc)
        harness = harness_go(a.policy or os.path.join(os.path.dirname(os.path.abspath(a.batons)), ".claude", "policy.json"))
        with open(a.issues, encoding="utf-8") as fh:
            issues_text = fh.read()
        rep = deps.load_json(a.prs)
        prs = rep.get("prs", rep) if isinstance(rep, dict) else rep
        if a.fetch:
            row, decisions, cards = fetch(a.slug)
        else:
            if not (a.row and a.decisions):
                raise InputError("--fetch, or --row and --decisions")
            row, decisions = deps.load_json(a.row), deps.load_json(a.decisions)
            cards = deps.load_json(a.cards) if a.cards else []
        if a.pr_files:
            files = {int(k): v for k, v in deps.load_json(a.pr_files).items()}
        elif a.fetch and a.repo:
            files = pr_files_gh(a.repo, [p["number"] for p in prs])
        else:
            files = {}
        res = compute(row, decisions, cards, prs, files, read_batons(a.batons, lanes),
                      read_batons(a.head_batons, lanes), issues_text, lanes, now, a.session, harness, repo)
    except (InputError, OSError, ValueError, KeyError) as e:
        print(f"lane state: unread ({e})", file=sys.stderr)
        return 2
    print(json.dumps(res, indent=1, default=str) if a.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
