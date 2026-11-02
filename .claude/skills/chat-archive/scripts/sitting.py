#!/usr/bin/env python3
"""The weekly sitting (architecture run 75cbc21d, build item 2; Baylee's ruling 4b7bf44c).

One chat a week where Baylee rules every non-urgent direction item at once. This script is
offline and pure: the session gathers JSON dumps from Grove (MCP) and the repos, and the
script numbers the items, renders the page, parses his one answer into a plan, and writes
the SQL that records a card ruled in the sitting. It never calls Grove or GitHub.
Procedure: session-start references/sitting.md.

  page    --queue Q --cards C --decisions D --baylee B [--ledger docs/cost-ledger.md]
          --since YYYY-MM-DD [--until YYYY-MM-DD] [--key-out KEY.json] [--json]
  answer  --key KEY.json --text "<his answer>"         -> plan JSON on stdout
  card-sql --card <uuid> --option <id|none> --notes "<text>" --at <ISO time>

Inputs:
  Q  open Grove tasks tagged `sitting-queue` (compact=false): one per built branch waiting.
     Notes lines: `sitting: fairbay/<repo>@<branch>` (required), `screens: <dir on the
     branch>`, `checks: <one line>`, `recommend: merge|hold[: reason]`, `pr: fairbay/<repo>#<n>`
     (a draft opened before the item was queued).
  C  open adjudication cards, every list (grove_list_adjudications, status open).
  D  decisions logged since the last sitting (current_only=false), session records included.
  B  open Grove tasks tagged `baylee` (his real-world steps).

Exit 0; 2 on an input error; `answer` exits 3 when the answer settles nothing.
Python 3.11, stdlib only.
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ops_read as R  # noqa: E402  (same directory: records, tags, loaders)

QUEUE_TAG = "sitting-queue"
SIT_RE = re.compile(r"^sitting: (fairbay/[A-Za-z0-9._-]+)@(\S+)$")
KEY_RE = re.compile(r"^(screens|checks|recommend|pr): (.+)$")
DEADLINE_DAYS = 7
STALE_DAYS = 10  # past one missed sitting; pr_state calls a draft stale at 14


class InputError(Exception):
    pass


def load(path):
    try:
        return R.load_list(path)
    except R.InputError as e:
        raise InputError(str(e))


def notes_lines(t):
    return [ln.strip() for ln in (t.get("notes") or "").splitlines()]


# ---------------------------------------------------------------- queue

def parse_queue(tasks, until):
    """Built branches waiting for the sitting. A task with no valid `sitting:` line is listed as malformed."""
    items, bad = [], []
    seen = {}
    for t in tasks:
        if QUEUE_TAG not in R.tags_of(t) or (t.get("status") or "open") != "open":
            continue
        landing = [ln for ln in notes_lines(t) if ln.startswith("landing: ")]
        if landing:  # a PR already exists for it (an earlier sitting opened it): the gate shows that PR, not the page
            bad.append({"id": t.get("id"), "title": t.get("title") or "", "reason": f"already has {landing[0]}; its PR is on the gate"})
            continue
        sits = [SIT_RE.match(ln) for ln in notes_lines(t)]
        sits = [m for m in sits if m]
        if len(sits) != 1:
            bad.append({"id": t.get("id"), "title": t.get("title") or "",
                        "reason": "no `sitting: fairbay/<repo>@<branch>` line" if not sits else "more than one `sitting:` line"})
            continue
        repo, branch = sits[0].group(1), sits[0].group(2)
        fields = {}
        for ln in notes_lines(t):
            m = KEY_RE.match(ln)
            if m and m.group(1) not in fields:
                fields[m.group(1)] = m.group(2).strip()
        rec = fields.get("recommend", "")
        verdict = rec.split(":", 1)[0].strip().lower()
        reason = rec.split(":", 1)[1].strip() if ":" in rec else ""
        if verdict not in ("merge", "hold"):
            verdict, reason = "merge", reason or "no recommendation written; the default is merge"
        created = R.day_of(t.get("created_at"))
        item = {"id": t.get("id"), "title": t.get("title") or "", "repo": repo, "branch": branch,
                "screens": fields.get("screens"), "checks": fields.get("checks"), "pr": fields.get("pr"),
                "recommend": verdict, "reason": reason,
                "age_days": (until - created).days if created else None}
        item["stale"] = item["age_days"] is not None and item["age_days"] > STALE_DAYS
        key = (repo, branch)
        if key in seen:
            bad.append({"id": t.get("id"), "title": item["title"], "reason": f"same branch as {R.short(seen[key])}"})
            continue
        seen[key] = t.get("id")
        items.append(item)
    items.sort(key=lambda i: (i["repo"], -(i["age_days"] or 0), i["title"]))
    return items, bad


# ---------------------------------------------------------------- cards

def card_fields(c):
    adj = ((c.get("metadata") or {}).get("adjudication") or {})
    q = c.get("question") or adj.get("question") or c.get("title") or ""
    opts = c.get("options") or adj.get("options") or []
    rec = c.get("recommendation") or adj.get("recommendation") or {}
    return q, opts, rec


def parse_cards(cards):
    """Open cards with options. A task tagged `adjudication` that carries no options is not a card the page can rule."""
    out, bad = [], []
    for c in cards:
        if (c.get("status") or "open") != "open" or c.get("resolution"):
            continue
        q, opts, rec = card_fields(c)
        if not [o for o in opts if isinstance(o, dict) and o.get("id")]:
            bad.append({"id": c.get("id"), "title": q, "reason": "tagged adjudication but carries no options"})
            continue
        out.append({"id": c.get("id"), "list": c.get("list") or "?", "question": q,
                    "options": [{"id": str(o.get("id")), "label": o.get("label") or ""} for o in opts if isinstance(o, dict)],
                    "recommend": str(rec.get("option_id")) if rec.get("option_id") else None,
                    "reason": rec.get("reason") or "", "created": str(R.day_of(c.get("created_at")) or "")})
    out.sort(key=lambda c: (c["list"], c["created"]))
    return out, bad


# ---------------------------------------------------------------- digest

def parse_digest(decisions, since, until):
    """Contested calls logged since the last sitting, plus the calls the archives already showed him
    (each record's random fifth), less any he has reversed. Each appears once."""
    in_window = lambda d: d is not None and since <= d <= until  # the last sitting's own day counts again: a session after it
    by_id = {str(d.get("id")): d for d in decisions if d.get("id")}
    reversed_ids = set(R.reversal_targets(decisions))
    records, _ = R.parse_records(decisions)
    out, seen = [], set()

    def add(did, why):
        full = next((k for k in by_id if R.same_id(k, did)), None)
        key = full or did
        if key in seen or any(R.same_id(key, r) for r in reversed_ids):
            return
        seen.add(key)
        d = by_id.get(full) if full else None
        if d is None and not re.fullmatch(r"[0-9a-f-]{8,36}", did):
            # an older record wrote the call itself instead of its id: shown, but it cannot be reversed by id
            out.append({"id": did, "why": why + ", prose (no id)", "text": did, "confidence": None})
            return
        out.append({"id": key, "why": why, "text": (d or {}).get("decision") or "(not in the dump)",
                    "confidence": (d or {}).get("confidence")})

    for d in decisions:
        if "contested" in R.tags_of(d) and in_window(R.day_of(d.get("created_at"))):
            add(str(d["id"]), "contested")
    for r in records:
        if in_window(r["date"]):
            for cid in r["calls_shown"]:
                add(cid, "random fifth")
    return out


# ---------------------------------------------------------------- real-world step

def parse_baylee(tasks, until):
    """His open real-world steps; the first is the one the sitting drafts send-ready."""
    rows = []
    for t in tasks:
        if "baylee" not in R.tags_of(t) or (t.get("status") or "open") != "open" or "adjudication" in R.tags_of(t):
            continue
        due = R.day_of(t.get("due_at"))
        rows.append({"id": t.get("id"), "title": t.get("title") or "", "due": str(due) if due else None,
                     "days_left": (due - until).days if due else None, "priority": t.get("priority") or 0,
                     "created": str(R.day_of(t.get("created_at")) or "")})
    far = 10 ** 6
    rows.sort(key=lambda r: (r["days_left"] if r["days_left"] is not None else far, -r["priority"], r["created"]))
    for r in rows:
        r["deadline"] = r["days_left"] is not None and r["days_left"] <= DEADLINE_DAYS
    return rows


def real_world_items(rows):
    """The steps the sitting drafts send-ready: every one with a deadline inside a week (at most 3), else the first."""
    due = [r for r in rows if r["deadline"]][:3]
    return due or rows[:1]


# ---------------------------------------------------------------- ledger

def read_ledger(path):
    """The markdown table rows of docs/cost-ledger.md, verbatim; None when absent."""
    if not path:
        return None
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        raise InputError(f"cannot read {path}: {e.strerror or e}")
    rows = [ln for ln in text.splitlines() if ln.startswith("|")]
    return rows or None


# ---------------------------------------------------------------- page

def build(queue, cards, decisions, baylee, ledger_rows, since, until):
    items, bad = parse_queue(queue, until)
    crd, bad_cards = parse_cards(cards)
    dig = parse_digest(decisions, since, until)
    rw = parse_baylee(baylee, until)
    records, unreadable = R.parse_records(decisions)
    counter = R.counter_line(records, since - timedelta(days=1), until)  # counter_line's window starts after its first day
    key = {}
    for i, it in enumerate(items, 1):
        key[f"Q{i}"] = {"kind": "queue", "id": it["id"], "repo": it["repo"], "branch": it["branch"],
                        "pr": it["pr"], "recommend": it["recommend"]}
    for i, c in enumerate(crd, 1):
        key[f"C{i}"] = {"kind": "card", "id": c["id"], "options": [o["id"] for o in c["options"]],
                        "recommend": c["recommend"]}
    for i, d in enumerate(dig, 1):
        key[f"D{i}"] = {"kind": "digest", "id": d["id"], "recommend": "keep"}
    for i, r in enumerate(real_world_items(rw), 1):
        key[f"R{i}"] = {"kind": "real_world", "id": r["id"], "recommend": None}
    return {"since": str(since), "until": str(until), "queue": items, "malformed": bad + bad_cards, "cards": crd,
            "digest": dig, "real_world": rw, "counter": counter, "ledger": ledger_rows,
            "unreadable_records": len(unreadable), "key": key}


def render(res):
    L = [f"**Sitting {res['until']}** (since {res['since']})", ""]
    L.append("**Direction waiting (merge or hold)**")
    if not res["queue"]:
        L.append("- none queued")
    for n, it in zip([k for k in res["key"] if k.startswith("Q")], res["queue"]):
        age = f", {it['age_days']} d" if it["age_days"] is not None else ""
        stale = " **(waited past one sitting)**" if it.get("stale") else ""
        L.append(f"- **{n}** {it['title']} — `{it['repo']}@{it['branch']}`{age}{stale}. Recommend **{it['recommend']}**"
                 + (f": {it['reason']}" if it["reason"] else ""))
        if it["pr"]:
            L.append(f"  - lands through its open draft {it['pr']}")
        if it["checks"]:
            L.append(f"  - checks: {it['checks']}")
        if it["screens"]:
            L.append(f"  - screens: `{it['screens']}` (shown inline below)")
    for b in res["malformed"]:
        L.append(f"- not offered: {R.short(b['id'])} ({b['title'][:80]}): {b['reason']}")
    L += ["", "**Cards (pick an option)**"]
    if not res["cards"]:
        L.append("- none open")
    for n, c in zip([k for k in res["key"] if k.startswith("C")], res["cards"]):
        opts = "; ".join(f"{o['id']}) {o['label']}" for o in c["options"])
        rec = f" Recommend **{c['recommend']}**" + (f": {c['reason']}" if c["reason"] else "") if c["recommend"] else " No recommendation."
        L.append(f"- **{n}** [{c['list']}] {c['question']} — {opts}.{rec}")
    L += ["", "**Calls made without you (keep or reverse)**"]
    if not res["digest"]:
        L.append("- none")
    for n, d in zip([k for k in res["key"] if k.startswith("D")], res["digest"]):
        label = "" if d["why"].endswith("(no id)") else f"{R.short(d['id'])} "
        L.append(f"- **{n}** {label}({d['why']}): {d['text'][:200]}")
    L += ["", "**Your real-world steps**"]
    rw = res["real_world"]
    if not rw:
        L.append("- none open")
    names = [k for k in res["key"] if k.startswith("R")]
    for n, top in zip(names, real_world_items(rw)):
        due = f", due {top['due']}" + (" — **deadline inside a week**" if top["deadline"] else "") if top["due"] else ""
        L.append(f"- **{n}** {top['title']} ({R.short(top['id'])}{due}). Draft below, send-ready; say `{n} done` once it is sent.")
    if rw:
        L.append(f"- {len(rw) - len(names)} more open in Grove (tag `baylee`).")
    L += ["", "**Counter**", f"- {res['counter']['line']}"]
    if res["ledger"]:
        L += ["", "**Cost ledger**"] + res["ledger"]
    L += ["", "**Answer once.** `ok` takes every recommendation. Or name items: `Q1 hold: <why>`, `C2 b`, "
          "`D1 reverse`, plus `ok` for the rest. An item your answer leaves unclear waits for the next sitting."]
    return "\n".join(L)


# ---------------------------------------------------------------- answer

ITEM_RE = re.compile(r"^[QCDR]\d+$", re.I)
ALL_OK = {"ok", "okay", "all ok", "ok to the rest", "ok for the rest", "rest ok", "the rest ok", "all as recommended",
          "rest as recommended", "the rest as recommended", "approve all", "as recommended"}
# A note that carries a condition is not an approval: the item waits (review round 1, finding 1).
CONDITIONAL = re.compile(r"\b(not|no|never|unless|after|if|but|except|until|once|when|only|before)\b|n't\b", re.I)
VERBS = {
    "queue": {"merge": "merge", "approve": "merge", "approved": "merge", "land": "merge", "ship": "merge", "yes": "merge",
              "ok": "merge", "okay": "merge", "hold": "hold", "wait": "hold", "drop": "drop", "close": "drop"},
    "digest": {"keep": "keep", "ok": "keep", "reverse": "reverse", "undo": "reverse"},
    "real_world": {"done": "done", "sent": "done", "later": "later", "skip": "later"},
}
FILLER = {"and", "&", "both", "please", "pls"}
SAFE_WORDS = {"hold", "wait", "keep", "later", "skip"}  # actions that change nothing may carry any note


def clauses(text):
    """Comma, semicolon, newline and ' and ' between items split clauses; a colon starts the clause's note."""
    out = []
    for part in re.split(r"[,;\n]+", text or ""):
        part = part.strip(" .!")
        if not part:
            continue
        head = part.split(":", 1)[0]
        subs = re.split(r"\s+and\s+", head, flags=re.I)
        # "C1 a and C2 b" is two clauses; "Q1 and Q3 merge" is one (its first half has no word of its own)
        if len(subs) > 1 and ":" not in part and all(
                any(ITEM_RE.match(w) for w in x.split()) and any(not ITEM_RE.match(w) for w in x.split()) for x in subs):
            out.extend(x.strip() for x in subs)
        else:
            out.append(part)
    return out


def parse_clause(key, clause):
    """-> (names, action word or None, note, problem). Words before the colon must be item names, filler and at most
    one action word; anything else makes the clause unreadable, so its items wait."""
    head, _, note = clause.partition(":")
    note = note.strip()
    words = [w for w in re.split(r"\s+", head.strip()) if w]
    names = [w.upper() for w in words if ITEM_RE.match(w)]
    rest = [w.lower() for w in words if not ITEM_RE.match(w) and w.lower() not in FILLER]
    if not names:
        return [], None, note, None
    if len(rest) > 1:
        return names, None, note, f"more than one word besides the items: {' '.join(rest)}"
    if not rest and note:  # "Q1: merge" — the word right after the colon
        first, _, tail = note.partition(" ")
        rest, note = [first.strip(" .!-").lower()], tail.strip(" -")
    word = rest[0] if rest else None
    if note and CONDITIONAL.search(note) and word not in SAFE_WORDS:
        return names, None, note, "the note carries a condition"
    return names, word, note, None


def parse_answer(key, text):
    """His one answer -> one action per numbered item. Strict on purpose: an item merges, rules or reverses only when a
    clause names it with one plain word, or when a clause that is only `ok` (or "rest as recommended") takes the
    recommendation for the items no clause named. Anything else waits for the next sitting. A clause naming no item
    and not an `ok` clause is reported, never read."""
    plan, said, conflicts = {}, {}, set()
    accept_all = False
    unparsed, unknown = [], []
    for c in clauses(text):
        low = c.lower().strip()
        if low in ALL_OK:
            accept_all = True
            continue
        names, word, note, problem = parse_clause(key, c)
        if not names:
            unparsed.append(c)
            continue
        for name in names:
            if name not in key:
                unknown.append(name)
                continue
            k = key[name]
            act = None
            if not problem and word is not None:
                if k["kind"] == "card":
                    act = f"option:{word}" if word in k["options"] else None
                else:
                    act = VERBS.get(k["kind"], {}).get(word)
            entry = {"action": act, "notes": note} if act else {"action": "unsettled", "said": c,
                                                                  "why": problem or ("no option of this card" if k["kind"] == "card" and word else "no plain action word")}
            if name in plan and plan[name]["action"] != entry["action"]:
                conflicts.add(name)
            plan[name] = entry
            said[name] = c
    for name in conflicts:
        plan[name] = {"action": "unsettled", "said": said[name], "why": "named twice with different actions"}
    for name, k in key.items():
        if name in plan:
            continue
        if accept_all and k["recommend"]:
            r = k["recommend"]
            plan[name] = {"action": f"option:{r}" if k["kind"] == "card" else r, "notes": "accepted the recommendation"}
        else:
            plan[name] = {"action": "unsettled", "said": "", "why": "not named"}
    if unknown:
        plan["_unknown"] = unknown
    if unparsed:
        plan["_unparsed"] = unparsed
    return plan


def plan_lines(key, plan):
    """The plan echoed once before anything runs: what will happen to each item, unsettled ones last."""
    order = sorted((k for k in plan if not k.startswith("_")), key=lambda k: (plan[k]["action"] == "unsettled", k))
    lines = [f"- {k}: {plan[k]['action']}" + (f" ({plan[k].get('why')})" if plan[k]["action"] == "unsettled" else "")
             for k in order]
    for k in ("_unknown", "_unparsed"):
        if plan.get(k):
            lines.append(f"- {'not on the page' if k == '_unknown' else 'not read'}: {', '.join(plan[k])}")
    return lines


# ---------------------------------------------------------------- card resolution

def dollar_tag(*texts):
    n = 0
    while any(f"$s{n}$" in x for x in texts):
        n += 1
    return f"$s{n}$"


def card_sql(card, option, notes, at, options=None):
    """SQL that records a card ruled in the sitting as the vault page records it (metadata.adjudication.resolution
    with notes, option_id, resolved_at, resolved_by; status done) through task_update, keeping every other metadata
    key. It touches only a card still open with no resolution, so a ruling made on the vault page is never overwritten."""
    if not R.UUID_RE.match(card or ""):
        raise InputError("--card must be a full UUID")
    if not at or R.to_dt(at) is None:
        raise InputError("--at must be an ISO time")
    opt = None if option in (None, "", "none") else option
    if opt is not None and options is not None and opt not in options:
        raise InputError(f"--option {opt!r} is not one of the card's options {options}")
    res = {"notes": notes or "", "option_id": opt, "resolved_at": at, "resolved_by": "baylee", "via": "sitting"}
    body = json.dumps(res)
    tag = dollar_tag(body)
    meta = ("coalesce(t.metadata, '{}'::jsonb) || jsonb_build_object('adjudication', "
            f"coalesce(t.metadata->'adjudication', '{{}}'::jsonb) || jsonb_build_object('resolution', {tag}{body}{tag}::jsonb))")
    return ("with t as (select id, owner_id, metadata from task where id = '" + card + "' and 'adjudication' = any(tags)"
            " and status = 'open' and coalesce(metadata #> '{adjudication,resolution}', 'null'::jsonb) = 'null'::jsonb)\n"
            "select count(*) as ruled from t, lateral (select task_update(t.id, t.owner_id, jsonb_build_object('status', 'done', "
            "'completed_at', '" + at + "', 'metadata', " + meta + "), 'claude-web')) u;")


# ---------------------------------------------------------------- cli

def check_counts(dumps, expect):
    """A row lost between a tool's output and its dump file is caught here, never rendered as 'nothing waits'."""
    for part in [p for p in expect.split(",") if p.strip()]:
        name, _, n = part.partition("=")
        name = name.strip()
        if name not in dumps or not n.strip().isdigit():
            raise InputError(f"--expect: bad entry {part!r}")
        if len(dumps[name]) != int(n):
            raise InputError(f"{name}: the dump has {len(dumps[name])} rows, the tool reported {n}; redo that dump")


def day(s, name):
    d = R.parse_day(s)
    if d is None:
        raise InputError(f"{name} must be YYYY-MM-DD")
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("page")
    for f in ("queue", "cards", "decisions", "baylee"):
        p.add_argument(f"--{f}", required=True)
    p.add_argument("--ledger")
    p.add_argument("--since", required=True)
    p.add_argument("--until")
    p.add_argument("--key-out")
    p.add_argument("--expect", default="", help="queue=N,cards=N,decisions=N,baylee=N: the counts the tools reported; a dump that differs exits 2")
    p.add_argument("--json", action="store_true")
    a = sub.add_parser("answer")
    a.add_argument("--key", required=True)
    a.add_argument("--text", required=True)
    c = sub.add_parser("card-sql")
    c.add_argument("--card", required=True)
    c.add_argument("--option", required=True)
    c.add_argument("--notes", default="")
    c.add_argument("--at", required=True)
    c.add_argument("--options", help="the card's option ids, comma-separated (from key.json); an option outside them exits 2")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "page":
            since = day(args.since, "--since")
            until = day(args.until, "--until") if args.until else datetime.now(timezone.utc).date()
            dumps = {f: load(getattr(args, f)) for f in ("queue", "cards", "decisions", "baylee")}
            check_counts(dumps, args.expect)
            res = build(dumps["queue"], dumps["cards"], dumps["decisions"], dumps["baylee"],
                        read_ledger(args.ledger), since, until)
            if args.key_out:
                with open(args.key_out, "w", encoding="utf-8") as f:
                    json.dump(res["key"], f, indent=1)
            print(json.dumps(res, default=str, indent=1) if args.json else render(res))
            return 0
        if args.cmd == "answer":
            try:
                key = json.load(open(args.key, encoding="utf-8"))
            except (OSError, ValueError) as e:
                raise InputError(f"cannot read key {args.key}: {e}")
            plan = parse_answer(key, args.text)
            print(json.dumps({"plan": plan, "echo": plan_lines(key, plan)}, indent=1))
            settled = [k for k, v in plan.items() if not k.startswith("_") and v["action"] != "unsettled"]
            return 0 if settled or not key else 3
        opts = [o.strip() for o in args.options.split(",")] if args.options else None
        print(card_sql(args.card, args.option, args.notes, args.at, opts))
        return 0
    except InputError as e:
        print(f"sitting.py: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
