#!/usr/bin/env python3
"""Next from the list: per lane, the highest rank in MBN docs/ISSUES.md that waits on nothing.

Dispatch (session-start references/dispatch.md, Step 1 read 7) prints this beside each lane's
START HERE line (Grove f21b91ed step 1's last line; Baylee's "Fine" to the list's order, 396d026e).
The file is the repo's docs/ISSUES.md as `git show origin/main:docs/ISSUES.md` wrote it.

  issues_next.py ISSUES.md [--lane X ...] [--rank N ...] [--json]

Reads two tables: "## The list" (rank, tier, what a visitor hits, ..., Waits on, Folds) and
"## How lanes pull from it" (lane, ranks in order). A lane's next is the first entry of its row
whose ranks all have "—" in the Waits-on cell and whose own text carries no "after", "once" or
"when" ("26 (after its card)" waits; "11 (m1360)" does not). An entry marked "now" ("11 (m1360,
now)") is free whatever its Waits-on cell says: the lane split out the free part of a waiting
rank. A struck row (~~ in any cell, or a Count cell starting "struck") is skipped. An entry such
as "22 with 4 (the cards)" names two ranks; both must be free. `--rank N` prints whether rank N
is free or what it waits on (a START HERE that names a rank other than the pick).

Exit 0; 2 when the file or a table cannot be read. A list row the parser drops (a different column
count) is named on stderr and counts as unreadable, never as free. Python 3.11, stdlib only.
"""
import argparse
import json
import re
import sys

WAIT_WORDS = re.compile(r"\b(after|once|when)\b", re.I)
NOW_WORD = re.compile(r"\bnow\b", re.I)
NUM = re.compile(r"\d+")
LANE = re.compile(r"[A-Z][A-Z0-9]*")


class InputError(Exception):
    pass


def cells(line):
    """The cells of one markdown table row, trimmed; None when the line is not a row."""
    s = line.strip()
    if not s.startswith("|"):
        return None
    parts = s.strip("|").split("|")
    return [p.strip() for p in parts]


def is_rule(c):
    return all(set(x) <= set(":- ") for x in c)


def section(text, heading):
    """The lines under `## <heading>` up to the next `## `."""
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().lower() == f"## {heading}".lower():
            start = i + 1
            break
    if start is None:
        raise InputError(f"no section '## {heading}'")
    out = []
    for ln in lines[start:]:
        if ln.startswith("## "):
            break
        out.append(ln)
    return out


def parse_issues(text):
    """(rank -> {what, waits, free, struck}, dropped row numbers) from the list table."""
    rows, dropped = {}, []
    header = None
    for ln in section(text, "The list"):
        c = cells(ln)
        if c is None:
            continue
        if header is None:
            header = [h.lower() for h in c]
            continue
        if is_rule(c):
            continue
        if len(c) != len(header):
            m = NUM.search(c[0]) if c else None
            dropped.append(int(m.group()) if m else None)
            continue
        row = dict(zip(header, c))
        m = NUM.search(row.get("#", ""))
        if not m:
            continue
        waits = row.get("waits on", "").strip()
        struck = any("~~" in v for v in c) or row.get("count (reach first)", row.get("count", "")).lower().startswith("struck")
        rows[int(m.group())] = {
            "what": row.get("what a visitor hits", "").strip("~ "),
            "waits": "" if waits in ("—", "-", "") else waits,
            "free": waits in ("—", "-", ""),
            "struck": struck,
        }
    if header is None or "waits on" not in header:
        raise InputError("the list table has no 'Waits on' column (is the header '| # | Tier | … | Waits on | Folds |'?)")
    if not rows:
        raise InputError("the list table has no rank rows")
    return rows, dropped


def split_entries(s):
    """Split a lane row on commas outside parentheses."""
    out, buf, depth = [], [], 0
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        out.append("".join(buf).strip())
    return [e for e in out if e]


def parse_lanes(text):
    """lane -> list of entries, each {text, ranks}."""
    lanes = {}
    header = None
    for ln in section(text, "How lanes pull from it"):
        c = cells(ln)
        if c is None:
            continue
        if header is None:
            header = c
            continue
        if is_rule(c) or len(c) < 2:
            continue
        lane = c[0].strip("*`_ ").upper()
        if not LANE.fullmatch(lane):
            continue
        entries = []
        for e in split_entries(c[1]):
            head = e.partition("(")[0]
            ranks = [int(x) for x in NUM.findall(head)]
            if ranks:
                entries.append({"text": e, "ranks": ranks})
        lanes[lane] = entries
    if not lanes:
        raise InputError("the lanes table has no lane rows")
    return lanes


def rank_reasons(rank, issues, dropped):
    row = issues.get(rank)
    if row is None:
        return [f"rank {rank}'s row could not be read" if rank in dropped else f"rank {rank} is not in the list"]
    if row["struck"]:
        return [f"rank {rank} is struck"]
    if not row["free"]:
        return [f"rank {rank} waits on {row['waits']}"]
    return []


def entry_reasons(e, issues, dropped):
    """Why an entry waits; [] when it is free. 'now' in the entry overrides a Waits-on cell, not a missing or struck row."""
    reasons = []
    if WAIT_WORDS.search(e["text"]):
        reasons.append(f"its entry says '{e['text']}'")
    now = bool(NOW_WORD.search(e["text"]))
    for r in e["ranks"]:
        for why in rank_reasons(r, issues, dropped):
            if now and " waits on " in why:
                continue
            reasons.append(why)
    return reasons


def next_for(entries, issues, dropped):
    """The first entry that waits on nothing; the skipped entries with their reasons."""
    skipped = []
    for e in entries:
        reasons = entry_reasons(e, issues, dropped)
        if reasons:
            skipped.append({"entry": e["text"], "why": "; ".join(reasons)})
            continue
        first = issues[e["ranks"][0]]
        return {"rank": e["ranks"][0], "ranks": e["ranks"], "entry": e["text"], "what": first["what"]}, skipped
    return None, skipped


def compute(text, lanes_wanted=None, ranks_wanted=None):
    issues, dropped = parse_issues(text)
    lanes = parse_lanes(text)
    out = {}
    for lane in sorted(lanes):
        if lanes_wanted and lane not in lanes_wanted:
            continue
        nxt, skipped = next_for(lanes[lane], issues, dropped)
        out[lane] = {"next": nxt, "skipped": skipped}
    for lane in lanes_wanted or []:
        out.setdefault(lane, {"next": None, "skipped": [], "not_on_list": True})
    res = {"lanes": out, "dropped": [d for d in dropped if d is not None], "dropped_rows": len(dropped)}
    if ranks_wanted:
        res["ranks"] = {}
        for r in ranks_wanted:
            why = rank_reasons(r, issues, dropped)
            res["ranks"][r] = {"free": not why, "why": "; ".join(why), "what": (issues.get(r) or {}).get("what", "")}
    return res


def render(res):
    L = []
    for lane, e in res["lanes"].items():
        if e.get("not_on_list"):
            L.append(f"{lane}: not on the list (no row in 'How lanes pull from it')")
            continue
        n = e["next"]
        if n:
            L.append(f"{lane}: rank {n['rank']} ({n['what'][:90]})" + (f" [{n['entry']}]" if n["entry"] != str(n["rank"]) else ""))
        else:
            L.append(f"{lane}: none free (every rank in its row waits)")
        for s in e["skipped"]:
            L.append(f"  skipped {s['entry']}: {s['why']}")
    for r, v in (res.get("ranks") or {}).items():
        L.append(f"rank {r}: " + ("free" if v["free"] else v["why"]) + (f" ({v['what'][:60]})" if v["what"] else ""))
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path", help="docs/ISSUES.md as written by git show origin/main:docs/ISSUES.md")
    ap.add_argument("--lane", action="append", default=[], help="only these lanes; a lane not in the table prints 'not on the list'")
    ap.add_argument("--rank", action="append", type=int, default=[], help="also say whether this rank is free or what it waits on")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        try:
            text = open(a.path, encoding="utf-8").read()
        except OSError as e:
            raise InputError(f"cannot read {a.path}: {e.strerror or e}")
        res = compute(text, [x.upper() for x in a.lane] or None, a.rank or None)
    except InputError as e:
        print(f"issues_next.py: {e}", file=sys.stderr)
        return 2
    if res["dropped_rows"]:
        print(f"issues_next.py: {res['dropped_rows']} list row(s) unreadable (column count differs from the header): "
              + ", ".join(str(d) for d in res["dropped"]) if res["dropped"] else
              f"issues_next.py: {res['dropped_rows']} list row(s) unreadable (column count differs from the header)", file=sys.stderr)
    print(json.dumps(res, indent=1) if a.json else render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
