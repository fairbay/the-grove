#!/usr/bin/env python3
"""Dependency check: every wait a lane repo cites is open, owned and queued (Grove 6c8059b0).

A wait is an 8-hex Grove id cited as a blocker in one of the places dispatch reads:
  - a "Waits on" cell of docs/ISSUES.md's list table (a struck row waits on nothing);
  - the wait clause of an entry of its "How lanes pull from it" table (not one marked "now");
  - a wait phrase in a lane row line of the project row ("Lane X, ..."): the text after a
    wait word (a closed list: once, after, when, until, behind, waits on/for, waiting on/for,
    blocked by/on, depends on, held by, held up by) up to the sentence's end (". ", ";" or
    ": ") or a comma that does not go on with an and/or list of ids.
An id its own text marks as over ("done", "(done …)", "was done", "answered", "'a'") is
evidence, not a wait; "is answered" is a wait. A date-shaped token (20261109) is not an id.

Each cited id is looked up in the open Grove tasks of the lists read and in the decisions:
  ok         an open task owned by a lane that plans it (its row line, its baton's next:, its
             list row's Folds cells or entries), an open card (tag adjudication), a task of
             Baylee's (tag baylee, or list mbn-launch-ops), or a decision;
  STALE      neither an open task of the lists read nor a decision: done, dropped, on another
             list, or not a Grove id. A finding to fix in the text, never proof the wait is
             over: nothing reads a STALE wait as released;
  UNOWNED    an open task with no lane-x tag and not Baylee's: nothing will clear it;
  UNQUEUED   an open task tagged lane-x that its lane plans nowhere;
  MISLABELED a place says "lane X's <id>" or "<id> (lane X)" but the task is tagged lane-Y.
A rank on a lane's list row whose Waits-on cell starts with "—" but carries more text is
CLOSED_NOT_FREE: issues_next.py reads only an exact "—" as free, so the rank is held for nothing.

Freed (task df2da0a4, fairbay/ops docs/partial-dispatch/DESIGN.md): with --freed-since ISO and/or
--item TOKEN, also print what finished (Grove tasks and cards completed or dropped since, from
the event log; batches, PRs or ids named with --item) and every place still waiting on it: a wait
phrase in a lane row line, a baton's next:, an ISSUES entry or Waits-on cell, or an open task's
notes that names a finished item by id, by token, or by the gate its task is tagged with
(gate-g9 -> "waits for G9"). A hit is a finding for the lane, never proof the place is free.

  deps_check.py --issues docs/ISSUES.md --fetch [--batons handoffs] [--slug S] [--json] [--report]
                [--freed-since ISO] [--item m1384 --item '#575' ...]
  deps_check.py --issues F --row ROW.json --tasks TASKS.json [--decisions DEC.json] ...   (tests)

--fetch reads with $GROVE_TOKEN through the grove skill's grove.py: the project row, the open
tasks of lists <slug>, mbn-launch-ops, ops and grove, and every decision (paged). Exit 0 when
there is no finding, 1 when there is one, 2 when an input cannot be read; --report exits 0 in
every case (it prints "deps: unread (<reason>)" on stderr), so a pre_ready line never blocks.
Python 3.11, stdlib only.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

ID = re.compile(r"\b[0-9a-f]{8}\b", re.I)
NUM = re.compile(r"\d+")
DATE = re.compile(r"20\d\d[01]\d[0-3]\d")
# The wait words (a closed list: a wait written another way is not read).
WAIT_WORD = re.compile(r"\b(once|after|when|until|behind|waits? (?:on|for)|waiting (?:on|for)|"
                       r"blocked (?:by|on)|depends on|held (?:up )?by)\b", re.I)
LANE_LINE = re.compile(r"^Lane ([A-Z])\b[,:( ]")
# "lane A's cc9a702b, 6591985c and lane E's 7b4172e1": the ids right after one "lane X's".
LANE_POSSESSIVE = re.compile(r"\blane ([A-Z])'s ((?:[0-9a-f]{8}(?:, | and |,)?\s*)+)", re.I)
ID_THEN_LANE = re.compile(r"\b([0-9a-f]{8}) \(lane ([A-Z])\b", re.I)
# An id its own text marks as over is evidence, not a wait: "7b4172e1 done", "7b4172e1 (done
# 11-09)", "7b4172e1 was done", "card 4a0fda55 answered 'a'", "card 501962e6 'a'". The present
# tense is a wait: "until card 1234abcd is answered" (review finding 1).
EVIDENCE = re.compile(r"\)?\s*\(?\s*(?:was )?(?:done\b|answered\b|'[a-z]')", re.I)


def waits_in(text):
    """The ids a text cites as waits, lower-cased: an id marked as over is skipped, and so is a
    date-shaped token (20261109). Other all-digit ids are real (76787135)."""
    return [m.group(0).lower() for m in ID.finditer(text)
            if not DATE.fullmatch(m.group(0)) and not EVIDENCE.match(text, m.end())]
# A comma ends a wait phrase unless an "and"/"or" list of blockers goes on after it ("once X
# lands, then Y" names what comes next, not a blocker: review finding 4).
LIST_GOES_ON = re.compile(r"\s*(?:and |or )?(?:lane [A-Z]'s |card |its own |the )?"
                          r"(?:[0-9a-f]{8}|G\d+|gate-g\d+|m\d{4}|#\d+)\b"
                          r"(?!\s+(?:opens|starts|follows|comes|is next))", re.I)
OTHER_LISTS = ("mbn-launch-ops", "ops", "grove")
GROVE_PY = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "grove", "scripts", "grove.py"))


class InputError(Exception):
    pass


# ---------------------------------------------------------------- reading the places

def wait_phrases(text):
    """The wait phrases of one line of prose: each runs from a wait word to the sentence's end
    or a comma that does not continue a list of ids."""
    out = []
    for m in WAIT_WORD.finditer(text):
        rest = text[m.start():]
        end = len(rest)
        for stop in re.finditer(r"\. |;|: |\.$", rest):
            end = stop.start()
            break
        phrase = rest[:end]
        cut = len(phrase)
        for c in re.finditer(",", phrase):
            if not LIST_GOES_ON.match(phrase[c.end():]):
                cut = c.start()
                break
        out.append(phrase[:cut])
    return out


def table_rows(text, heading):
    lines = text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip().lower() == f"## {heading}".lower()) + 1
    except StopIteration:
        raise InputError(f"no section '## {heading}'")
    header, rows = None, []
    for ln in lines[start:]:
        if ln.startswith("## "):
            break
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if all(set(c) <= set(":- ") for c in cells):
            continue
        if header is None:
            header = [c.lower() for c in cells]
            continue
        rows.append(dict(zip(header, cells)) if len(cells) == len(header) else None)
    return header, rows


ENTRIES = re.compile(r",\s*(?![^()]*\))")


def lane_rows(issues_text):
    """{lane: [entry, ...]} from "How lanes pull from it"; InputError when the table is unreadable."""
    header, rows = table_rows(issues_text, "How lanes pull from it")
    if not header or "lane" not in header or "ranks, in order" not in header:
        raise InputError("the lanes table has no Lane / Ranks, in order columns")
    out = {}
    for r in rows:
        if r is None:
            raise InputError("a lanes-table row has a different column count")
        out[r["lane"]] = [e.strip() for e in ENTRIES.split(r["ranks, in order"]) if e.strip()]
    return out


def entry_rank(entry):
    m = NUM.match(entry)
    return int(m.group()) if m else None


def cited(issues_text, row_lines):
    """([(id, place, text)] for every id cited as a wait, [(rank, cell)] for every rank on a
    lane's row whose Waits-on cell starts with "—" but carries more text: issues_next.py reads
    only an exact "—" as free, so such a rank is held for nothing (review finding 7))."""
    out, closed_not_free = [], []
    header, rows = table_rows(issues_text, "The list")
    if not header or "waits on" not in header:
        raise InputError("the list table has no Waits on column")
    lanes = lane_rows(issues_text)
    on_a_row = {entry_rank(e) for entries in lanes.values() for e in entries}
    for r in rows:
        if r is None:
            raise InputError("a list row has a different column count")
        if any("~~" in c for c in r.values()) or r.get("count (reach first)", "").lower().startswith("struck"):
            continue  # a struck row waits on nothing
        cell = r["waits on"].strip()
        if cell[:1] in ("—", "-", ""):
            rank = entry_rank(r.get("#", ""))
            if cell not in ("—", "-", "") and rank in on_a_row:
                closed_not_free.append((rank, cell))
            continue
        for i in waits_in(cell):
            out.append((i, f"ISSUES rank {r.get('#', '?')}", cell))
    for lane, entries in lanes.items():
        for entry in entries:
            if re.search(r"\bnow\b", entry):
                continue
            for phrase in wait_phrases(entry):  # the wait clause only (review finding 5)
                for i in waits_in(phrase):
                    out.append((i, f"ISSUES lane {lane} entry", entry))
    for line in row_lines:
        m = LANE_LINE.match(line)
        if not m:
            continue
        for phrase in wait_phrases(line):
            for i in waits_in(phrase):
                out.append((i, f"lane {m.group(1)} row line", phrase))
    return out, closed_not_free


def list_queue(issues_text):
    """{lane: ids} a lane's list row plans: the Folds cells of its ranks (a fold is work the rank
    does) and the ids its own entries name ("2 (the handbook read cc9a702b, now)"). A Waits-on
    cell is not a plan: a blocker cited there is the waiting rank's wait (review finding 6)."""
    _, rows = table_rows(issues_text, "The list")
    folds = {}
    for r in rows:
        if r and entry_rank(r.get("#", "")) is not None:
            folds[entry_rank(r["#"])] = {i.lower() for i in ID.findall(r.get("folds", ""))}
    out = {}
    for lane, entries in lane_rows(issues_text).items():
        ids = set()
        for e in entries:
            ids |= folds.get(entry_rank(e), set())
            ids |= {i.lower() for i in ID.findall(e)}
        out[lane] = ids
    return out


def lane_labels(text):
    """{id: lane} for each id a text attributes to a lane."""
    labels = {}
    for m in LANE_POSSESSIVE.finditer(text):
        for i in ID.findall(m.group(2)):
            labels[i] = m.group(1)
    for m in ID_THEN_LANE.finditer(text):
        labels[m.group(1)] = m.group(2)
    return labels


def baton_next(text):
    """The text of a baton's next: block (top-level key to the next top-level key)."""
    m = re.search(r"^next:\s*$(.*?)(?=^[A-Za-z_][\w-]*:)", text + "\nend:\n", re.M | re.S)
    return m.group(1) if m else ""


# ---------------------------------------------------------------- judging

def owner(task):
    tags = [t.lower() for t in task.get("tags") or []]
    if "adjudication" in tags:
        return "card"
    if "baylee" in tags or task.get("list") == "mbn-launch-ops":
        return "baylee"
    lanes = sorted({t[5:].upper() for t in tags if re.fullmatch(r"lane-[a-z]", t)})
    return lanes[0] if len(lanes) == 1 else ("+".join(lanes) if lanes else None)


def judge(cites, tasks, decisions, row_lines, batons, queue=None):
    """{id: {kind, places, ...}} over every cited id. `queue` is list_queue()'s {lane: ids}."""
    queue = queue or {}
    by_prefix = {t["id"][:8].lower(): t for t in tasks if t.get("status", "open") == "open"}
    dec = {d["id"][:8].lower() for d in decisions}
    lane_text = {}
    for line in row_lines:
        m = LANE_LINE.match(line)
        if m:
            lane_text[m.group(1)] = lane_text.get(m.group(1), "") + " " + line
    found = {}
    for i, place, text in cites:
        f = found.setdefault(i, {"id": i, "places": [], "texts": []})
        if place not in f["places"]:
            f["places"].append(place)
            f["texts"].append(text)
    for i, f in found.items():
        t = by_prefix.get(i)
        if t is None:
            f["kind"] = "ok" if i in dec else "STALE"
            f["why"] = ("a decision" if i in dec else
                        "not an open task of the lists read: done, dropped, on another list, or not a Grove id")
            continue
        f["title"] = (t.get("title") or "")[:90]
        o = owner(t)
        f["owner"] = o
        labels = {}
        for tx in f["texts"]:
            labels.update({k: v for k, v in lane_labels(tx).items() if k == i})
        said = labels.get(i)
        if o in ("card", "baylee"):
            f["kind"], f["why"] = "ok", ("an open card" if o == "card" else "Baylee's")
        elif o is None:
            f["kind"], f["why"] = "UNOWNED", "open, no lane-x tag, not Baylee's"
        elif said and said not in o.split("+"):
            f["kind"], f["why"] = "MISLABELED", f"cited as lane {said}'s, tagged lane-{o.lower()}"
        elif not any(i in lane_text.get(L, "") or i in batons.get(L, "") or i in queue.get(L, set())
                     for L in o.split("+")):
            f["kind"], f["why"] = "UNQUEUED", f"lane {o}'s row line, baton next: and list row never name it"
        else:
            f["kind"], f["why"] = "ok", f"lane {o}, queued"
    return found


def summary(found, closed_not_free=()):
    kinds = {}
    for f in found.values():
        kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    order = ["STALE", "UNOWNED", "UNQUEUED", "MISLABELED", "ok"]
    head = f"deps: {len(found)} cited; " + ", ".join(f"{k} {kinds[k]}" for k in order if k in kinds)
    if closed_not_free:
        head += f"; CLOSED_NOT_FREE {len(closed_not_free)}"
    lines = [head]
    for k in order[:-1]:
        for f in sorted((f for f in found.values() if f["kind"] == k), key=lambda f: f["id"]):
            lines.append(f"  {k} {f['id']}: {f['why']}; cited in {', '.join(f['places'])}"
                         + (f" ({f['title']})" if f.get("title") else ""))
    for rank, cell in closed_not_free:
        lines.append(f"  CLOSED_NOT_FREE rank {rank}: its Waits-on cell is not exactly \"—\", so issues_next.py "
                     f"holds it: {cell[:80]}")
    return "\n".join(lines)


# ---------------------------------------------------------------- freed (docs/partial-dispatch/DESIGN.md)

GATE_TAG = re.compile(r"^gate-g(\d+)$", re.I)


def finished_keys(items):
    """{key: label} for what finished: each item's 8-hex id, plus "G<n>" for each gate-g<n> tag it
    carries (a wait is often written "waits for G9", not by id: task df2da0a4's round 0). An item
    whose id is not a Grove UUID is a token from --item (m1384, #575) and is its own key."""
    keys = {}
    for it in items:
        iid = str(it.get("id") or "").strip()
        if not iid:
            continue
        how = it.get("how") or "done"
        title = (it.get("title") or "").strip()
        is_id = bool(ID.fullmatch(iid[:8])) and (len(iid) == 8 or iid[8:9] == "-")
        key = iid[:8].lower() if is_id else iid
        label = f"{key} {how}" + (f" ({title[:60]})" if title else "")
        keys[key] = label
        for t in it.get("tags") or []:
            m = GATE_TAG.fullmatch(t)  # fullmatch: `$` alone lets a trailing line break through
            if m:
                keys.setdefault(f"G{m.group(1)}", label)
    return keys


def key_in(key, phrase):
    """A key inside one wait phrase: an id as waits_in reads it (an id marked as over is evidence,
    not a wait), any other key as a whole word ("G9" is not "G90", "#57" is not "#575")."""
    if ID.fullmatch(key):
        return key in waits_in(phrase)
    g = re.fullmatch(r"G(\d+)", key)
    if g:  # "G9", "g9", "gate-g9", "gate 9" (review finding 3)
        return re.search(rf"(?<![\w#])(?:gate[- ]?g?|g){g.group(1)}(?!\w)", phrase, re.I) is not None
    return re.search(r"(?<![\w#])" + re.escape(key) + r"(?!\w)", phrase) is not None


def sentence(line, phrase):
    """The sentence of a line that holds a wait phrase, so the hit shows what was waiting."""
    at = line.find(phrase)
    start = max(line.rfind(". ", 0, at), line.rfind("; ", 0, at), line.rfind("(", 0, at))
    start = 0 if start < 0 else start + 1
    s = line[start:at + len(phrase)].strip(" ;(")
    return s if len(s) <= 160 else "…" + s[-159:]


def freed(keys, issues_text, row_lines, batons, tasks):
    """[{lane, place, key, finished, text}]: every place dispatch reads whose wait phrase names
    something that finished. A finding to put in front of the lane, never proof it is free: the
    phrase can name other waits too, and the lane's session reads it."""
    places = []  # (lane, place, text, whole): `whole` = the text is all wait (a Waits-on cell)
    for line in row_lines:
        m = LANE_LINE.match(line)
        if m:
            places.append((m.group(1), "row line", line, False))
    for lane, text in sorted(batons.items()):
        # a YAML item wraps: join its continuation lines so "waits for\n  G9" reads (finding 9)
        places.append((lane, "baton next", re.sub(r"\n[ \t]+(?!- )", " ", text), False))
    planned = {}
    for lane, entries in lane_rows(issues_text).items():
        for e in entries:
            planned.setdefault(entry_rank(e), []).append(lane)
            if not re.search(r"\bnow\b", e):
                places.append((lane, "ISSUES entry", e, False))
    _, rows = table_rows(issues_text, "The list")
    for r in rows:
        if r and "waits on" in r and not any("~~" in c for c in r.values()):
            for lane in planned.get(entry_rank(r.get("#", "")), ["?"]):  # finding 6
                places.append((lane, f"ISSUES rank {r.get('#', '?')}", r["waits on"], True))
    for t in tasks:
        if t.get("status", "open") != "open":
            continue
        o = owner(t) or "no lane"
        places.append((o, f"task {t['id'][:8]}", (t.get("title") or "") + "\n" + (t.get("notes") or ""), False))
    hits, seen = [], set()
    for lane, place, text, whole in places:
        for line in text.splitlines():
            # a Waits-on cell is a wait at its start, and often history after (rank 2's cell:
            # "197 before m1383"): read it as one phrase from "waits on", not whole
            phrases = wait_phrases("waits on " + line) if whole else wait_phrases(line)
            for ph in phrases:
                for k, label in keys.items():
                    if (lane, place, k) not in seen and key_in(k, ph):
                        seen.add((lane, place, k))
                        hits.append({"lane": lane, "place": place, "key": k, "finished": label,
                                     "text": sentence(line, ph),
                                     # a task's notes are narrative as often as a wait: the record
                                     # only, never a prompt (finding 5)
                                     "prompt": not place.startswith("task ")})
    return hits


def freed_summary(since, items, hits, partial=None):
    head = (f"freed: {len(items)} finished since {since or 'the named items'}; {len(hits)} waiting place(s)"
            + (f"; partial ({partial})" if partial else ""))
    lines = [head]
    for h in sorted(hits, key=lambda h: (h["lane"], h["place"], h["key"])):
        lane = h["lane"] if len(h["lane"]) == 1 else f"({h['lane']})"
        lines.append(f"  {lane} {h['place']}: {h['key']} = {h['finished']}: \"{h['text']}\""
                     + ("" if h.get("prompt", True) else " [record only]"))
    return "\n".join(lines)


def _when(s):
    """An ISO time, Z or offset, as an aware datetime (finding 8: a string compare misorders)."""
    from datetime import datetime, timezone
    d = datetime.fromisoformat(str(s).strip().replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- inputs

def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as e:
        raise InputError(f"{path}: {e}")


def fetch(slug):
    g = _grove()
    try:
        rows = g.list_items("project", slug=slug, limit=1)
        if not rows:
            raise InputError(f"no project {slug}")
        row = g.get("project", rows[0]["id"]).get("next_actions") or []
        tasks = []
        for lst in (slug,) + OTHER_LISTS:
            got = g._request("GET", "/api/tasks", query={"list": lst, "status": "open", "limit": 500})["tasks"]
            if len(got) >= 500:
                raise InputError(f"list {lst} is at the read's cap (500 open tasks)")
            tasks += got
        decisions, off = [], 0
        while off is not None:
            page = g._request("GET", "/api/decisions", query={"limit": 500, "offset": off})
            decisions += page["decisions"]
            off = page.get("next_offset")
    except g.GroveError as e:
        raise InputError(f"Grove read failed: {e}")
    return row, tasks, decisions


def fetch_finished(since):
    """The Grove tasks (cards included) completed or dropped at or after `since`, from the event
    log (newest first, 200 a kind: task_search orders by created_at, so a done-task list would
    miss an old task finished today). Returns (items, partial): partial names what could not be
    read, and the items read so far still count (review finding 7)."""
    try:
        cut = _when(since)
    except ValueError:
        raise InputError(f"--freed-since {since!r} is not an ISO time")
    g = _grove()
    out, ids, partial = [], set(), []
    for kind, how in (("task.completed", "done"), ("task.dropped", "dropped")):
        try:
            ev = g._request("GET", "/api/events", query={"kind": kind, "limit": 200})["events"]
        except g.GroveError as e:
            partial.append(f"{kind} unread: {e}")
            continue
        recent = [e for e in ev if _when(e.get("created_at") or "1970-01-01") >= cut]
        if len(ev) >= 200 and len(recent) == len(ev):
            partial.append(f"over 200 {kind} events since {since}; the oldest are not read")
        for e in recent:
            if e["entity_id"] in ids:
                continue
            ids.add(e["entity_id"])
            try:
                t = g.get("task", e["entity_id"])
            except g.GroveError:
                partial.append(f"task {e['entity_id'][:8]} unread")
                continue
            if t.get("status") == "open":
                continue  # reopened since: not finished
            out.append({"id": t["id"], "title": t.get("title"), "tags": t.get("tags") or [], "how": how})
    return out, "; ".join(partial) or None


def _grove():
    if not os.environ.get("GROVE_TOKEN", "").strip():
        raise InputError("GROVE_TOKEN is not set (Code sessions and routines have it)")
    if not os.path.exists(GROVE_PY):
        raise InputError(f"no grove.py at {GROVE_PY}")
    spec = importlib.util.spec_from_file_location("grove_client", GROVE_PY)
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    return g


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--issues", required=True, help="docs/ISSUES.md (git show origin/main:docs/ISSUES.md)")
    ap.add_argument("--fetch", action="store_true", help="read the row, tasks and decisions with $GROVE_TOKEN")
    ap.add_argument("--slug", default="medicaid-benefits-navigator")
    ap.add_argument("--row", help="tests: JSON list of the row's next_actions")
    ap.add_argument("--tasks", help="tests: JSON list of open tasks (id, status, list, tags, title)")
    ap.add_argument("--decisions", help="tests: JSON list of decisions (id)")
    ap.add_argument("--batons", help="the repo's handoffs/ directory (lane-<x>.yaml)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--report", action="store_true", help="exit 0 even with findings (pre_ready prints, never blocks)")
    ap.add_argument("--freed-since", metavar="ISO",
                    help="also print what finished since this time (the last dispatch record's created_at) "
                         "and every place still waiting on it")
    ap.add_argument("--item", action="append", default=[],
                    help="a finished thing the Grove log does not hold: a batch (m1384), a merged PR (#575), "
                         "or an id his reply names; repeatable")
    ap.add_argument("--finished", help="tests: JSON list of finished items (id, title, tags, how)")
    a = ap.parse_args(argv)
    try:
        with open(a.issues, encoding="utf-8") as fh:
            issues = fh.read()
        if a.fetch:
            row, tasks, decisions = fetch(a.slug)
        else:
            if not (a.row and a.tasks):
                raise InputError("give --fetch, or --row and --tasks")
            row, tasks = load_json(a.row), load_json(a.tasks)
            decisions = load_json(a.decisions) if a.decisions else []
        if not isinstance(row, list) or not all(isinstance(x, str) for x in row):
            raise InputError("the row's next_actions is not a list of lines")
        batons = {}
        if a.batons:
            if not os.path.isdir(a.batons):
                raise InputError(f"no batons directory {a.batons}")
            for name in sorted(os.listdir(a.batons)):
                m = re.fullmatch(r"lane-([a-z])\.yaml", name)
                if m:
                    with open(os.path.join(a.batons, name), encoding="utf-8") as fh:
                        batons[m.group(1).upper()] = baton_next(fh.read())
        cites, closed_not_free = cited(issues, row)
        found = judge(cites, tasks, decisions, row, batons, list_queue(issues))
    except (InputError, OSError) as e:
        print(f"deps: unread ({e})", file=sys.stderr)
        return 0 if a.report else 2  # --report never blocks a close (review finding 10)
    hits = items = partial = None
    if a.freed_since or a.item or a.finished:
        items = []
        try:
            if a.finished:
                items = load_json(a.finished)
            elif a.freed_since:
                items, partial = fetch_finished(a.freed_since)
        except (InputError, OSError) as e:
            partial = str(e)  # the named items still count (finding 7)
        items = items + [{"id": i.strip(), "how": "named"} for i in a.item if i.strip()]
        hits = freed(finished_keys(items), issues, row, batons, tasks)
    if a.json:
        out = {"findings": sorted(found.values(), key=lambda f: (f["kind"], f["id"])),
               "closed_not_free": [{"rank": r, "cell": c} for r, c in closed_not_free]}
        if hits is not None:
            out["freed"] = {"since": a.freed_since, "finished": items, "hits": hits, "partial": partial}
        print(json.dumps(out, indent=1))
    else:
        print(summary(found, closed_not_free))
        if hits is not None:
            print(freed_summary(a.freed_since, items, hits, partial))
    bad = closed_not_free or any(f["kind"] != "ok" for f in found.values())
    return 1 if bad and not a.report else 0


if __name__ == "__main__":
    sys.exit(main())
