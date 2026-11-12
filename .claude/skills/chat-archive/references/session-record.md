# Session record, contested calls, data-batch close, agent state

What the archive (and, when the archive did not run, the next session's entry)
writes so the decision-routing signals have data: `fairbay/ops`
docs/decision-routing/DESIGN.md §3–§5 (Baylee's ruling 7fd4b24e). The weekly read
that consumes the records is `scripts/ops_read.py` (project-health, "Ops read").

## Contents
- The record (Step 3e) — fields, sources, the decision call, no close without it
- Contested calls — the calls Baylee sees, and how he reverses any call
- Reversals and wrong questions — the tags, with needless asks
- At entry (session-start Phase 0) — a missing record for the previous session
- MBN data-batch close — guard-record.json, guard.mjs, the verdict line, the Go
- PR subscriptions — unsubscribe from every PR that outlives the session
- Agent state — the output-file check before any report about an agent

## The record (Step 3e)

One Grove decision per session, tagged `session-record`, `project_ref` set, the
numbers as JSON in its `context` field (decisions have no metadata; the project
row's metadata is overwritten each session, so it cannot hold a series).

```json
{"record": 2, "session": "<session URL>", "surface": "chat|code|routine",
 "date": "YYYY-MM-DD", "repo": "fairbay/<repo> or null", "kind": "upkeep|direction|<change_batches.kind>",
 "asks": 0, "refusals": 0, "refused": [], "merges": 0,
 "prs": [{"pr": "fairbay/<repo>#<n>", "via": "self|ask|github|pending|open", "tapped": false}],
 "start": "pasted|typed|none", "opening_chars": 0, "interrupts": 0,
 "calls_logged": ["<rung-3 decision ids>"],
 "cards": ["<adjudication ids filed>"], "tasks_for_baylee": ["<task ids for him>"],
 "cache_read_m": {"opus": 12.3}, "source": "transcript", "lane": "<x>",
 "global_reads": [{"file": "ladder.md", "bytes": 12127}]}
```

**Build it with one call, on every surface** (architecture run 75cbc21d, build item 1:
the counter whole; `docs/architecture-run/04-PROPOSAL.md` §8). A chat and a Code
session both keep their transcript on disk (`~/.claude/projects/<dir>/<id>.jsonl`;
seen 2026-10-28 in chat), so nothing is counted by recall:

```bash
python3 .claude/skills/chat-archive/scripts/session_report.py --record \
  --session <session URL> --surface chat|code|routine --repo fairbay/<repo>|null \
  --kind upkeep|direction|<kind> [--lane <x>] \
  --prs "<n>:<via>,fairbay/<other>#<n>:<via>" [--not-merged <n>] [--asks-prose N] \
  --calls <ids> --cards <ids> --tasks <ids>
```

It reads the newest transcript (`--prefix` to name one), prints the record as one
JSON line, and that line is the decision's `context`, unedited. **Exit 2 means no
record yet:** it prints why (a PR this session opened or merged that `--prs` does
not name, a `self` or `ask` PR with no merge call here, an `ask` with no ask counted)
and nothing on stdout; fix the inputs, never the JSON by hand. The transcript
checks what it can see: every PR this session opened (`gh pr create`, `gh api` POST
`…/pulls`) or merged must be in `--prs`, keyed by repo and number; a merge call whose
result shows no merge is named in `--prs` (it did merge) or `--not-merged`; and
`--cards` names at least as many cards as the session filed. A merge call with no PR
number is counted in `unchecked_merges`.

| Field | Source |
|---|---|
| `session` | `--session`: this session's URL; the archive also writes it as the handoff's `meta.session`, which is how the next entry finds this record |
| `date` | UTC date of the archive |
| `kind` | `--kind`: a data batch: its `ops.change_batches.kind`; else the goal line: a ledger item is `upkeep` unless the goal marked it `direction` |
| `asks` | AskUserQuestion and `ask_user_input_v0` calls in the transcript, plus `--asks-prose` for questions put to Baylee in prose: the script never counts prose, the archiving session adds them by hand (the transcript cannot tell a prose question from prose) |
| `refusals`, `refused` | tool results carrying a permission or classifier refusal, or his rejection of a tool call, each refused command in `refused` |
| `merges` | PR merge attempts (`gh api -X PUT …/merge`, `gh pr merge`, git-ops merge), whatever their outcome: one per PR a call names, so a `for n in 100 431; do …` loop or two chained merges count two, each with the outcome its own success line or the call's answer shows; a failed attempt retried to a merge stays in the count but needs no `--not-merged` |
| `prs` | `--prs`: **every PR this session opened, merged or left for his tap**, with how it stands. `self`: the session merged ruled upkeep, no tap. `ask`: the session merged under his answer (close-at-land's merge request). `github`: he merged it himself. `pending`: ready and waiting for his tap at archive. `open`: a draft the work continues on. `tapped` is `ask`, `github` or `pending` |
| `start`, `opening_chars` | from the transcript's first human message (meta records, compaction summaries and "being continued" openers skipped): `pasted` only on positive evidence of a printed prompt (a `Go:` sentence at a line start or after `lane X:`, a dispatch prompt), else `typed`; `none` when there is none, and always for a routine (its prompt is not his). The length rides beside it |
| `interrupts` | `asks + refusals − merge-call refusals + github/pending PRs + cards + 1 for a pasted start`: a refused merge costs him its tap, counted once on its PR (an ask, or `github`/`pending`); a merge under his answer is inside the ask; ruled upkeep costs nothing |
| `calls_logged` | `--calls`: Grove decisions this session logged at rung 3 (not the record itself, not reversals) |
| `cards`, `tasks_for_baylee` | `--cards`, `--tasks`: Grove ids filed this session |
| `cache_read_m` | the session's cache-read tokens in millions by model family. The weekly read's S10 line sums it per day (`ops_read.py`) |
| `source` | `transcript`; an entry stub is `no-transcript` (At entry, below) |
| `lane` | `--lane`: in a lanes repo, the lane the session worked (`"a"`); the record also takes the tag `lane-<x>`, which is how dispatch finds each lane's last session (session-start `references/dispatch.md`). Omitted outside lanes and for a dispatch record (tag `dispatch` instead) |
| `global_reads` | the `.claude/global/` detail files the transcripts show read (a Read call, or a Bash `cat`/`head` of one; sub-agents included), in first-read order, each once, with its bytes on disk now (`null` when not found); `[]` when none. The global-rules lookback reads which files sessions open (`docs/global-rules-core/DESIGN.md` §7.3) |
| `opening_hash` | eight hex characters of the opening message with white space collapsed; equal to a dispatch record's prompt `hash` when he pasted that prompt unchanged |
| `dispatch` | `--dispatch <file> --lanes <declared lanes>`: a dispatch run's own block, what it printed (every lane's state, each prompt with its text, `first` print time, `since` the first offer, `offered` count and hash, his steps, his calls, the waiting and running lines, the cleanup); the next dispatch reads it to tell a prompted lane from a ready one (session-start `references/dispatch.md` Step 4) |

**What reads it.** The weekly read's "Counter" line (`ops_read.py`, Budgets) counts
the week's whole records (record 2, built by `--record`), sums their interrupts,
starts and PR taps, and, over every record with a cost (record 1 included), prints
the process share: cache-read of ops sessions and lane H. Record 1 (written by hand
before 2026-10-28) still counts for S1, S2 and S10. Under it, "Dispatch prompts"
counts the week's dispatch runs' printed prompts (ready lanes, once per session),
how many were pasted unchanged (a record whose `opening_hash` equals a prompt's hash,
logged after its first print) and the strict count of `docs/dispatch/DESIGN.md` §1.2; and
"Lane overlaps" names a lane's session that logged again after another session of
the lane (a restated record still counts as a time it logged). Both report-only.

**No transcript at all** (a surface without the harness): count asks, refusals and
merges from the conversation, `source: self-reported`, `cache_read_m: null`,
`record: 1`. The weekly read shows it as not whole. Never grade the asks (no
"needed" field: a session cannot judge its own asks).

**The call.** `grove_log_decision(decision="session-record <date> <repo or slug>:
asks A, refusals R, merges M, calls L, cards C", project_ref=…,
context=<the JSON>, tags=["session-record", "lane-<meta.lane>"] (the lane tag
from the baton's `meta.lane`; in a repo without lanes the list is
["session-record"] alone), confidence="high", reversible="yes", rung=3)`. Then
read it back once: where `GROVE_TOKEN` is set (Code, routines), run
`python3 .claude/skills/chat-archive/scripts/session_report.py --check-record <full decision id> [--lane <x>]`
(exit 0 = the weekly reads count it; "cannot read" is a failed read, so retry it and do not log again;
"superseded" means a newer record already counts, so do nothing); in chat, `grove_get` and check `context`
parses and the tags carry the lane. On any other exit 2 or a failed check, log the record again with
`supersedes=<first id>` (the weekly read counts a superseding record once;
five lane A records of 2026-10 missed the tag when it was a parenthesis, and in
the week to 2026-11-03 four had a null or prose `context`, one hiding 142.5M
from S10: ledger 6e5aa00e).

**No close without it.** The archive does not write the summary (Step 4), the
Next-step line or Step 9's write-back until the record's id is in hand. If
Grove refuses twice and a work PR is still open, its handoff carries the record
JSON in a top-level `pending_record:` field (the baton that does not depend on
Grove), the summary says "Session record pending: Grove refused (<error>)", and
the next session's entry logs it. With no work PR open (no PR is opened for a
handoff alone, close-at-land "Land-at-push"), or in a session-only chat, the
archive puts the JSON in the response and says the next entry will write a stub.

## Contested calls

Rung-3 calls are logged, not sampled for Baylee: the sampled list and the signal
that counted reversals against it are retired (Baylee, 2026-11-09, bcbd89f4: "isn't
adding value"; history in `fairbay/ops` docs/decision-routing/DESIGN.md §3). Every
call stays reversible by his note (Reversals, below).

**Contested calls are shown, never batched.** A rung-3 call made against a reviewer's
blocking or high finding, against what a card for it would have recommended, or on a
reading of one of his rulings that its words do not plainly settle (when he is not in
the session to ask) gets the tag `contested` when it is logged and is listed in the
Step 4 summary and the Grove session line (9b) under **Contested calls:**, one line each:

```
- 5f2c1a90 — <the decision's first 90 characters> — reply "reverse 5f2c1a90" to undo
```

None → no heading. No batched list of calls is put to him at once (becb3a31).

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
- **Needless ask.** When Baylee answers an ask, a task or a parked item routed
  to him with "no need to ask" in any words ("why not just do it", "you could
  have done that"), the session that receives it, or the archive counting asks
  at Step 3e, logs one decision tagged `needless_ask` and `table-row-<n>` (the
  row that sent it to him; `table-row-unknown` when none did), `project_ref`
  `fairbay/<repo>`, the item and his words in `context`, then does the work.
  A card he resolves by note is a wrong question above, never also a needless
  ask (one incident, one count). The weekly read counts needless asks with the
  wrong-question cards (S5): a postmortem line each, and a card when two land
  on one row where the repo's policy sets `same_row_card` (ops does; MBN does
  not). Decision-table tidy, fairbay/ops
  docs/decision-routing/table-tidy/DESIGN.md (Grove d0f4f58d).

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
   `--pairs <file>` when the pairs output is at hand, and `--tasks <file>` with
   a dump of the batches whose follow-ups changed since the record was written:
   for each batch included, **all** of its tasks, every status, dropped ones
   too (one `grove_list_tasks(tag="from-<id>", compact=false, limit=100)` per
   batch, concatenated into one JSON array). `--tasks` replaces the follow-ups
   only of the batches the dump holds a task for and keeps the record's
   snapshot for the rest, so a dump of the new batch alone leaves older leaks
   in place (MBN guard.mjs since c1352d0a; a repo whose guard.mjs header still
   says it REPLACES every batch's follow-ups needs a dump of every batch in the
   record). stderr names both sets and any follow-up the record lists that the
   dump lacks: a partial dump for that batch, so dump it again in full. The
   verdict is stdout's one line; never capture it with `2>&1`. Exit 0, 3 and 4 are verdicts
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
replaced by the next batch's migration number: one more than the highest
`mNNNN` in any of (1) `ops.change_batches` (read it), (2) the content branches
(`git ls-remote --heads origin 'claude/data-*'`; since PLAN Step 27 a content
batch never merges, so its id is never on main), (3) `db/migrations/*_m*.sql`
on main and on every open PR's head (a schema file in a draft claims its id),
(4) `scripts/m*/` on main; or the number the plan names for the next batch.
The next session checks the id is still free before its first commit (another
lane may take it first; ops d13fbd48). When the rule and the plan disagree,
write no Go: name the mismatch in the Next-step line for Baylee to settle. Read the sentence from the file,
never from memory: what it covers is Baylee's consent and changes only by his
ruling.

## PR subscriptions

For every PR this session opened or was subscribed to that stays open after it (a
draft later sessions continue, a branch waiting on a card, a PR left for his
tap), call `unsubscribe_pr_activity` once per PR before the summary: a CI event on
it otherwise wakes the finished session and spends a turn (2026-11-03, MBN #446;
ops 2a9021d0). Not for a PR that merged or closed here (the subscription ends
itself), or one Baylee asked this session to watch.

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
