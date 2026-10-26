# Session record, random fifth, data-batch close, agent state

What the archive (and, when the archive did not run, the next session's entry)
writes so the decision-routing signals have data: `fairbay/ops`
docs/decision-routing/DESIGN.md §3–§5 (Baylee's ruling 7fd4b24e). The weekly read
that consumes the records is `scripts/ops_read.py` (project-health, "Ops read").

## Contents
- The record (Step 3e) — fields, sources, the decision call, no close without it
- The random fifth — which calls Baylee sees, and how he reverses one
- Reversals and wrong questions — the two tags
- At entry (session-start Phase 0) — a missing record for the previous session
- MBN data-batch close — guard-record.json, guard.mjs, the verdict line, the Go
- Agent state — the output-file check before any report about an agent

## The record (Step 3e)

One Grove decision per session, tagged `session-record`, `project_ref` set, the
numbers as JSON in its `context` field (decisions have no metadata; the project
row's metadata is overwritten each session, so it cannot hold a series).

```json
{"record": 1, "session": "<session URL or id>", "surface": "chat|code|routine",
 "date": "YYYY-MM-DD", "repo": "fairbay/<repo> or null", "kind": "upkeep|direction|<change_batches.kind>",
 "asks": 0, "refusals": 0, "refused": [], "merges": 0,
 "calls_logged": ["<rung-3 decision ids>"], "calls_shown": ["<ids of the random fifth>"],
 "cards": ["<adjudication ids filed>"], "tasks_for_baylee": ["<task ids for him>"],
 "cache_read_m": null,
 "source": "transcript|self-reported|no-transcript", "lane": "<x>, lanes repos only"}
```

| Field | Source |
|---|---|
| `session` | this session's id or URL; the archive also writes it as the handoff's `meta.session`, which is how the next entry finds this record |
| `date` | UTC date of the archive |
| `kind` | a data batch: its `ops.change_batches.kind`; else the goal line: a ledger item is `upkeep` unless the goal marked it `direction` |
| `asks` | questions put to Baylee after his opening message (AskUserQuestion, `ask_user_input_v0`, a question in prose) |
| `refusals`, `refused` | tool results carrying a permission or classifier refusal, each refused command in `refused` |
| `merges` | PR merge calls (`gh api -X PUT …/merge`, git-ops merge) |
| `calls_logged` | Grove decisions this session logged at rung 3 (not the record itself, not reversals) |
| `calls_shown`, `cards`, `tasks_for_baylee` | the random fifth below; Grove ids filed this session |
| `cache_read_m` | the session's cache-read tokens in millions by model family, `{"opus": 12.3, "sonnet": 4.1}`, as `session_report.py` prints it (below); else `null`, never a guess. The weekly read's S10 line sums it per day (`ops_read.py`); a record without it is counted as "no cost", not as zero |
| `source` | `transcript` when counted from the transcript; `self-reported` when counted by recall; `no-transcript` for an entry stub |
| `lane` | in a lanes repo, the lane the session worked (`"a"`); the record also takes the tag `lane-<x>`, which is how dispatch finds each lane's last session (session-start `references/dispatch.md`). Omitted outside lanes and for a dispatch record (tag `dispatch` instead) |

**Counting.** In a Code session, run `python3 .claude/skills/chat-archive/scripts/session_report.py
<session-dir-prefix> <out.json> <out.md> --routing` (the prefix is
`~/.claude/projects/<project>/<session-id>`, no extension; MBN's
`scripts/session-usage/report.py` wraps it and takes `--work-from` too): stdout
ends with `{"asks","refusals","merges","source":"transcript","cache_read_m":{…}}`,
the record's four counts and its cost in one line, and the refused commands for
`refused` are in the out.json's `routing` section. Anywhere else (chat, a repo
without the synced skill) count the three from the conversation, set
`source: self-reported` and `cache_read_m: null`. Never grade the asks (no
"needed" field: a session cannot judge its own asks).

**The call.** `grove_log_decision(decision="session-record <date> <repo or slug>:
asks A, refusals R, merges M, calls L (shown S), cards C", project_ref=…,
context=<the JSON>, tags=["session-record", "lane-<meta.lane>"] (the lane tag
from the baton's `meta.lane`; in a repo without lanes the list is
["session-record"] alone), confidence="high", reversible="yes", rung=3)`. Then
read it back once (`grove_get`) and check `context` parses and the tags carry
the lane; if the tag is missing, log the record again with
`supersedes=<first id>` (the weekly read counts a superseding record once;
five lane A records of 2026-10 missed the tag when it was a parenthesis).

**No close without it.** The archive does not write the summary (Step 4), the
Next-step line or Step 9's write-back until the record's id is in hand. If
Grove refuses twice, the git handoff still goes out (it is the baton that does
not depend on Grove) with the record JSON in a top-level `pending_record:`
field, the summary says "Session record pending: Grove refused (<error>)", and
the next session's entry logs it. A session-only chat with no handoff file
puts the JSON in the response and says the next entry will write a stub.

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
   (`meta.session`, `meta.generated`). For a project with no handoff file, it
   is the project row's `last_session` day.
2. `grove_list_decisions(project_ref=<repo or slug>, current_only=false,
   compact=false, limit=100)`, keeping those tagged `session-record`. One
   covers it when its `context.session` equals `meta.session`; when the handoff
   has no `meta.session` (written before this step existed), when its
   `created_at` is after `meta.generated`; for a project with no handoff, when
   its `context.date` is `last_session`. A record with no `session` field
   (written by hand before this format) covers only by `created_at`.
3. None: the handoff's `pending_record:` (a record Grove refused at archive) is
   logged as written. Else, when that session's transcript is on disk (a resumed
   Code container), count it as at Step 3e with `source: transcript`. Else log a
   stub: `asks`, `refusals`, `merges` null, the lists empty, `source:
   no-transcript`, the decision text "session-record <date> <repo>: stub, no
   transcript". Never a second stub for the same `meta.session`.
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
   `--pairs <file>` when the pairs output is at hand, and `--tasks <file>` only
   with a dump of **every** batch in the record: `--tasks` replaces the
   follow-ups of all batches, so a dump of the new batch alone erases older
   leaks and can turn a pause into `continue`. Build it with one
   `grove_list_tasks(tag="from-<id>", compact=false, limit=100)` per batch id in
   guard-record.json, concatenated into one JSON array; without that, run
   without `--tasks` (the record's snapshot). Exit 0, 3 and 4 are verdicts
   (continue, pause-and-repair, escalate); exit 2 is an input error: fix the
   record or the tags and run again, never write a verdict from an exit 2.
3. **Write the verdict line** verbatim into HANDOFF `progress:` (with lanes: the lane file's
   `progress:`, `references/lanes.md`) and into the
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
replaced by the next batch's migration number: the highest `mNNNN` across
`scripts/m*/` and `db/migrations/*_m*.sql`, plus one, or the number the plan
names for the next batch. When the two disagree, write no Go: name the
mismatch in the Next-step line for Baylee to settle. Read the sentence from the file,
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
