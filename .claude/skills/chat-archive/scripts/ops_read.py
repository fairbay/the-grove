#!/usr/bin/env python3
"""Weekly ops read of decision routing (docs/decision-routing/DESIGN.md section 5, channel 2).

A pure, offline computation over JSON dumps that a session gathers from Grove (MCP) and
GitHub. It prints signals S1, S2, S4, S5 against the thresholds in each repo's
.claude/policy.json, the activity that has no session record, the newest sync.yml /
rules.yml conclusions, and a list of actions for the session to file. It never calls Grove
or GitHub, and it hard-codes no threshold: every number comes from the policy's `signals`
block, and a missing key is reported as "not judged: <repo> policy lacks signals.<key>.<field>".

Usage:
  python3 ops_read.py --decisions FILE [--cards FILE] [--activity FILE] [--runs FILE]
      --policy REPO=PATH [--policy REPO=PATH ...] [--default-policy PATH]
      [--minutes FILE] [--gaps FILE] [--until YYYY-MM-DD] [--days 7] [--json]

--minutes FILE: JSON array of {repo, date, minutes}, one row per Actions run in the billing month
(minutes = the run's duration rounded up to whole minutes). It feeds S11, the account-wide Actions
minutes line; S10 (cache-read tokens per day) reads the optional `cache_read_m` of the records.
The Budgets section also prints a report-only "Counter" line from record-2 fields (session_report.py
--record): whole records, interrupts, starts, PR taps and the process share of cache-read; then a
"Dispatch prompts" line (the week's printed prompts, how many were pasted unchanged by opening_hash,
and the strict count of docs/dispatch/DESIGN.md §1.2) and a "Lane overlaps" line (a lane's session that
logged again after another session of the lane), both report-only.

--gaps FILE: JSON array of the open Grove tasks tagged guide-gap (ops_gather.py writes gaps.json). It feeds
the report-only "Guide gaps" line: how many are open and the administrator-guide pages they name (MBN
docs/admin-guide maintain/freshness-and-the-routine.md, "The counter"). Without it the line says "not read".

Exit 0 normally; 2 on an input error (unreadable file, bad JSON, --policy without '=').
Python 3.11, stdlib only.
"""
import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction

K_S1 = "S1_policy_asks_per_upkeep_session"
K_S2 = "S2_harness_refusals_per_session"
K_S4 = "S4_reversals_over_calls_shown"
K_S5 = "S5_wrong_question_cards"
K_S10 = "S10_cache_read_tokens_per_day"
K_S11 = "S11_actions_minutes_month"
BUDGET_REPO = "fairbay/ops"  # the two budget lines are account-wide; their thresholds live in ops's policy
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
ROW_RE = re.compile(r"^table-row-(\d+)$")
WRAP_KEYS = ("decisions", "tasks", "items", "results", "data", "workflow_runs")
HASH_RE = re.compile(r"[0-9a-f]{8}")  # session_report.py text_hash
SESSION_RE = re.compile(r"session_[A-Za-z0-9]+")
LANE_TAG = re.compile(r"lane-[a-z][0-9]?", re.I)  # a lane id (a, a2), not a word such as lane-sweep
GAP_TAG = "guide-gap"  # a task naming a page the MBN administrator guide lacks or must fix
GAP_LIMIT = 100  # ops_gather.py reads at most this many (its GAP_LIMIT); a full file is printed as "at least"
GAP_PAGE_LINE = re.compile(r"^[ \t]*(?:[-*>][ \t]*)?page:[ \t]*(\S.*?)[ \t]*$", re.I | re.M)  # `page: <slug or plain name>`, bullet allowed
GUIDE_SECTIONS = "start|system|how-to|launch|maintain"  # docs/admin-guide/src/content/docs/<section>/<slug>.md
GUIDE_PREFIX = "docs/admin-guide/src/content/docs/"
GUIDE_SLUG = r"((?:" + GUIDE_SECTIONS + r")/[a-z0-9][a-z0-9-]*)"
# a guide path in prose: the full prefix (also inside a GitHub URL), or a bare <section>/<slug> only with its .md, so that
# prose such as "start/stop" or "the system/design question" is not read as a page
GUIDE_PAGE = re.compile(r"(?:" + re.escape(GUIDE_PREFIX) + GUIDE_SLUG + r"(?:\.mdx?)?|(?<![\w/-])" + GUIDE_SLUG + r"\.mdx?)(?![\w-])")


class InputError(Exception):
    pass


# ---------------------------------------------------------------- input helpers

SYNC_PREFIX = "sync "  # scripts/sync.py SYNC_COMMIT_PREFIX

def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError as e:
        raise InputError(f"cannot read {path}: {e.strerror or e}")
    except ValueError as e:
        raise InputError(f"bad JSON in {path}: {e}")


def load_list(path):
    data = load_json(path)
    if isinstance(data, dict):
        for k in WRAP_KEYS:
            if isinstance(data.get(k), list):
                data = data[k]
                break
    if not isinstance(data, list):
        raise InputError(f"{path}: expected a JSON array")
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise InputError(f"{path}: item {i} is not an object")
    return data


def to_dt(s):
    if not isinstance(s, str):
        return None
    try:
        dt = datetime.fromisoformat(s.strip())
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def day_of(s):
    dt = to_dt(s)
    return dt.date() if dt else None


def parse_day(s):
    if isinstance(s, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None
    return None


def load_minutes(path):
    rows = []
    for i, m in enumerate(load_list(path)):
        n = m.get("minutes")
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise InputError(f"{path}: row {i} minutes is not a non-negative integer")
        rows.append({"repo": norm_repo(m.get("repo")) or "?", "date": parse_day(m.get("date")), "minutes": n})
    return rows


def tags_of(x):
    t = x.get("tags")
    if isinstance(t, str):
        return [p.strip() for p in t.split(",") if p.strip()]
    return [str(p) for p in t] if isinstance(t, list) else []


def norm_repo(r):
    if not isinstance(r, str) or not r.strip():
        return None
    r = r.strip()
    if "/" in r or UUID_RE.match(r):
        return r
    return "fairbay/" + r


def same_id(a, b):
    """Full ids match exactly; an 8+ character prefix of the other also matches."""
    if not a or not b:
        return False
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    return len(short) >= 8 and long_.startswith(short)


def short(x):
    x = str(x)
    return x[:8] if (len(x) >= 32 and re.fullmatch(r"[0-9a-f-]+", x)) else x


# ---------------------------------------------------------------- records

def parse_records(decisions, keep_restated=False):
    """Session records. keep_restated: also return the records a later record superseded, marked restated (the lane-overlap
    line needs every time a session logged; every count reads only the records that are not restated)."""
    records, unreadable = [], []
    for d in decisions:
        if "session-record" not in tags_of(d):
            continue
        # a record restated by a later record (supersedes) counts once: the newer one
        restated = bool(d.get("superseded_by") or any(same_id(str(o.get("supersedes") or ""), str(d.get("id"))) for o in decisions
                                                      if "session-record" in tags_of(o) and o.get("supersedes")))
        if restated and not keep_restated:
            continue
        did = d.get("id")
        title = d.get("decision") or ""

        def bad(reason):
            if not restated:  # a restated record's newer copy is the one judged
                unreadable.append({"kind": "record", "id": did, "title": title, "reason": reason,
                                   "created": (d.get("created_at") or "")[:10]})

        raw = d.get("context")
        if isinstance(raw, dict):
            ctx = raw
        else:
            try:
                ctx = json.loads(raw) if isinstance(raw, str) and raw.strip() else None
            except ValueError as e:
                bad(f"context is not JSON ({e.__class__.__name__})")
                continue
        if not isinstance(ctx, dict):
            bad("context is not a JSON object")
            continue
        created = to_dt(d.get("created_at"))
        rdate = parse_day(ctx.get("date")) or (created.date() if created else None)
        if rdate is None:
            bad("no date")
            continue
        repo = norm_repo(ctx.get("repo")) or norm_repo(d.get("project_ref"))
        if repo is None:
            bad("no repo")
            continue
        counts = {}
        ok = True
        for f in ("asks", "refusals", "merges"):
            v = ctx.get(f)
            if v is not None and (isinstance(v, bool) or not isinstance(v, int)):
                bad(f"{f} is not an integer or null")
                ok = False
                break
            counts[f] = v
        if not ok:
            continue
        cache = ctx.get("cache_read_m")
        if cache is not None and (not isinstance(cache, dict) or any(not is_num(v) or v < 0 for v in cache.values())):
            bad("cache_read_m is not a model -> millions object or null")
            continue
        shown = ctx.get("calls_shown") or []
        if not isinstance(shown, list):
            bad("calls_shown is not a list")
            continue
        refused = ctx.get("refused") or []
        if not isinstance(refused, list):
            bad("refused is not a list")
            continue
        prs = ctx.get("prs") or []
        if not isinstance(prs, list):
            bad("prs is not a list")
            continue
        records.append({
            "id": did, "session": str(ctx.get("session") or did or "?"), "date": rdate,
            "created": created or datetime.min.replace(tzinfo=timezone.utc),
            "repo": repo, "kind": ctx.get("kind") or "upkeep", "source": ctx.get("source"),
            "asks": counts["asks"], "refusals": counts["refusals"],
            "refused": [str(x) for x in refused], "calls_shown": [str(x) for x in shown],
            "cache_read_m": cache,
            # record 2 (session_report.py --record, 75cbc21d): the whole counter; absent on older records
            "version": ctx.get("record") if isinstance(ctx.get("record"), int) and not isinstance(ctx.get("record"), bool) else 1,
            "lane": str(ctx["lane"]).lower() if ctx.get("lane") else None,
            "start": ctx.get("start") if ctx.get("start") in ("pasted", "typed", "none") else None,
            "prs": [x for x in prs if isinstance(x, dict)],
            "cards": len(ctx.get("cards") or []) if isinstance(ctx.get("cards"), list) else 0,
            "interrupts": ctx.get("interrupts") if isinstance(ctx.get("interrupts"), int) and not isinstance(ctx.get("interrupts"), bool) else None,
            # dispatch counter (5b925af6; docs/dispatch/DESIGN.md §4.3): the opening's hash, the session id, the printed block
            "opening_hash": ctx.get("opening_hash") if isinstance(ctx.get("opening_hash"), str) and HASH_RE.fullmatch(ctx["opening_hash"]) else None,
            "sid": session_id(ctx.get("session")) or f"record:{did or len(records)}", "restated": restated,
            "dispatch": dispatch_prompts(ctx.get("dispatch"), created or datetime.min.replace(tzinfo=timezone.utc)) if ("dispatch" in tags_of(d) or isinstance(ctx.get("dispatch"), dict)) else None,
        })
        if not records[-1]["lane"]:  # a record 1 may carry its lane only as a lane-<x> tag
            records[-1]["lane"] = next((t[5:].lower() for t in tags_of(d) if LANE_TAG.fullmatch(t)), None)
    return records, unreadable


def session_id(s):
    """The session_… id inside a session URL or id; None when the field names none (a chat label, a record 1 without one)."""
    m = SESSION_RE.search(str(s or ""))
    return m.group(0) if m else None


def dispatch_prompts(block, created):
    """What a dispatch record printed, read tolerantly (session_report.py --dispatch writes the checked form; the 10-28 record
    was written by hand). Returns {"printed": [{lane, hash, at}], "known": bool}: printed = the lanes whose state is ready
    (a prompted lane's prompt is carried under Running, not printed again), or every prompt lane when the block has no
    states; hash None when the block carries no text; known False for a dispatch record with no prompt list (record 1).
    at is the record's time: the run printed it then (a reprint's `first` names the earlier print)."""
    if not isinstance(block, dict) or not isinstance(block.get("prompts"), (dict, list)):
        return {"printed": [], "known": False}
    prompts, states = block["prompts"], block.get("lanes") if isinstance(block.get("lanes"), dict) else None
    items = prompts.items() if isinstance(prompts, dict) else ((str(x), None) for x in prompts)
    printed = []
    for lane, p in items:
        lane = str(lane).lower()
        if states is not None and states.get(lane) != "ready":
            continue
        h = p.get("hash") if isinstance(p, dict) else None
        printed.append({"lane": lane, "hash": h if isinstance(h, str) and HASH_RE.fullmatch(h) else None, "at": created})
    return {"printed": printed, "known": True}


def sortkey(r):
    return (r["date"], r["created"])


def reversal_targets(decisions):
    """Ids of calls that a decision tagged `reversal` reverses."""
    out = []
    for r in decisions:
        if "reversal" not in tags_of(r):
            continue
        sup = r.get("supersedes")
        if sup:
            out.append(str(sup))
        for d in decisions:
            if d.get("superseded_by") and same_id(str(d["superseded_by"]), str(r.get("id"))) and d.get("id"):
                out.append(str(d["id"]))
    return out


# ---------------------------------------------------------------- policy

def read_policy(path):
    pol = load_json(path)
    if not isinstance(pol, dict):
        raise InputError(f"{path}: policy is not a JSON object")
    return pol


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def thresholds(pol, repo, key, fields):
    """Return (values, reasons). A reason is a loud 'not judged' sentence."""
    sigs = pol.get("signals")
    sig = sigs.get(key) if isinstance(sigs, dict) else None
    vals, reasons = {}, []
    for f, kind in fields:
        if not isinstance(sig, dict) or f not in sig:
            reasons.append(f"not judged: {repo} policy lacks signals.{key}.{f}")
        elif kind == "num" and not is_num(sig[f]):
            reasons.append(f"not judged: {repo} policy has non-numeric signals.{key}.{f}")
        elif kind == "count" and (isinstance(sig[f], bool) or not isinstance(sig[f], int) or sig[f] < 1):
            reasons.append(f"not judged: {repo} policy has signals.{key}.{f} that is not a positive integer")
        else:
            vals[f] = sig[f]
    return vals, reasons


def not_judged(reasons):
    return {"status": "not_judged", "reason": "; ".join(reasons), "line": "not judged: " + "; ".join(r.replace("not judged: ", "") for r in reasons)}


def fmt_num(v):
    return f"{v:g}" if isinstance(v, float) else str(v)


# ---------------------------------------------------------------- signals

def signal_s1(repo, pol, recs, until, actions):
    vals, bad = thresholds(pol, repo, K_S1, [("max", "num"), ("window_sessions", "count")])
    if bad:
        return not_judged(bad)
    mx, n = vals["max"], vals["window_sessions"]
    upkeep = [r for r in recs if r["kind"] != "direction" and r["date"] <= until and r["asks"] is not None]
    window = sorted(upkeep, key=sortkey)[-n:]
    sessions = [{"session": r["session"], "date": r["date"].isoformat(), "asks": r["asks"]} for r in window]
    breaching = [r for r in window if r["asks"] > mx]
    res = {"status": "breach" if breaching else "ok", "max": mx, "window_sessions": n,
           "sessions": sessions, "breaching": [r["session"] for r in breaching]}
    if window:
        listing = "asks " + ", ".join(f"{s['asks']}" for s in sessions) + " (oldest to newest)"
    else:
        listing = "no upkeep sessions with counts"
    line = f"S1 policy asks per upkeep session (trailing {n}, max {fmt_num(mx)}): {listing} -> {res['status']}"
    if breaching:
        line += "; over: " + ", ".join(f"{r['session']} ({r['asks']})" for r in breaching)
        newest = max(breaching, key=sortkey)
        body = "Upkeep sessions in the trailing window (asks per session):\n" + "\n".join(
            f"- {s['date']} {s['session']}: asks {s['asks']}" + (" (over)" if s["asks"] > mx else "") for s in sessions
        ) + "\n\nName the edge that produced the asks. Cap: one design round per edge; after that the edge is a ruling for Baylee."
        actions.append({"type": "task", "signal": "S1", "repo": repo,
                        "dedup_key": f"routing-breach S1 {repo} {newest['session']}",
                        "title": f"S1 {repo}: policy asks above {fmt_num(mx)} in an upkeep session (newest {newest['date'].isoformat()})",
                        "body": body})
    res["line"] = line
    return res


def signal_s2(repo, pol, week_recs, actions):
    vals, bad = thresholds(pol, repo, K_S2, [("max", "num")])
    if bad:
        return not_judged(bad)
    mx = vals["max"]
    report_only = (pol["signals"][K_S2] or {}).get("report_only")
    over = [r for r in week_recs if r["refusals"] is not None and r["refusals"] > mx]
    res = {"status": "breach" if over else "ok", "max": mx, "report_only": report_only,
           "records": [{"session": r["session"], "date": r["date"].isoformat(), "refusals": r["refusals"], "refused": r["refused"]} for r in over]}
    line = f"S2 harness refusals per session this week (max {fmt_num(mx)}{', report-only' if report_only else ''}): {len(over)} over -> {res['status']}"
    if over:
        line += "; " + "; ".join(f"{r['session']} refused {r['refused'] or ['(none listed)']}" for r in over)
    # report-only: the refusal already fell back to the tap; the line and res["records"]
    # list it, and no task is filed (ledger 2e3d7eb2: a weekly pile for a no-action signal)
    for r in ([] if report_only else over):
        cmds = "\n".join(f"- {c}" for c in r["refused"]) or "- (the record lists none)"
        actions.append({"type": "task", "signal": "S2", "repo": repo,
                        "dedup_key": f"routing-breach S2 {repo} {r['session']}",
                        "title": f"S2 {repo}: harness refusal in session {r['session']} ({r['date'].isoformat()})",
                        "body": f"Refused in session {r['session']} ({r['refusals']} refusals):\n{cmds}\n\n"
                                "Widening the Go is Baylee's ruling (direction); this task names the refused action only."})
    res["line"] = line
    return res


def signal_s4(repo, pol, recs, until, targets, actions):
    vals, bad = thresholds(pol, repo, K_S4, [("max", "num"), ("window_calls_shown", "count"), ("min_shown_before_judging", "num")])
    if bad:
        return not_judged(bad)
    mx, n, minshown = vals["max"], vals["window_calls_shown"], vals["min_shown_before_judging"]
    shown = []
    for r in sorted((r for r in recs if r["date"] <= until), key=sortkey, reverse=True):
        for cid in r["calls_shown"]:
            if cid not in shown:
                shown.append(cid)
    shown = shown[:n]
    reversed_ids = [c for c in shown if any(same_id(c, t) for t in targets)]
    res = {"max": mx, "shown": len(shown), "reversed": len(reversed_ids), "reversed_ids": reversed_ids,
           "min_shown_before_judging": minshown, "window_calls_shown": n}
    if len(shown) < minshown:
        res.update(status="not_judged", rate=None, reason=f"not judged ({len(shown)} shown, needs {fmt_num(minshown)})")
        res["line"] = f"S4 reversals over calls shown (newest {n}, max {fmt_num(mx)}): {res['reason']}"
        return res
    rate = len(reversed_ids) / len(shown)
    breach = Fraction(len(reversed_ids), len(shown)) > Fraction(str(mx))
    res.update(status="breach" if breach else "ok", rate=rate)
    res["line"] = (f"S4 reversals over calls shown (newest {n}, max {fmt_num(mx)}): "
                   f"{len(reversed_ids)}/{len(shown)} = {rate:.2f} -> {res['status']}")
    if breach:
        res["line"] += "; reversed: " + ", ".join(short(c) for c in reversed_ids)
        actions.append({"type": "card", "signal": "S4", "repo": repo,
                        "dedup_key": f"routing-card S4 {repo} rev-{short(sorted(reversed_ids)[-1])}-{len(reversed_ids)}",
                        "title": f"S4 {repo}: {len(reversed_ids)} of {len(shown)} shown upkeep calls reversed (limit {fmt_num(mx)})",
                        "body": f"Reversals over calls shown: {len(reversed_ids)}/{len(shown)} = {rate:.2f}, above {fmt_num(mx)}. Reversed calls:\n"
                                + "\n".join(f"- {c}" for c in reversed_ids),
                        "recommendation": "narrow upkeep: move the reversed calls' kind to owner_context"})
    return res


def card_row(card):
    for t in tags_of(card):
        m = ROW_RE.match(t)
        if m:
            return int(m.group(1))
    return "unknown"


def signal_s5(repo, pol, cards, since, until, days, actions):
    """cards: this repo's wrong_question cards and needless_ask decisions (any date)."""
    vals, bad = thresholds(pol, repo, K_S5, [("any", "any")])
    if bad:
        return not_judged(bad)
    sig = pol["signals"][K_S5]
    in_week = [c for c in cards if c["day"] and since < c["day"] <= until]
    res = {"status": "ok", "postmortems": [], "row_counts": {}, "same_row_card": sig.get("same_row_card"), "window_days": sig.get("window_days")}
    lines = []
    for c in sorted(in_week, key=lambda c: (c["day"], str(c["id"]))):
        what = "ask" if c.get("kind") == "ask" else "card"
        how = "answered: no need to ask" if what == "ask" else "resolved by note with no option"
        text = f"postmortem: {what} {short(c['id'])} {c['title']} {how}; decision-table row {c['row']}"
        res["postmortems"].append(text)
        lines.append(text)
        actions.append({"type": "postmortem", "signal": "S5", "repo": repo,
                        "dedup_key": f"routing-postmortem {c['id']}",
                        "title": f"Postmortem: {'needless ask' if what == 'ask' else 'wrong-question card'} {short(c['id'])} {c['title']} (row {c['row']})",
                        "body": text + "\nName the decision-table row that produced it in the next session's plan."})
    if in_week:
        res["status"] = "postmortem"
    wd = sig.get("window_days")
    if sig.get("same_row_card") is None:
        lines.append("same-row card not judged: policy has no S5 same_row_card")
        head = f"S5 wrong-question cards and needless asks this week (any): {len(in_week)} -> {res['status']}"
        res["line"], res["detail"] = head, lines
        return res
    if not (isinstance(wd, int) and not isinstance(wd, bool) and wd >= 1):
        lines.append(f"same-row card not judged: {repo} policy lacks signals.{K_S5}.window_days")
        head = f"S5 wrong-question cards and needless asks this week (any): {len(in_week)} -> {res['status']}"
        res["line"], res["detail"] = head, lines
        return res
    counts = {}
    for c in cards:
        if c["day"] and until - timedelta(days=wd) < c["day"] <= until:
            counts.setdefault(c["row"], []).append(c)
    res["row_counts"] = {str(k): len(v) for k, v in counts.items()}
    per_row = ", ".join(f"row {k}: {len(v)}" for k, v in sorted(counts.items(), key=lambda kv: (kv[0] == "unknown", kv[0] if kv[0] != "unknown" else 0))) or "none"
    scope = f"{wd} days"
    lines.append(f"wrong-question cards and needless asks per decision-table row over {scope}: {per_row}")
    srow = sig.get("same_row_card")
    if srow is None:
        lines.append("same-row card not judged: policy has no S5 same_row_card")
    elif not is_num(srow):
        lines.append(f"same-row card not judged: {repo} policy has non-numeric signals.{K_S5}.same_row_card")
    else:
        for row, cs in sorted(((k, v) for k, v in counts.items() if k != "unknown"), key=lambda kv: kv[0]):
            if len(cs) >= srow:
                res["status"] = "breach"
                lines.append(f"row {row}: {len(cs)} wrong-question cards and needless asks (card at {fmt_num(srow)}) -> breach")
                actions.append({"type": "card", "signal": "S5", "repo": repo,
                                "dedup_key": f"routing-card S5 {repo} row-{row} {short(max(cs, key=lambda c: (c['day'], str(c['id'])))['id'])}",
                                "title": f"S5 {repo}: {len(cs)} wrong-question cards and needless asks on decision-table row {row} in {scope}",
                                "body": f"Wrong-question cards and needless asks, all from decision-table row {row}:\n"
                                        + "\n".join(f"- {short(c['id'])} {c['title']} ({c['day'].isoformat()})" for c in sorted(cs, key=lambda c: c["day"])),
                                "recommendation": f"rewrite decision-table row {row}"})
    head = f"S5 wrong-question cards and needless asks this week (any): {len(in_week)} -> {res['status']}"
    res["line"] = head
    res["detail"] = lines
    return res


# ---------------------------------------------------------------- build

def signal_s10(pol, records, since, until, actions):
    """Cache-read tokens per day across every repo's session records, in millions (account-wide)."""
    days = {}
    week = [r for r in records if since < r["date"] <= until]
    counted = [r for r in week if r["cache_read_m"] is not None]
    for r in counted:
        d = days.setdefault(r["date"].isoformat(), {"total": 0.0, "by_model": {}})
        for model, m in r["cache_read_m"].items():
            d["total"] += m
            d["by_model"][model] = d["by_model"].get(model, 0.0) + m
    observed = "no record carries a cache_read_m" if not counted else "; ".join(
        f"{day} {fmt_num(round(v['total'], 1))}M ({', '.join(f'{m} {fmt_num(round(x, 1))}M' for m, x in sorted(v['by_model'].items()))})"
        for day, v in sorted(days.items()))
    coverage = f"{len(counted)} of {len(week)} records this week carry a cost"
    res = {"days": {d: round(v["total"], 3) for d, v in sorted(days.items())}, "records_with_cost": len(counted), "records": len(week)}
    vals, bad = thresholds(pol, BUDGET_REPO, K_S10, [("max_per_day", "num")]) if pol else ({}, [f"not judged: no {BUDGET_REPO} policy"])
    if bad:
        res.update(status="not_judged", reason="; ".join(bad))
        res["line"] = f"S10 cache-read tokens per day, millions ({coverage}): {observed}. " + not_judged(bad)["line"]
        return res
    mx = vals["max_per_day"]
    over = sorted(d for d, v in res["days"].items() if v > mx)
    res.update(status="breach" if over else "ok", max_per_day=mx, over=over)
    res["line"] = f"S10 cache-read tokens per day, millions (max {fmt_num(mx)}; {coverage}): {observed} -> {res['status']}"
    for d in over:
        actions.append({"type": "task", "signal": "S10", "repo": BUDGET_REPO, "dedup_key": f"budget-breach S10 {d}",
                        "title": f"S10: cache-read tokens {fmt_num(res['days'][d])}M on {d}, above {fmt_num(mx)}M a day",
                        "body": f"Session records dated {d} carry {fmt_num(res['days'][d])}M cache-read tokens against a flag of {fmt_num(mx)}M a day.\n\n"
                                "Name the sessions behind it (batch size, review passes, sub-agents by model). Slowing the plan is Baylee's call."})
    return res


def is_process(r):
    """Process work: an ops session, or lane H (global ops and the tech stack) in a lanes repo."""
    return r["repo"] == BUDGET_REPO or r["lane"] == "h"


def counter_line(records, since, until):
    """The whole counter (75cbc21d build item 1). Report-only: no threshold, no action. Two record sets, each named in the line:
    whole records (record 2, built from the transcript by session_report.py --record) give interrupts, starts and PR taps;
    every record with a cost (record 1 included) gives the process share of cache-read (ops sessions and lane H)."""
    week = [r for r in records if since < r["date"] <= until]
    whole = [r for r in week if r["version"] >= 2 and r["source"] == "transcript" and r["interrupts"] is not None]
    res = {"records": len(week), "whole": len(whole)}
    starts = {k: sum(1 for r in whole if r["start"] == k) for k in ("pasted", "typed", "none")}
    prs = [x for r in whole for x in r["prs"]]
    taps = sum(1 for x in prs if x.get("tapped"))
    res.update(interrupts=sum(r["interrupts"] for r in whole), starts=starts, prs=len(prs), tapped=taps)
    costed = [r for r in week if r["cache_read_m"] is not None]
    total = sum(sum(r["cache_read_m"].values()) for r in costed)
    proc = sum(sum(r["cache_read_m"].values()) for r in costed if is_process(r))
    res["process_share"] = round(proc / total, 3) if total else None
    share = f"{round(100 * proc / total)}% of {fmt_num(round(total, 1))}M over the {len(costed)} records with a cost" if total else "no record carries a cost"
    res["line"] = (f"Counter: {len(whole)} of {len(week)} records whole (built by --record); from those: interrupts {res['interrupts']}, "
                   f"starts pasted {starts['pasted']} / typed {starts['typed']} / none {starts['none']}, "
                   f"PRs {len(prs)} ({taps} tapped by him). Process share of cache-read (ops sessions and lane H): {share}")
    return res


def dispatch_line(every, since, until):
    """Prompts that started a session (5b925af6; docs/dispatch/DESIGN.md §1.2 and §4.3). Report-only. For the week's dispatch
    runs (one session; its turns' records, a restated turn included, are one run): the prompts printed (lanes in state ready, once
    per run), how many distinct, how many were pasted unchanged (a record whose opening_hash equals the prompt's hash, logged
    after its first print; records are logged at a session's end, so no upper bound), and the strict count of §1.2 (a record of
    that lane with start pasted, logged after the print and before the repo's next dispatch run). Lane ids are read without the
    repo: only MBN declares lanes, and its lane H records may name fairbay/ops. `every` includes restated records."""
    disp = sorted((r for r in every if r["dispatch"] is not None), key=lambda r: r["created"])
    week = [r for r in disp if since < r["date"] <= until]
    live = [r for r in every if not r["restated"]]
    lane_recs = [r for r in live if r["lane"] and r["dispatch"] is None]
    runs = {}
    for d in week:
        runs.setdefault(d["sid"], []).append(d)
    unknown = sum(1 for ds in runs.values() if not any(d["dispatch"]["known"] for d in ds))
    prints = {}  # (run, lane, hash) -> the run's first print of it
    for sid, ds in runs.items():
        for d in ds:
            for p in d["dispatch"]["printed"] if d["dispatch"]["known"] else []:
                key = (sid, p["lane"], p["hash"])
                if key not in prints:
                    prints[key] = {**p, "repo": d["repo"]}
    strict, newest, groups = 0, 0, {}
    for (sid, lane, h), p in prints.items():
        nxt = next((o["created"] for o in disp if o["repo"] == p["repo"] and o["sid"] != sid and o["created"] > p["at"]), None)
        newest += nxt is None
        if any(r["lane"] == lane and r["start"] == "pasted" and p["at"] < r["created"] and (nxt is None or r["created"] <= nxt) for r in lane_recs):
            strict += 1
        if h:
            groups.setdefault((lane, h), []).append(p["at"])
    pasted = sum(1 for (lane, h), ats in groups.items() if any(r["opening_hash"] == h and min(ats) < r["created"] for r in live))
    printed, hashed = len(prints), sum(len(a) for a in groups.values())
    res = {"dispatches": len(runs), "no_prompt_list": unknown, "printed": printed, "distinct": len(groups),
           "reprinted": hashed - len(groups), "no_text": printed - hashed, "pasted": pasted, "strict": strict, "newest": newest}
    if not week:
        res["line"] = "Dispatch prompts: no dispatch record this week"
        return res
    res["line"] = (f"Dispatch prompts: {len(runs)} dispatch runs" + (f" ({unknown} with no prompt list)" if unknown else "")
                   + f"; {printed} printed ({len(groups)} distinct, {hashed - len(groups)} reprinted"
                   + (f", {printed - hashed} with no text" if printed - hashed else "") + "); "
                   + f"pasted unchanged {pasted} of {len(groups)} (a record's opening_hash after the first print); "
                   + f"strict {strict} of {printed} (a pasted record of the lane before the next dispatch"
                   + (f"; {newest} printed by the newest run, whose sessions may not have logged yet" if newest else "") + ")")
    return res


def overlap_line(records, since, until):
    """Two sessions of one lane open at once (docs/dispatch/DESIGN.md defect 6), read after the fact: a session logs a record of
    its lane, another session logs one of the same lane, and the first logs again; reported when that return is this week."""
    by_lane = {}
    for r in sorted((r for r in records if r["lane"] and r["dispatch"] is None), key=lambda r: r["created"]):
        by_lane.setdefault(r["lane"], []).append(r)
    found, seen = [], set()
    for lane, rs in sorted(by_lane.items()):
        for i, r in enumerate(rs):
            if not since < r["date"] <= until:
                continue
            j = next((j for j in range(i - 1, -1, -1) if rs[j]["sid"] == r["sid"]), None)
            if j is None:
                continue
            between = [o for o in rs[j + 1:i] if o["sid"] != r["sid"]]
            if not between or (lane, r["sid"]) in seen:
                continue
            seen.add((lane, r["sid"]))
            t = lambda o: o["created"].strftime("%m-%d %H:%M")
            found.append({"lane": lane, "session": r["sid"], "first": t(rs[j]), "again": t(r), "between": [o["sid"] for o in between],
                          "text": f"lane {lane.upper()}: {r['sid']} logged {t(rs[j])} and again {t(r)}, after "
                                  + ", ".join(f"{o['sid']} ({t(o)})" for o in between)})
    res = {"overlaps": found}
    res["line"] = ("Lane overlaps: " + "; ".join(f["text"] for f in found)) if found else "Lane overlaps: none (no lane's session logged again after another session of the lane)"
    return res


def gap_line(gaps):
    """The guide-gap counter (MBN task 9a9911a9 item 4(iii); the guide's maintain/freshness-and-the-routine.md, "The counter").
    Report-only: the open Grove tasks tagged guide-gap and the guide pages they name. A task names a page by notes lines
    `page: <slug or plain name>`, one page a line, a bullet allowed (they win); else by guide paths in its title or notes (the
    full docs/admin-guide/src/content/docs/ prefix, a GitHub URL included, or a bare <section>/<slug>.md). Pages are keyed
    without the prefix, .md and case, shown as first spelled. A task that names none is listed by id and title. Grove tasks
    are open, done or dropped; only open ones count. `gaps` None means the file was not given: "not read", never 0."""
    if gaps is None:
        return {"status": "not_read", "open": None, "pages": {}, "unnamed": [],
                "line": "Guide gaps: not read (no --gaps input; ops_gather.py writes gaps.json)"}
    rows, ids = [], set()
    for t in gaps:
        tid = t.get("id")
        if GAP_TAG in tags_of(t) and (t.get("status") or "open") == "open" and not (tid and tid in ids):
            ids.add(tid)
            rows.append(t)
    pages, shown, unnamed = {}, {}, []
    one_line = lambda s: " ".join(str(s).split())
    for t in rows:
        notes = t.get("notes") or ""
        named = [m.group(1) for m in GAP_PAGE_LINE.finditer(notes)] or \
                [m.group(1) or m.group(2) for m in GUIDE_PAGE.finditer(f"{t.get('title') or ''}\n{notes}")]
        tid = short(t.get("id") or "?")
        if not named:
            unnamed.append({"id": tid, "title": one_line(t.get("title") or "")})
        for p in named:
            p = one_line(re.sub(r"\.mdx?$", "", p.split(GUIDE_PREFIX)[-1], flags=re.I))
            key = p.lower()
            shown.setdefault(key, p)
            if tid not in pages.setdefault(key, []):
                pages[key].append(tid)
    pages = {shown[k]: v for k, v in pages.items()}
    full = len(gaps) >= GAP_LIMIT
    res = {"status": "ok", "open": len(rows), "truncated": full, "pages": pages, "unnamed": unnamed}
    line = f"Guide gaps: {'at least ' if full else ''}{len(rows)} open task{'s' if len(rows) != 1 else ''} tagged {GAP_TAG}"
    if pages:
        line += "; pages named: " + ", ".join(f"{p} ({len(v)}: {', '.join(v)})" for p, v in sorted(pages.items(), key=lambda kv: (-len(kv[1]), kv[0].lower())))
    if unnamed:
        line += f"; {len(unnamed)} with no page named: " + ", ".join(f"{u['id']} '{u['title'][:60]}'" for u in unnamed)
    if full:
        line += f" (the read's {GAP_LIMIT}-row cap: more may be open)"
    res["line"] = line
    return res


HEALTH_TAG = "project-health"  # the decision project-health logs each run; its text carries `health: N/10 (red: …)`
HEALTH_RE = re.compile(r"^health: (\d+)/(\d+)(?: \(red: ([^)]*)\))?", re.M)  # a line of its own: a quoted old score never counts


def health_line(decisions, since, until):
    """The operational-health score (project-health SKILL.md "Operational health", MBN f21b91ed step 2). Report-only:
    the newest decision in the window tagged project-health whose text has a line `health: N/10 (red: …)` (the first such
    line; the skill writes it first), printed with its date and red lines; an older score outside the window is named as
    stale, never reprinted as this week's; none → say so. Newest by the full created_at, so two runs on one day keep order."""
    scored = []
    for d in decisions:
        if HEALTH_TAG not in tags_of(d):
            continue
        m = HEALTH_RE.search(d.get("decision") or "")
        when = to_dt(d.get("created_at"))
        if not m or when is None:
            continue
        scored.append({"id": short(d.get("id") or "?"), "day": when.date(), "when": when, "score": int(m.group(1)),
                       "of": int(m.group(2)), "red": [x.strip() for x in (m.group(3) or "").split(",") if x.strip()]})
    scored.sort(key=lambda s: s["when"], reverse=True)
    week = [s for s in scored if since < s["day"] <= until]
    if week:
        s = week[0]
        red = f"; red: {', '.join(s['red'])}" if s["red"] else "; nothing red"
        line = f"Operational health: {s['score']}/{s['of']} on {s['day']} ({s['id']}){red}"
        return {"status": "ok", "score": s["score"], "of": s["of"], "red": s["red"], "day": str(s["day"]), "id": s["id"], "line": line}
    if scored:
        s = scored[0]
        line = (f"Operational health: no check this week; last {s['score']}/{s['of']} on {s['day']} ({s['id']})"
                + (f", red: {', '.join(s['red'])}" if s["red"] else ""))
        return {"status": "stale", "score": s["score"], "of": s["of"], "red": s["red"], "day": str(s["day"]), "id": s["id"], "line": line}
    return {"status": "none", "score": None, "of": None, "red": [], "day": None, "id": None,
            "line": "Operational health: no check on record"}


def signal_s11(pol, minutes, until, actions):
    """GitHub Actions minutes used this billing month (UTC calendar month) against the plan's limit."""
    vals, bad = thresholds(pol, BUDGET_REPO, K_S11, [("limit_per_month", "num"), ("flag_at_fraction", "num")]) if pol else ({}, [f"not judged: no {BUDGET_REPO} policy"])
    if minutes is None:
        bad = bad + ["not judged: no --minutes input (Actions runs of the month, one row per run)"]
    if bad:
        return not_judged(bad) | {"line": "S11 Actions minutes this month: " + not_judged(bad)["line"]}
    start = until.replace(day=1)
    rows = [m for m in minutes if m["date"] and start <= m["date"] <= until]
    used = sum(m["minutes"] for m in rows)
    by_repo = {}
    for m in rows:
        by_repo[m["repo"]] = by_repo.get(m["repo"], 0) + m["minutes"]
    limit, frac = vals["limit_per_month"], vals["flag_at_fraction"]
    breach = used >= frac * limit
    top = ", ".join(f"{r} {n}" for r, n in sorted(by_repo.items(), key=lambda kv: (-kv[1], kv[0]))[:5]) or "no runs"
    res = {"status": "breach" if breach else "ok", "used": used, "limit_per_month": limit, "flag_at_fraction": frac,
           "month": start.strftime("%Y-%m"), "by_repo": by_repo, "runs": len(rows)}
    res["line"] = (f"S11 Actions minutes {res['month']} (flag at {fmt_num(frac)} of {fmt_num(limit)}): {used} used over {len(rows)} runs "
                   f"({top}) -> {res['status']}; run durations rounded up per run, so the plan's own count can differ")
    if breach:
        actions.append({"type": "task", "signal": "S11", "repo": BUDGET_REPO, "dedup_key": f"budget-breach S11 {res['month']}",
                        "title": f"S11: Actions minutes {used} of {fmt_num(limit)} in {res['month']}",
                        "body": f"{used} minutes over {len(rows)} runs in {res['month']} (by repo: {top}) against {fmt_num(limit)} a month; the flag is {fmt_num(frac)} of it.\n\n"
                                "At the limit the backups, db-apply and the daily production check stop (2026-10-09). Name what to trim; a repo going public frees its minutes (Baylee's call)."})
    return res


def build(decisions, cards, activity, runs, policies, default_policy, until, days, minutes=None, gaps=None):
    since = until - timedelta(days=days)
    in_week = lambda d: since < d <= until
    every, unreadable = parse_records(decisions, keep_restated=True)
    records = [r for r in every if not r["restated"]]
    seen = set()
    uniq = []
    for r in records:
        key = r["id"] or id(r)
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    records = uniq
    targets = reversal_targets(decisions)

    wq = []
    for c in cards:
        if "wrong_question" not in tags_of(c):
            continue
        repo = norm_repo(c.get("project_ref"))
        if repo is None:
            unreadable.append({"kind": "card", "id": c.get("id"), "title": c.get("title") or "", "reason": "no project_ref"})
            continue
        # The day it was tagged (updated_at): the wrong_question tag is added by the session that
        # consumes the card, so a card consumed late still gets its postmortem in that week.
        # resolved_at (top-level `resolution`, or metadata.adjudication) only when updated_at is absent.
        res = c.get("resolution") or ((c.get("metadata") or {}).get("adjudication") or {}).get("resolution") or {}
        when = res.get("resolved_at") if isinstance(res, dict) else None
        wq.append({"id": c.get("id"), "title": c.get("title") or c.get("question") or "", "repo": repo,
                   "row": card_row(c), "day": day_of(c.get("updated_at") or when)})
    # An ask Baylee answered "no need to ask" is logged as a decision tagged needless_ask and
    # table-row-<n> (session-record.md); it counts with the wrong-question cards on its row.
    for d in decisions:
        if "needless_ask" not in tags_of(d):
            continue
        repo = norm_repo(d.get("project_ref"))
        if repo is None:
            unreadable.append({"kind": "needless_ask", "id": d.get("id"), "title": (d.get("decision") or "")[:80], "reason": "no project_ref"})
            continue
        wq.append({"id": d.get("id"), "title": (d.get("decision") or "")[:80].strip(), "repo": repo, "kind": "ask",
                   "row": card_row(d), "day": day_of(d.get("created_at"))})

    act = []
    for a in activity:
        d = parse_day(a.get("date"))
        repo = norm_repo(a.get("repo"))
        if d and repo:
            act.append({"repo": repo, "date": d, "kind": a.get("kind"), "ref": str(a.get("ref", "")), "message": a.get("message")})

    repos = set(policies) | {r["repo"] for r in records} | {c["repo"] for c in wq} | {a["repo"] for a in act}
    actions = []
    out_repos = {}
    for repo in sorted(repos):
        pol, note = None, None
        if repo in policies:
            pol = policies[repo][0]
        elif default_policy:
            pol = default_policy[0]
            note = f"{repo}: no policy given, read against {default_policy[1]}"
        recs = [r for r in records if r["repo"] == repo]
        week = [r for r in recs if in_week(r["date"])]
        entry = {"policy": (policies[repo][1] if repo in policies else (default_policy[1] if default_policy else None)), "note": note}
        nc = []
        for r in sorted(week, key=sortkey):
            fields = (["asks"] if r["kind"] != "direction" and r["asks"] is None else []) + (["refusals"] if r["refusals"] is None else [])
            if fields:
                nc.append({"session": r["session"], "date": r["date"].isoformat(), "fields": fields, "source": r["source"]})
        entry["not_counted"] = nc
        if pol is None:
            msg = f"not judged: no policy ({repo})"
            entry["note"] = f"{repo}: no policy given and no --default-policy"
            for k in ("S1", "S2", "S4", "S5"):
                entry[k] = {"status": "not_judged", "reason": msg, "line": msg}
            entry["interactions"] = []
            out_repos[repo] = entry
            continue
        entry["S1"] = signal_s1(repo, pol, recs, until, actions)
        entry["S2"] = signal_s2(repo, pol, week, actions)
        entry["S4"] = signal_s4(repo, pol, recs, until, targets, actions)
        entry["S5"] = signal_s5(repo, pol, [c for c in wq if c["repo"] == repo], since, until, days, actions)
        inter = []
        s1w = None
        if entry["S1"]["status"] == "breach":
            names = set(entry["S1"]["breaching"]) | {s["session"] for s in entry["S1"]["sessions"]}
            s1w = [r for r in recs if r["session"] in names and r["refusals"]]
            if s1w:
                inter.append("S1 high with S2 > 0: harness, leave the policy alone")
            if entry["S4"]["status"] in ("ok", "breach") and entry["S4"]["reversed"] == 0:
                inter.append("S1 high with S4 = 0 over ≥ min shown: too timid, lower the bar in the table")
        if entry["S4"]["status"] == "breach":
            inter.append("S4 high: too autonomous, widen owner_context")
        entry["interactions"] = inter
        out_repos[repo] = entry

    # activity with no session record (a record of that repo dated the same day, any kind)
    rec_days = {}
    for r in records:
        rec_days.setdefault(r["repo"], set()).add(r["date"])
    groups = {}
    for a in act:
        # sync.py's mirror commits ("sync … from ops") land in every repo on every ops push: not a session's work
        if a["kind"] == "commit" and str(a.get("message") or "").startswith(SYNC_PREFIX):
            continue
        if in_week(a["date"]):
            groups.setdefault((a["repo"], a["date"]), []).append(a)
    no_record = []
    for (repo, d), items in sorted(groups.items()):
        have = rec_days.get(repo, set())
        if d in have:  # same UTC day only: a neighbour day's record would mask an unrecorded session
            continue
        commits = [i for i in items if i["kind"] == "commit"]
        groves = [i for i in items if i["kind"] == "grove"]
        refs = [short(i["ref"][:8] if re.fullmatch(r"[0-9a-f]{40}", i["ref"]) else i["ref"]) for i in items]
        no_record.append({"repo": repo, "date": d.isoformat(), "commits": len(commits), "grove_writes": len(groves), "refs": refs,
                          "text": f"activity with no record: {repo} {d.isoformat()}: {len(commits)} commits, {len(groves)} grove writes ({', '.join(refs)})"})
    quiet = not groups and not any(in_week(r["date"]) for r in records)

    newest = {}
    for r in runs:
        repo, wf = norm_repo(r.get("repo")), r.get("workflow")
        if not repo or not wf:
            continue
        key = (repo, wf)
        t = to_dt(r.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)
        if key not in newest or t > newest[key][0]:
            newest[key] = (t, r)
    runs_out = [{"repo": k[0], "workflow": k[1], "conclusion": v[1].get("conclusion"), "created_at": v[1].get("created_at"), "url": v[1].get("url")}
                for k, v in sorted(newest.items())]

    budget_pol = (policies[BUDGET_REPO][0] if BUDGET_REPO in policies else (default_policy[0] if default_policy else None))
    budgets = {"S10": signal_s10(budget_pol, records, since, until, actions),
               "S11": signal_s11(budget_pol, minutes, until, actions),
               "counter": counter_line(records, since, until),
               "dispatch": dispatch_line(every, since, until),
               "overlap": overlap_line(every, since, until),
               "gaps": gap_line(gaps),
               "health": health_line(decisions, since, until)}

    # dedupe actions
    seen_keys, uniq_actions = set(), []
    for a in actions:
        if a["dedup_key"] not in seen_keys:
            seen_keys.add(a["dedup_key"])
            # the key rides in the filed text, so next week's search by key finds it (never a duplicate)
            a["body"] = a["body"].rstrip() + f"\n\ndedup: {a['dedup_key']}"
            uniq_actions.append(a)

    return {"window": {"since": since.isoformat(), "until": until.isoformat(), "days": days, "quiet_week": quiet},
            "repos": out_repos, "budgets": budgets, "no_record": no_record, "runs": runs_out, "unreadable": unreadable, "actions": uniq_actions}


# ---------------------------------------------------------------- render

def sig_line(k, s):
    return f"- {s['line']}" if s["line"].startswith(k + " ") else f"- {k}: {s['line']}"


def render(res):
    w = res["window"]
    L = [f"## Ops read — decision routing ({w['since']} to {w['until']})", "",
         f"Window: dates after {w['since']} through {w['until']} (UTC)."]
    if res["unreadable"]:
        # one short line per record logged this week; older ones as a count (ledger 6e5aa00e)
        fresh = [u for u in res["unreadable"] if not u.get("created") or w["since"] < u["created"] <= w["until"]]
        older = len(res["unreadable"]) - len(fresh)
        L += ["", f"Unreadable records: {len(res['unreadable'])} (skipped; {len(fresh)} logged this week"
                  + (f", {older} older, listed in --json" if older else "") + ")"]
        L += [f"- {u['kind']} {short(u['id'])} ({u.get('created') or 'no date'}): {u['reason']}; {u['title'][:70].strip()}" for u in fresh]
    for repo, e in res["repos"].items():
        L += ["", f"### {repo}"]
        if e.get("note"):
            L.append(e["note"])
        for k in ("S1", "S2", "S4"):
            L.append(sig_line(k, e[k]))
        s5 = e["S5"]
        L.append(sig_line("S5", s5))
        for d in s5.get("detail", []):
            L.append(f"  - {d}")
        for i in e["interactions"]:
            L.append(f"- {i}")
        for n in e["not_counted"]:
            L.append(f"- not counted: {n['session']} {n['date']} ({', '.join(n['fields'])} null{'; ' + n['source'] if n['source'] else ''})")
    b = res["budgets"]
    L += ["", "### Budgets (account-wide)", f"- {b['S10']['line']}", f"- {b['S11']['line']}", f"- {b['counter']['line']}",
          f"- {b['dispatch']['line']}", f"- {b['overlap']['line']}", f"- {b['gaps']['line']}", f"- {b['health']['line']}"]
    L += ["", "Activity with no record:"]
    if res["no_record"]:
        L += [f"- {n['text']}" for n in res["no_record"]]
    elif w["quiet_week"]:
        L.append("- quiet week: no activity")
    else:
        L.append("- none")
    L += ["", "Runs:"]
    L += [f"- {r['repo']} {r['workflow']}: {r['conclusion']} ({r['created_at']}) {r['url'] or ''}".rstrip() for r in res["runs"]] or ["- none given"]
    L += ["", f"Actions: {len(res['actions'])}"]
    for a in res["actions"]:
        L.append(f"- [{a['type']}] {a['title']} (dedup: {a['dedup_key']})" + (f" -> {a['recommendation']}" if a.get("recommendation") else ""))
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- main

def parse_args(argv):
    p = argparse.ArgumentParser(prog="ops_read.py", description="Weekly ops read of decision routing (offline).")
    p.add_argument("--decisions", required=True)
    p.add_argument("--cards")
    p.add_argument("--activity")
    p.add_argument("--runs")
    p.add_argument("--minutes")
    p.add_argument("--gaps")
    p.add_argument("--policy", action="append", default=[], metavar="REPO=PATH")
    p.add_argument("--default-policy")
    p.add_argument("--until")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--json", action="store_true")
    return p, p.parse_args(argv)


def main(argv=None):
    parser, a = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if a.days < 1:
            raise InputError("--days must be at least 1")
        until = datetime.now(timezone.utc).date()
        if a.until:
            until = parse_day(a.until)
            if until is None:
                raise InputError(f"--until must be YYYY-MM-DD, got {a.until!r}")
        policies = {}
        for spec in a.policy:
            repo, sep, path = spec.partition("=")
            if not sep or not repo.strip() or not path.strip():
                raise InputError(f"--policy needs REPO=PATH, got {spec!r}")
            policies[norm_repo(repo)] = (read_policy(path.strip()), path.strip())
        default = (read_policy(a.default_policy), a.default_policy) if a.default_policy else None
        decisions = load_list(a.decisions)
        cards = load_list(a.cards) if a.cards else []
        activity = load_list(a.activity) if a.activity else []
        runs = load_list(a.runs) if a.runs else []
        minutes = load_minutes(a.minutes) if a.minutes else None
        gaps = load_list(a.gaps) if a.gaps else None
    except InputError as e:
        print(f"ops_read.py: {e}", file=sys.stderr)
        return 2
    res = build(decisions, cards, activity, runs, policies, default, until, a.days, minutes, gaps)
    if a.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
