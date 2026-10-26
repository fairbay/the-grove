#!/usr/bin/env python3
"""process_gate.py — the gate on process design runs and the ledger read (stdlib; synced with
the chat-archive skill, beside ops_read.py).

Design: fairbay/ops docs/process-governance/DESIGN.md (Grove ed7657bc). Three commands:

  check <DESIGN.md> ...     Lint each design doc's gate block (exit 2 naming every miss). In
                            fairbay/ops every docs/**/DESIGN.md carries a `Gate:` line:
                            `process` (the block below is required), `product`, `legacy`
                            (written before the gate) or `none — <reason>`; no line is a miss.
                            Review-panel and delegate-adversarial run this before round 1 of a
                            process design; unit.yml runs it at landing as the backstop.
  read  --decisions D.json  The counts the gate asks for, from the dumps the weekly ops read
        [--tasks T.json]    takes (project-health "Ops read"): touches per week (asks + refusals
        [--rules FILE ...]  + cards from session records), the share of records that are process
        [--until DATE]      work (on fairbay/ops, or tagged dispatch), rules-file bytes and
        [--days N] [--json] lines (S12), the ledger (Grove tasks tagged `ledger` with a `seen-N`
                            tag) and whether this month's consolidation has been logged
                            (a decision tagged `process-consolidate`).
  consolidate ...           `read` over the calendar month of --until, plus likely duplicate
                            ledger entries and the month's rules-file commits (when the clone
                            has history) — the monthly pass's input.

The gate block (first 40 lines of the doc):

  Gate: process
  Metric: <the count the change moves, by the name the read prints — touches, share,
          bytes, lines, tokens, minutes, dollars, taps, cards, asks, refusals, rounds,
          records, PRs, batches — with today's figure and its source>
  Backtest: <N ≥ 1> past instances read; <what the change would have done to them>
  Defects: <at least one citation: a Grove id, a PR #, a record date>

This is a shape check: it proves the lines exist and carry a number of the right kind,
not that the number is the one the change moves. The reviewer reads the line.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))

HEAD_LINES = 40
FIELD = re.compile(r"^[\s*_`]*(Gate|Metric|Backtest|Defects)[\s*_`]*:[\s*_`]*(.*?)\s*$")
CITATION = re.compile(r"\b[0-9a-f]{8}\b|#\d+|\b20\d\d-\d\d-\d\d\b")
INTEGER = re.compile(r"\d[\d,]*")
METRIC_NAMES = ("touch", "share", "byte", "line", "token", "minute", "dollar", "$", "tap", "card",
                "ask", "refusal", "round", "record", "pr", "batch", "merge", "spend", "cost")
GATE_KINDS = ("process", "product", "legacy", "none")
RECORD_TEXT = re.compile(r"asks (\d+), refusals (\d+), merges (\d+).*?cards (\d+)")
SEEN = re.compile(r"^seen-(\d+)$")
STOP = {"the", "a", "an", "of", "in", "on", "to", "for", "and", "or", "is", "at", "by", "with", "from", "that", "this"}


# ----------------------------------------------------------------------------- check

def gate_fields(text):
    fields = {}
    for line in text.splitlines()[:HEAD_LINES]:
        m = FIELD.match(line)
        if m and m.group(1) not in fields:
            fields[m.group(1)] = m.group(2)
    return fields


def first_int(s):
    m = INTEGER.search(s or "")
    return int(m.group(0).replace(",", "")) if m else None


def check_doc(text, require_gate=True):
    """Misses for a design doc ([] = pass). require_gate: a doc with no Gate: line is a miss
    (every docs/**/DESIGN.md in fairbay/ops); False passes an ungated doc untouched."""
    fields = gate_fields(text)
    gate = fields.get("Gate")
    if gate is None:
        return ["Gate: line missing (process | product | legacy | none — <reason>)"] if require_gate else []
    kind = gate.split()[0].lower().strip("—-–:,.") if gate.strip() else ""
    if kind not in GATE_KINDS:
        return [f"Gate: '{gate}' is not one of {', '.join(GATE_KINDS)}"]
    if kind == "none" and not re.search(r"[—-]\s*\S", gate):
        return ["Gate: none needs a reason after a dash"]
    if kind != "process":
        return []
    misses = []
    metric = fields.get("Metric")
    if metric is None:
        misses.append("Metric: line missing")
    elif metric.lower().startswith("none") or first_int(metric) is None:
        misses.append("Metric: names no count (a change with no number is a ledger note, not a run)")
    elif not any(k in metric.lower() for k in METRIC_NAMES):
        misses.append("Metric: names no count the read prints (touches, share, bytes, lines, tokens, minutes, dollars, taps, cards, asks, refusals, rounds, records, PRs, batches)")
    backtest = fields.get("Backtest")
    if backtest is None:
        misses.append("Backtest: line missing")
    elif not (first_int(backtest) or 0) >= 1:
        misses.append("Backtest: no instance count of 1 or more")
    defects = fields.get("Defects")
    if defects is None:
        misses.append("Defects: line missing")
    elif not CITATION.search(defects):
        misses.append("Defects: no citation (a Grove id, a PR #, or a date)")
    return misses


def cmd_check(args):
    rc = 0
    for path in args.paths:
        with open(path, encoding="utf-8") as f:
            misses = check_doc(f.read(), require_gate=not args.opt_in)
        if misses:
            rc = 2
            print(f"{path}: gate FAIL")
            for m in misses:
                print(f"  - {m}")
        else:
            print(f"{path}: gate ok")
    return rc


# ----------------------------------------------------------------------------- read

def load_json(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for k in ("items", "data", "decisions", "tasks"):
            if isinstance(data.get(k), list):
                return data[k]
    return data if isinstance(data, list) else []


def to_day(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def tags_of(x):
    t = x.get("tags") or []
    return [str(v) for v in t] if isinstance(t, list) else []


def _ops_read():
    try:
        sys.path.insert(0, HERE)
        import ops_read  # noqa: E402
        return ops_read
    except Exception:
        return None


def norm_repo(r, ops_read=None):
    if ops_read:
        return ops_read.norm_repo(r)
    return r.strip() if isinstance(r, str) and r.strip() else None


def session_records(decisions):
    """(date, repo, asks, refusals, cards, tags) per session record, plus the unreadable list.

    With ops_read importable, its parser decides: a record it dropped as superseded is not
    counted again from its text; a record it could not parse for want of a JSON context (a
    compact dump) is read from its own text; anything else unreadable is reported, not
    counted. Without it (a dump read outside a synced repo), the record's own text is parsed."""
    ops_read = _ops_read()
    by_id = {d.get("id"): d for d in decisions if "session-record" in tags_of(d)}
    out, unreadable = [], []
    if ops_read:
        recs, bad = ops_read.parse_records(decisions)
        for b in bad:
            # a compact dump has no context: the record's own text carries the counts
            d = by_id.get(b.get("id")) or {}
            m = RECORD_TEXT.search(d.get("decision") or "")
            day = to_day(d.get("created_at"))
            if str(b.get("reason") or "").startswith("context is not") and m and day and not d.get("superseded_by"):
                out.append((day, norm_repo(d.get("project_ref"), ops_read) or "?", int(m.group(1)), int(m.group(2)),
                            int(m.group(4)), tags_of(d)))
            else:
                unreadable.append({"id": b.get("id"), "reason": b.get("reason")})
        for r in recs:
            d = by_id.get(r["id"]) or {}
            ctx = d.get("context")
            if isinstance(ctx, str):
                try:
                    ctx = json.loads(ctx)
                except ValueError:
                    ctx = {}
            cards = None
            if isinstance(ctx, dict) and isinstance(ctx.get("cards"), list):
                cards = len(ctx["cards"])
            if cards is None:
                m = RECORD_TEXT.search(d.get("decision") or "")
                cards = int(m.group(4)) if m else 0
            out.append((r["date"], r["repo"], r["asks"] or 0, r["refusals"] or 0, cards, tags_of(d)))
        return out, unreadable
    for d in by_id.values():
        if d.get("superseded_by"):
            continue
        m = RECORD_TEXT.search(d.get("decision") or "")
        day = to_day(d.get("created_at"))
        if not m or not day:
            unreadable.append({"id": d.get("id"), "reason": "no asks/refusals/cards in the text"})
            continue
        out.append((day, norm_repo(d.get("project_ref")) or "?", int(m.group(1)), int(m.group(2)), int(m.group(4)), tags_of(d)))
    return out, unreadable


def is_process(rec):
    repo, tags = rec[1], rec[5]
    return (repo or "").endswith("/ops") or repo == "ops" or "dispatch" in tags


def default_rules():
    """The rules file where this copy runs: global-CLAUDE.md at the root in fairbay/ops (the
    source; its own .claude/global.md is a stub), else the synced .claude/global.md."""
    root = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
    for cand in (os.path.join(root, "global-CLAUDE.md"), os.path.join(root, ".claude", "global.md")):
        if os.path.isfile(cand):
            return [cand]
    return []


def rules_stats(paths):
    out = []
    for p in paths:
        if not os.path.isfile(p):
            out.append({"file": p, "bytes": None, "lines": None, "missing": True})
            continue
        with open(p, "rb") as f:
            data = f.read()
        out.append({"file": os.path.basename(p), "bytes": len(data), "lines": data.count(b"\n")})
    return out


def rule_commits(paths, since):
    out = []
    for p in paths:
        d = os.path.dirname(os.path.abspath(p))
        try:
            r = subprocess.run(["git", "-C", d, "log", f"--since={since}", "--format=%ad %h %s", "--date=short",
                                "--", os.path.basename(p)], capture_output=True, text=True, timeout=20)
            s = subprocess.run(["git", "-C", d, "rev-parse", "--is-shallow-repository"],
                               capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode == 0:
            out.append({"file": os.path.basename(p), "commits": [l for l in r.stdout.splitlines() if l.strip()],
                        "shallow": s.stdout.strip() == "true"})
    return out


def ledger(tasks):
    """Open Grove tasks tagged `ledger` that carry a seen-N tag, by seen-N. A task tagged
    `process` alone is not a ledger entry (the tag was in use before the ledger)."""
    rows = []
    for t in tasks:
        tags = tags_of(t)
        if "ledger" not in tags or (t.get("status") or "open") != "open":
            continue
        seen = max((int(m.group(1)) for g in tags for m in [SEEN.match(g)] if m), default=None)
        if seen is None:
            continue
        rows.append({"id": str(t.get("id") or "?")[:8], "seen": seen, "title": (t.get("title") or "")[:90],
                     "project_ref": t.get("project_ref")})
    rows.sort(key=lambda r: (-r["seen"], r["title"]))
    return rows


def words(title):
    return {w for w in re.findall(r"[a-z0-9]+", (title or "").lower()) if w not in STOP and len(w) > 2}


def likely_duplicates(rows, overlap=3):
    pairs = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if a["project_ref"] == b["project_ref"] and len(words(a["title"]) & words(b["title"])) >= overlap:
                pairs.append(tuple(sorted((a["id"], b["id"]))))
    return pairs


def consolidated_this_month(decisions, until):
    for d in decisions:
        if "process-consolidate" in tags_of(d):
            day = to_day(d.get("created_at"))
            if day and day.year == until.year and day.month == until.month:
                return True
    return False


def build(decisions, tasks, rules, until, days):
    since = until - timedelta(days=days - 1)
    recs, unreadable = session_records(decisions)
    recs = [r for r in recs if since <= r[0] <= until]
    weeks = max(days / 7.0, 1e-9)
    touches = sum(r[2] + r[3] + r[4] for r in recs)
    by_repo = {}
    for r in recs:
        by_repo[r[1]] = by_repo.get(r[1], 0) + 1
    proc = sum(1 for r in recs if is_process(r))
    led = ledger(tasks)
    return {
        "window": {"since": since.isoformat(), "until": until.isoformat(), "days": days},
        "records": len(recs),
        "unreadable": unreadable,
        "touches": {"asks": sum(r[2] for r in recs), "refusals": sum(r[3] for r in recs),
                    "cards": sum(r[4] for r in recs), "total": touches, "per_week": round(touches / weeks, 1)},
        "process_share": {"process_records": proc, "all_records": len(recs),
                          "fraction": round(proc / len(recs), 2) if recs else None},
        "records_by_repo": by_repo,
        "rules": rules_stats(rules),
        "ledger": led,
        "ledger_earned": [r for r in led if r["seen"] >= 2],
        "consolidated_this_month": consolidated_this_month(decisions, until),
    }


def render(res, commits=None):
    w, t, ps = res["window"], res["touches"], res["process_share"]
    lines = [f"Process gate read, {w['since']} to {w['until']} ({w['days']} days), {res['records']} session records"
             + (f", {len(res['unreadable'])} unreadable" if res["unreadable"] else ""),
             f"- Touches: {t['total']} ({t['asks']} asks, {t['refusals']} refusals, {t['cards']} cards) = {t['per_week']} per week",
             f"- Process share: {ps['process_records']} of {ps['all_records']} records on fairbay/ops or tagged dispatch"
             + (f" ({int(ps['fraction'] * 100)}%)" if ps["fraction"] is not None else "")]
    for u in res["unreadable"]:
        lines.append(f"    unreadable record {str(u.get('id'))[:8]}: {u.get('reason')}")
    for r in res["rules"]:
        lines.append(f"- Rules file {r['file']}: " + ("missing" if r.get("missing") else f"{r['bytes']:,} bytes, {r['lines']} lines (S12)"))
    if res["ledger"]:
        lines.append(f"- Ledger: {len(res['ledger'])} open entries, {len(res['ledger_earned'])} at seen-2 or more (earned encoding)")
        lines.extend(f"    seen-{r['seen']} {r['id']} {r['title']}" for r in res["ledger"])
    else:
        lines.append("- Ledger: no open entries (tasks tagged ledger with a seen-N tag)")
    lines.append("- Consolidation this month: " + ("logged" if res["consolidated_this_month"]
                                                   else "not logged (run `consolidate`, then log a decision tagged process-consolidate)"))
    for p in res.get("duplicates") or []:
        lines.append(f"    likely duplicate ledger entries: {p[0]} and {p[1]} (merge, keep the higher seen-N)")
    for c in commits or []:
        lines.append(f"- {c['file']}: {len(c['commits'])} commits in the window"
                     + (" (shallow clone: history cut; `gh api repos/fairbay/ops/commits?path=…` for the rest)" if c.get("shallow") else ""))
        lines.extend(f"    {l}" for l in c["commits"][:30])
    return "\n".join(lines)


def cmd_read(args, consolidate=False):
    decisions = load_json(args.decisions) if args.decisions else []
    tasks = load_json(args.tasks) if args.tasks else []
    until = date.fromisoformat(args.until) if args.until else datetime.now(timezone.utc).date()
    rules = args.rules if args.rules is not None else default_rules()
    days = args.days
    if consolidate and days is None:
        days = until.day  # the calendar month to date
    res = build(decisions, tasks, rules, until, days or 7)
    commits = None
    if consolidate:
        res["duplicates"] = likely_duplicates(res["ledger"])
        commits = rule_commits(rules, res["window"]["since"])
        res["rule_commits"] = commits
    print(json.dumps(res, indent=2, default=str) if args.json else render(res, commits))
    return 0


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("paths", nargs="+")
    c.add_argument("--opt-in", action="store_true", help="a doc with no Gate: line passes (outside fairbay/ops)")
    for name in ("read", "consolidate"):
        r = sub.add_parser(name)
        r.add_argument("--decisions")
        r.add_argument("--tasks")
        r.add_argument("--rules", nargs="*")
        r.add_argument("--until")
        r.add_argument("--days", type=int, default=None)
        r.add_argument("--json", action="store_true")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.cmd == "check":
        return cmd_check(args)
    return cmd_read(args, consolidate=(args.cmd == "consolidate"))


if __name__ == "__main__":
    sys.exit(main())
