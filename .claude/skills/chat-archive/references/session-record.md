# Session record, random fifth, data-batch close, agent state

What the archive (and, when the archive did not run, the next session's entry)
writes so the decision-routing signals have data: `fairbay/ops`
docs/decision-routing/DESIGN.md §3–§5 (Baylee's ruling 7fd4b24e). The weekly read
that consumes the records is `scripts/ops_read.py` (project-health, "Ops read").

## Contents
- The record (Step 7b) — fields, sources, the decision call, no close without it
- The random fifth — which calls Baylee sees, and how he reverses one
- Reversals and wrong questions — the two tags
- At entry (session-start Phase 0) — a missing record for the previous session
- MBN data-batch close — guard-record.json, guard.mjs, the verdict line, the Go
- Agent state — the output-file check before any report about an agent

## The record (Step 7b)

One Grove decision per session, tagged `session-record`, `project_ref` set, the
numbers as JSON in its `context` field (decisions have no metadata; the project
row's metadata is overwritten each session, so it cannot hold a series).

```json
{"record": 1, "session": "<session URL or id>", "surface": "chat|code|routine",
 "date": "YYYY-MM-DD", "repo": "fairbay/<repo> or null", "kind": "upkeep|direction|<change_batches.kind>",
 "asks": 0, "refusals": 0, "refused": [], "merges": 0,
 "calls_logged": ["<rung-3 decision ids>"], "calls_shown": ["<ids of the random fifth>"],
 "cards": ["<adjudication ids filed>"], "tasks_for_baylee": ["<task ids for him>"],
 "source": "transcript|self-reported|no-transcript"}
```

| Field | Source |
|---|---|
| `date` | UTC date of the archive |
| `kind` | a data batch: its `ops.change_batches.kind`; else the goal line: a ledger item is `upkeep` unless the goal marked it `direction` |
| `asks` | questions put to Baylee after his opening message (AskUserQuestion, `ask_user_input_v0`, a question in prose) |
| `refusals`, `refused` | tool results carrying a permission or classifier refusal, each refused command in `refused` |
| `merges` | PR merge calls (`gh api -X PUT …/merge`, git-ops merge) |
| `calls_logged` | Grove decisions this session logged at rung 3 (not the record itself, not reversals) |
| `calls_shown`, `cards`, `tasks_for_baylee` | the random fifth below; Grove ids filed this session |
| `source` | `transcript` when counted from the transcript; `self-reported` when counted by recall; `no-transcript` for an entry stub |

**Counting.** In a Code session whose repo has `scripts/session-usage/report.py`
(MBN), run it with `--routing` on this session's transcript: it prints
`{"asks","refusals","merges","source":"transcript"}`. Anywhere else (chat, ops,
a repo without the script) count the three from the conversation and set
`source: self-reported`. Never grade the asks (no "needed" field: a session
cannot judge its own asks).

**The call.** `grove_log_decision(decision="session-record <date> <repo or slug>:
asks A, refusals R, merges M, calls L (shown S), cards C", project_ref=…,
context=<the JSON>, tags=["session-record"], confidence="high", reversible="yes",
rung=3)`. Then read it back once (`grove_get`) and check `context` parses.

**No close without it.** The archive does not reach Step 9's write-back, the
summary or the Next-step line until the record's id is in hand. If Grove refuses
twice, the archive ends with "Not closed: session record not written (<error>)"
and the record JSON in the response, so the next session's entry writes it.

## The random fifth

The random fifth is what Baylee sees of this session's rung-3 calls; without it
S4 has no denominator and silence would read as approval.

```bash
python3 -c 'import math,random,sys; ids=sys.argv[1:]; k=math.ceil(len(ids)/5) if ids else 0; print(" ".join(random.sample(ids,k)))' <id> <id> …
```

Print the picked calls in the Step 4 summary and in the Grove session line
(9b), one line each, under the heading **Calls to check (random fifth):**

```
- 5f2c1a90 — <the decision's first 90 characters> — reply "reverse 5f2c1a90" to undo
```

Their ids go in the record's `calls_shown`. No rung-3 calls → the line reads
"Calls to check: none this session" and `calls_shown` is empty.

## Reversals and wrong questions

- **Reversal.** When Baylee replies "reverse <id>" (or reverses a rung-3 call in a
  note), the session that receives it resolves the full id, logs a decision with
  `supersedes=<id>`, tag `reversal`, the reversed call and his words in
  `context`, then undoes the call as upkeep. One reversal decision per call.
- **Wrong question.** When a session consumes an adjudication card resolved by
  note with no option (`grove_list_adjudications(status="done")`, `resolution.option_id`
  null, `resolution.notes` present), it adds tags `wrong_question` and
  `table-row-<n>` (the decision-table row of the repo's `.claude/policy.json`
  that sent the item to him, 1-based; `table-row-unknown` when none did) with
  `grove_update_task`, keeping the card's existing tags. The next session's
  plan carries one postmortem line naming that row.

## At entry (session-start Phase 0)

Land-and-leave lets a session end without archiving, so the next session's
entry closes the gap once the project row is known:

1. The previous session is the one that wrote the handoff session-start loaded
   (`meta.generated`, `meta.surface`, `meta.landing`).
2. `grove_list_decisions(project_ref=<repo or slug>, limit=20, compact=false)`;
   a decision tagged `session-record` whose `context.date` is the handoff's date
   or later covers it.
3. None: when that session's transcript is on disk (a resumed Code container),
   count it as at Step 7b with `source: transcript`; otherwise log a stub with
   `asks`, `refusals`, `merges` null, the lists empty, `source: no-transcript`
   and the decision text "session-record <date> <repo>: stub, no transcript".
4. Then consume verdicts: tag wrong-question cards and log reversals as above.

## MBN data-batch close

For an MBN data session (DATA-WORK "One goal, one session"; a batch `mNNNN`
applied and published this session), before the handoff is written:

1. **Append the batch** to `scripts/batch/guard-record.json` (format in its
   `about`): `id`, `series`, `listings_edited` (pairs-from-export's summary, as the
   batch's Grove decision counts them), `listings_read` (the reads'
   validate-read line), `flagged` (the detector's worklist count), `cost`
   (report.py, cache read in millions), `source`, and `followups` (the batch's
   `from-mNNNN` tasks, each with its one class tag and status). Unknown → `null`,
   never a guess.
2. **Run the guard:** `node scripts/batch/guard.mjs --batch mNNNN`, adding
   `--tasks <file>` when a Grove dump of the batch's tasks is at hand
   (`grove_list_tasks(tag="from-mNNNN", compact=false)` saved as JSON) and
   `--pairs <file>` when the pairs output is. Exit 2 is an input error: fix the
   record or the tags and run again; never write a verdict from a failed run.
3. **Write the verdict line** verbatim into HANDOFF `progress:` and into the
   batch's Grove decision: in its `context` when 9b logs it now; when it was
   logged earlier (decisions are append-only), a superseding decision that
   repeats the call and adds the line.
4. **Act on it.** `continue`: the Next-step line carries the Go for the next
   batch. `pause-and-repair`: the next session lands the validator rule first
   and the Next-step line names it, no Go. `escalate`: bring Baylee the ledger
   and a recommendation (`policy: owner_context`); no Go. Open `gap` items above
   the cap make the next session a library session: name it, no Go.

**The Go in the Next-step line.** When the next session is a data batch, the
Step 5 line carries `.claude/policy.json` `harness.go` verbatim with `mNNNN`
replaced by the next batch's migration number (the next free number in
`supabase/migrations/` as the plan names it). Read the sentence from the file,
never from memory: what it covers is Baylee's consent and changes only by his
ruling.

## Agent state

Before saying that a background agent is running, finished, stopped or lost
(Step 2, Step 4, a briefing, a progress line), read its output file:

```bash
f=<output_file from the Agent call, e.g. /tmp/claude-0/…/tasks/<id>.output>
date; stat -L -c '%y %s bytes' "$f"   # -L: the output file is a symlink; without it stat reports the link
tail -c 600 "$f" | tail -n 1 | cut -c1-300
```

Never `cat` the file (it is the agent's whole transcript), and never wait on a
`grep` for the hand-back tool's name: the brief and the system text in the same
file contain it too. Finished means the completion notification arrived or the
last line is the hand-back call; an mtime within the last minute means running. An mtime older than a few
minutes with no hand-back after an interrupt, a container restart or a long gap
means stopped: relaunch it (same brief) and say so. A lost completion
notification is not a lost report: the hand-back is in `tasks/<id>.output`.
