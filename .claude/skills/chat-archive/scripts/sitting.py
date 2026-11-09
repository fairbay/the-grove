#!/usr/bin/env python3
"""Record Baylee's answer to an adjudication card the way the vault page records it.

The weekly sitting this script once rendered (architecture run 75cbc21d, ruling 4b7bf44c) is
retired (Baylee, 2026-11-06, Grove becb3a31): direction work is one card each, answered on
/adjudicate or in any chat, and an answer in chat is the card's answer (f49acabc). What
stays is the card SQL: the session that reads his answer in chat runs it with Supabase
`execute_sql` on the Grove project, then reads the card back in the done list
(session-start references/dispatch.md, Step 2; close-at-land "On his answer").

  card-sql --card <uuid> --option <id|none> --notes "<text>" --at <ISO time> [--options a,b] [--via chat|sitting]

Offline and pure: it prints SQL and never calls Grove. Exit 0; 2 on an input error.
Python 3.11, stdlib only.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ops_read as R  # noqa: E402  (same directory: UUID_RE, to_dt)


class InputError(Exception):
    pass


def dollar_tag(*texts):
    n = 0
    while any(f"$s{n}$" in x for x in texts):
        n += 1
    return f"$s{n}$"


def card_sql(card, option, notes, at, options=None, via="chat"):
    """SQL that records a card's answer as the vault page records it (metadata.adjudication.resolution with notes,
    option_id, resolved_at, resolved_by, via; status done) through task_update, keeping every other metadata key.
    It touches only a card still open with no resolution, so a ruling made on the vault page is never overwritten."""
    if not R.UUID_RE.match(card or ""):
        raise InputError("--card must be a full UUID")
    if not at or R.to_dt(at) is None:
        raise InputError("--at must be an ISO time")
    opt = None if option in (None, "", "none") else option
    if opt is not None and options is not None and opt not in options:
        raise InputError(f"--option {opt!r} is not one of the card's options {options}")
    res = {"notes": notes or "", "option_id": opt, "resolved_at": at, "resolved_by": "baylee", "via": via}
    body = json.dumps(res)
    tag = dollar_tag(body)
    meta = ("coalesce(t.metadata, '{}'::jsonb) || jsonb_build_object('adjudication', "
            f"coalesce(t.metadata->'adjudication', '{{}}'::jsonb) || jsonb_build_object('resolution', {tag}{body}{tag}::jsonb))")
    return ("with t as (select id, owner_id, metadata from task where id = '" + card + "' and 'adjudication' = any(tags)"
            " and status = 'open' and coalesce(metadata #> '{adjudication,resolution}', 'null'::jsonb) = 'null'::jsonb)\n"
            "select count(*) as ruled from t, lateral (select task_update(t.id, t.owner_id, jsonb_build_object('status', 'done', "
            "'completed_at', '" + at + "', 'metadata', " + meta + "), 'claude-web')) u;")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("card-sql")
    c.add_argument("--card", required=True)
    c.add_argument("--option", required=True, help="the option id he picked, or none for an answer by note")
    c.add_argument("--notes", default="", help="his words, and the decision id that quotes them")
    c.add_argument("--at", required=True, help="when he answered, ISO time")
    c.add_argument("--options", help="the card's option ids, comma-separated; an option outside them exits 2")
    c.add_argument("--via", choices=["chat", "sitting"], default="chat",
                   help="where he answered: any chat (the default; ruling f49acabc), or a sitting record of an older run")
    args = ap.parse_args(argv)
    try:
        opts = [o.strip() for o in args.options.split(",")] if args.options else None
        print(card_sql(args.card, args.option, args.notes, args.at, opts, args.via))
        return 0
    except InputError as e:
        print(f"sitting.py: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
