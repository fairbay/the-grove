# Dispatch — one turn that reads the lanes and prints what Baylee does next, lane by lane

For a repo whose `.claude/landing.yaml` declares `lanes:` (MBN). Grove task
cb0d5901: the chat that planned the lanes became the dispatcher by default, and
every "check on the sessions and give me prompts" turn paid for its whole
context. Everything that turn read is in Grove and the repo, so a fresh session
can do it in one turn and then be thrown away. Rules for what dispatch may
clean up: `fairbay/ops` docs/lanes/DESIGN.md §8. The output's order, the
lane-state model and the record's block: `fairbay/ops` docs/dispatch/DESIGN.md
(Baylee's direction, task a830496b, 2026-11-05).

## Contents

- Trigger
- Step 1 — Read (one pass, no prior chat)
- Step 2 — Clean up (upkeep only)
- Step 3 — Output (this order, nothing else)
- Step 4 — Record and stop

## Trigger

"dispatch MBN", "check the lanes", "what's next on MBN" as the **first message
of a session**. The same words mid-session are chat-status. Dispatch replaces
Phases 0–5: no briefing, no work queue, no "then wait". It does no lane work
itself, even when one lane's item looks small. The one exception is his reply
`go H` (Step 3), which turns the dispatching session into lane H's session.
Attach the repos of every lane that can run in place: for MBN, that is MBN,
grove and ops (lane H's; Baylee, 2026-11-09, decision 45e6dfb0). Run it in a Code session: a chat
may have no transcript on disk (ledger 521aac68: none in two chats on
2026-11-03), and then its record is self-reported and the weekly read cannot
count it; a chat that runs it still writes Step 4's block by hand.

**If you are about to read a prior chat (`recent_chats`,
`conversation_search`) to find out where the lanes stand, stop.** The row, the
batons, the PRs and the session records are the state; a chat is a lossy copy.

**If he replies in a dispatch session about one lane ("d task is done", "check
C", "A isn't running") and you are about to check only that lane, stop.** Such a
reply is a second dispatch (Step 4): every read of Step 1 again, the freed read
with `--freed-since` the previous turn's record and the item his reply names, and
a record that supersedes the previous one. He does not have to tell a finished
item that frees only its own lane from one other lanes wait on; the freed read
does (df2da0a4: on 2026-11-09 a one-lane answer to "d task is done" missed that
lane H's f5434f3a waited for the ruleset just finished, record 675410ba). The
replies `reprint lane X` and `go H` (Step 3) are not dispatches.

## Step 1 — Read (one pass, no prior chat)

Make the reads in parallel where the surface allows. Code: the CWD clone
(`git fetch origin main` first; read files as `git show origin/main:<path>`).
Chat: attach the repo with access `"read"` and use git-ops. Do not clone for
these reads: a clone raises an approval card for Baylee (global rules, "Shell
Commands That Raise Approval Cards"); read another repo's files and PRs with
`gh api`, batched into one shell call. Attach with `"push"` and clone only when
Step 2 has a cleanup item that needs a push (MBN 2026-11-03, Grove 95e47e55:
two push attaches and two clones for a read-only pass).

1. **Project row:** `grove_list_projects(slug=<slug>, compact=false)`. Lane
   lines are the `next_actions` items that start `Lane <X>,` for a lane
   `landing.yaml` declares (a `Lane G,` line for an undeclared lane is not a
   lane: its steps show only as his steps a lane waits on), plus the `CARD …`
   lines (built work waiting on his answer; close-at-land "File a card"), plus
   the `HOLD (` lines (a ruling of his that pauses a kind of work until an
   event: what is held, what releases it). Keep `updated_at`.
2. **Open PRs:** Phase 0's report (`pr_state.py report --repo fairbay/<repo>`
   without `--table`, the dispatched repo's own copy; chat: the GitHub list),
   and for a lane whose line names another repo (MBN's lane H: `fairbay/ops`),
   the open PRs of both infrastructure repos, `fairbay/ops` and `fairbay/grove`
   (read 7 passes them, with the dispatched repo's, to `--owned` as `repo#n`). For each PR, its lane: the
   `handoffs/lane-<x>.yaml` it changes (`pulls/<n>/files`, as lanes.md Exit 3),
   else "lane <X>" in its title or branch. None of these → "outside every lane",
   whatever lane tag its `owns:` task carries (02411f97: a no-lane draft read as
   lane A's through its task's tag, twice on 2026-11-09). A
   draft PR whose title ends "(drafted by data-draft-r)" is the routine's, not
   the lane's running evidence: it feeds only the routine rows below. Branches
   of data batches: `git ls-remote origin 'refs/heads/claude/data-*'` and each
   such branch's head time (`gh api repos/fairbay/<repo>/commits/<sha> --jq
   .commit.committer.date`) for the batch id the data lane's START HERE names.
   Phase 0's promotion of merged `LANDING` markers runs as usual (open tasks
   and the row's `LANDING` lines); Phase 0's previous-session record check
   does not (dispatch has no single previous session).
3. **Batons:** each `handoffs/lane-<x>.yaml` of the declared lanes: `meta`
   (session, generated, landing) and every `next:` item (the first is START
   HERE; the later ones are what the escape in the state table reads; `parked:`
   is not read: it holds what is not next). For a lane with an open PR (step 2,
   draft or ready), also read the baton at the PR's head
   (`gh api repos/fairbay/<repo>/contents/handoffs/lane-<x>.yaml?ref=<head_ref>
   -H "Accept: application/vnd.github.raw"`): a lane session commits its baton
   on its branch, and main gets it only at the merge. The newer
   `meta.generated` is the lane's baton. When the PR's newest commit is newer
   than that baton too, the lane line says so ("#n has commits after its
   baton"). (MBN 2026-11-03: lane B's newer baton sat on draft #378 and said
   the lane waited on Baylee; dispatch read main's and sent a prompt.)
4. **Decisions:** `grove_list_decisions(project_ref=<repo>, current_only=false,
   limit=100)`, compact (ids, tags, `created_at`: enough for the state table).
   A lane's last record is the newest of: its records tagged `lane-<x>`, and
   the untagged records newer than that one (or than its baton's
   `meta.generated`) whose `context.session` or `context.lane` matches the
   baton, read with `grove_get`. None → "no record" (its last session is the
   baton's `meta.generated`; nothing follows from it). A decision with a record
   from the same lane after it is finished work, never "running". `grove_events` has no project
   filter and no tags, so it cannot say which lane moved.
5. **Cards:** `grove_list_adjudications(list=<slug>, status="open")` and
   `(status="done", limit=50)`: answered and dropped are not the same, so a
   card is answered only when it is in the done list. A card gates a
   lane when its tags carry `lane-<x>` or its question names an 8-hex id the
   lane's first open item names (cards from a design turn cite its task:
   "Conditional cards (2cdca464), …"). The card's own id in a lane line is a
   carry, not a gate. A card that gates no lane is still his call (Step 3,
   "(no lane)"), unless his answer to it is already on record (a decision
   quoting his option for that card, usually tagged `baylee-ruling` and the
   card id): that card is answered, and Step 2 records it and does its
   follow-ups (ruling f49acabc). Tagging a card answered by note
   (`wrong_question`) is the consuming lane's job, not dispatch's. For a lane
   whose line names another repo, also `grove_list_adjudications(list="ops",
   status="open")` and the same for `list="grove"`: read 7 passes their ids to
   `--cards-open`.
6. **The last dispatch:** the newest decision tagged `dispatch` in read 4's
   list that is not superseded and whose `context.session` is not this
   session, read with `grove_get`. Its context's `dispatch.prompts` (lane →
   `text`, `first`, `since`, `offered`) feeds the `prompted` row and the offered
   count below. No such decision in the list, or no `dispatch.lanes` in its
   block (the hand-written block of 2026-10-28, a run before 2026-11-05) →
   nothing is prompted. A second or later dispatch turn in the same session
   uses the block its previous turn wrote instead (the same facts, from this
   session); its record supersedes the previous turn's, so a later session
   reads the newest.
7. **The list:** `docs/ISSUES.md` on main (Code: `git show origin/main:docs/ISSUES.md
   > <scratch>/ISSUES.md`; chat: `gh api repos/fairbay/<repo>/contents/docs/ISSUES.md
   -H "Accept: application/vnd.github.raw"`), then
   `python3 .claude/skills/session-start/scripts/issues_next.py <file> --lane a --lane b …`
   for every declared lane. It prints, per lane, the highest rank in the lane's
   row of "How lanes pull from it" that waits on nothing (its Waits-on cell is
   "—", its entry carries no "after", "once" or "when", the row is not struck),
   and the ranks it skipped with their reasons; a lane with no row (lane H)
   prints "not on the list". A Waits-on cell that blocks only part of a rank
   still counts as a wait (the script fails safe) until the lane's row carries
   the free part as its own entry marked "(now)" ("11 (m1360, now)"), which the
   script reads as free. When a baton's START HERE names a rank other than the
   pick, `--rank <n>` prints whether that rank is free or what it waits on. The
   script is the count; dispatch never reads the table by eye (f21b91ed step 1;
   Baylee's "Fine" to the order, 396d026e). A repo with no `docs/ISSUES.md`
   prints no list line.

   For a lane whose row line names another repo (MBN's lane H), the list is
   the infrastructure queue (`fairbay/ops` docs/infra-queue/DESIGN.md): the
   open tasks of Grove lists `ops` and `grove`, read by the script itself with
   `$GROVE_TOKEN` (no task rows relayed through tool arguments):
   `python3 .claude/skills/session-start/scripts/infra_queue.py --fetch --owned <read 2's open PRs as repo#n: ops#139,grove#24,medicaid-benefits-navigator#545> --cards-open <read 5's open card ids of lists ops and grove>`.
   It prints the pick, its order line, `notes:` (a task owning a PR not open,
   a card answered but not landed: Step 2's "Work found undone") and every
   skip with its rule (the rules: the script's docstring). The pick, notes and
   skips go to the record's cleanup list ("H: queue pick 0eeb2807; START HERE
   e6a91e53"), never printed. `pick: nothing queued`, or `pick: queue unread
   (<reason>)` with exit 2 (no token, as in a chat; an HTTP error; a list at
   the read's cap), leaves the lane in the state its baton gives it, and the
   cleanup says "H: queue nothing queued" or "H: queue unread (<reason>)".

   **The waits** (Grove 6c8059b0, `fairbay/ops` docs/deps-check/DESIGN.md):
   `python3 .claude/skills/session-start/scripts/deps_check.py --issues <the same file> --fetch --batons handoffs --report`
   looks up every id the list's Waits-on cells, its waiting lane entries and the
   row's lane lines cite as a wait, and names each that is STALE (not an open task
   of the lists read nor a decision), UNOWNED (no lane tag, not Baylee's), UNQUEUED
   (its lane plans it nowhere) or MISLABELED (cited under the wrong lane), and each
   rank held by a "—" cell with more text (CLOSED_NOT_FREE). Its first line and
   every finding go to the record's cleanup list ("deps: 15 cited; ok 15"), never
   printed, each with the lane whose places carry it. A finding changes no lane's
   state: STALE can also mean another list's task or a mistyped id, so a wait is
   over only when the lane that cites it says so in its next archive (lanes.md
   Exit 7). `deps: unread (<reason>)` (no token, as in a chat) changes nothing.

   **What finished, and who waited on it** (task df2da0a4, `fairbay/ops`
   docs/partial-dispatch/DESIGN.md): the same call takes
   `--freed-since <read 6's record created_at, minus one hour>` (the previous
   turn's, in a second turn; the hour covers what finished while that run read,
   and a repeat is harmless) and `--item <x>` for each thing the Grove log does
   not hold: a batch published since (`ops.change_batches.published_at`), a PR
   merged since (`#n`, with the `#`; read 2), an id or batch his reply names. It
   prints `freed: N finished since …` and one line per place whose wait phrase
   names a finished item, by id, by token, or by the gate a finished task is
   tagged with (`gate-g9` → "waits for G9"; one finished task of a gate is not
   the whole gate). A hit is a finding for the lane, not a state change: the
   lane's other waits still hold. For a lane printed in Start, its hits not
   marked `[record only]` (those come from a task's notes, which are as often
   history as a wait) go on its prompt's constraint line as one sentence naming
   at most three waiting ids: "Also check f5434f3a: 63346727 (G9) finished."
   Every hit, and any beyond three, goes to the record's cleanup list, and so do
   hits for lanes not in Start. A carried (prompted) box stays unchanged. `freed:
   …; partial (<reason>)` still counts what it read; the cleanup names the
   reason.

8. **Lookbacks:** `grove_list_tasks(tag="lookback", status="open", limit=100)`.
   A lookback is a check, filed when a change landed, on how that change is
   going (global rules, Decision Ladder rung 3). One whose `due_at` is past
   joins its lane's work as normal: it goes on that lane's prompt
   constraint line ("Also lookback <id 8>, due."), with the lane named by its
   `lane-<x>` tag. One that is not yet due, or names no declared lane, is not
   printed. Either way, the record's cleanup list names each due one
   ("lookback <id 8> due: lane H"). A lane that is not ready this run carries
   its lookback to a later run. Lane H needs no line: its queue (read 7)
   holds a task until its `due_at` and then picks it in order.
9. **Lane state, by script** (Grove 6c8059b0 items 3 and 6, 02411f97; `fairbay/ops`
   docs/lane-state/DESIGN.md): with read 2's report saved as JSON, read 3's
   PR-head batons in a directory, and the issues file of read 7,
   `python3 .claude/skills/session-start/scripts/lane_state.py --issues <file> --batons handoffs --prs <report.json> --head-batons <dir> --fetch --repo fairbay/<repo> --session <this session's URL>`.
   It applies the state table's evidence rows (the green ready PR's merge,
   running, prompted, call, held) and the data slot by rank, in the row's lane
   order, and prints each lane's state, the evidence that set it, and `check:`
   lines for what it does not settle: a wait its START HERE names, a step of
   Baylee's, a time not yet reached, a hold's scope and release, a ready PR
   outside G3, the runner's open draft, a lane with no START HERE. It also
   prints, per lane, the one Go a prompt may carry (`go:`; Step 3 "Go") and a
   `row-line:` check when the row's lane line is not in step with the lane's
   baton (it does not name the session that wrote the baton). The script says
   which is newer from the lane's session records, the line's "Last done" date
   and, last, the PR numbers the line cites. A line shown older
   is not the lane's START HERE: the script reads the baton's first item
   instead, and the check carries the sentence that goes on the lane's prompt,
   verbatim ("The baton on main (#n) is newer than the row's lane <X> line:
   follow the baton, and write the row line at the archive."; d9692d9f: read by
   hand on 2026-11-12, and the same stale line stopped data-draft-r that
   morning). **For those
   rows its state is the answer:** read by hand only a lane's `check:` lines
   (each names the table row that then applies) and its escape; a state that differs from the
   script's goes in the record's cleanup as "dispatch's reading (overrides
   lane_state: <lane> <its state> → <yours>, <why>)", never silently
   (8649cf1c read lane H running and d4b8a8a2 ready, on the same evidence).
   `lane state: unread (<reason>)` (no token, as in a chat) → the table by
   hand, as before, and the cleanup says so.

**Finding a task by its short id.** `grove_get` needs the full UUID and
`grove_list_tasks` has no id filter: `grove_list_tasks(q=<8 hex>, compact=false,
limit=10)`, kept where `id` starts with the prefix; no hit → `q=` two words of
the title the line gives, same check. Not found → treat the item as open and say
so in the lane's line.

**Lane state, per lane** (first match wins; "fresh" means under 6 hours old).
The state names the group the lane prints in (Step 3).

| Evidence | State → group |
|---|---|
| A ready PR of the lane carries its close-at-land commit (Phase 0 row G3: checks green), its `ci_checks` finished at least 10 minutes ago (the check runs' `completed_at`), and nothing was pushed after: its session finished and waits on the merge, whatever lane decision is fresh (that decision is the close-at-land's own; Baylee, 2026-11-10, aaf31319: lane C sat idle on a green #562 read as running) | Ruled upkeep (Step 2's ready-upkeep bullet) → Step 2 merges it, then the lane is judged on the rows below from its baton on main, and a Start entry notes "the old lane <X> session is finished; close it". Otherwise **your step** → Your step: the merge, with its link and the recommendation |
| A draft PR of the lane with a fresh head (`head_age_days` < 0.25), or a fresh decision tagged `lane-<x>` (not a record, not a Baylee ruling, not logged by a dispatch session: 02411f97) newer than the lane's last record and its baton | **running** → Running (name the PR or decision) |
| The last dispatch's block (read 6) carries a prompt for the lane whose `first` is under **2 hours** old, and nothing since that `first` shows the lane archived: no newer record tagged `lane-<x>`, no PR of the lane merged after it | **prompted** → Start: its carried box printed again, unchanged, with the note "printed HH:MM; skip it if that session is open" (Baylee, 2026-11-10, aaf31319: "always reprint if you don't see the session running"); its prompt is carried in Step 4's block unchanged (same `text`, `first`, `since`, `offered`) and the record keeps the state `prompted` |
| A ready PR of the lane that Step 2 may not merge (direction, or a class that is unclear) | **your step** → Your step: the merge, with its link and the recommendation |
| Its START HERE item is Baylee's own step ("Baylee reviews …", a page or list he answers, a real-world step), its precondition, when the line states one ("when …", "once …"), holds on the reads, and nothing on record shows it done | **your step** → Your step: the step with its link. Escape below |
| An open card gates it (read 5), or its START HERE waits on open cards ("once the cards are answered"), or a `CARD <id>` row line or an open `card-open` task names its built branch (close-at-land "File a card") | **your call** → Your call: the card ids and the link, with the branch. Escape below |
| Its START HERE waits on another lane's item ("wait for lane D's e70fc434") that is still open, with no alternative given, or on his step whose precondition does not hold; or its line names no open item; or its baton cannot be read | **waiting** → Waiting, not on you: the item and its lane, "nothing queued", or the read error. Escape below |
| The data runner is on (read 4 holds a decision tagged `data-apply-r` under 7 days old; Grove d53020da: data-apply-r checks and applies data-draft-r's drafts), lane A is the lane it drafts for, and the batch task of an open draft PR titled "… (drafted by data-draft-r)" (read by its `owns:` line) carries no `runner:` line and the PR is under 24 hours old, or a `runner: claimed` line under 12 hours old, or `runner: waits-publish #<n>` | **running** → Running: "the runner, #<n>" (it holds the data slot for every other data lane). The other `runner:` lines: `applied` (the batch is in; the draft stays open until the publish, holds nothing, and lane A is judged on the rows below from its baton, so the runner's next draft or the row's START HERE decides); `waits-pile` → **waiting** ("the runner's #<n>, after the next publish"); `stopped <step> <card>` → its card (tagged `lane-a`) gates lane A as any card does, and once answered `session` the row below applies with the constraint "data-apply-r stopped at <step>: card <id>." A draft 24 hours old or more with no `runner:` line is stalled: the row below applies |
| It is the lane data-draft-r drafts for (MBN lane A: the brief's precondition 2 reads lane A's START HERE), its START HERE batch `<id>` has an open draft PR titled "… (drafted by data-draft-r)", and nothing shows that PR's batch applied | **ready** → Start: the apply session for that PR, constraint "Apply and publish from data-draft-r's draft PR #<n>." (the Go verbatim as always, or none); never a prompt that drafts the same batch (5737a18a) |
| The same lane, no such PR yet, and the routine holds `<id>`: lane H's or the row's line says data-draft-r drafts `<id>`, or a `claude/data-*-<id>` branch has a head under 6 hours old (read 2), and no session record of the routine's run on `<id>` is logged yet (read 4: a decision beginning `session-record` that names `data-draft-r <id>`). Once that record is logged, the run has ended: a branch it left with no PR is the routine's stopped draft, and lane A is judged as any data lane, its prompt carrying "Continue from data-draft-r's stopped <id> draft on <branch>; its record <id 8> names the stop." (2026-11-05: run 3 stopped at the live step, record 290d34c1). An older branch with no PR and no such record is not the routine's (the proxy cannot delete branches): this row does not apply, and the lane's prompt carries "Branch <name> has no PR: reconcile it first." | **waiting** → Waiting, not on you: "the routine's draft of <id>". While this row holds, the routine counts as a running data lane for every other lane (Step 2's exclusion) |
| It is a data lane (Step 2's definition) while another data lane is running or prompted, the routine's draft included (the row above); or it is the second of two ready data lanes (Step 2's tie-break) | **waiting** → Waiting, not on you: "after lane A archives" or "after the routine's draft of <id>". Escape below, to an item that is not a data batch. A data lane whose batch names the id the routine holds (lane B's batch 1 named m1351 on 2026-11-05), when it is prompted later, carries "<id> is data-draft-r's: check the next free id before you draft." |
| A `HOLD (` row line (read 1) names the work the lane would do (its START HERE item, or the item the escape picks, falls in a kind the line holds: "every data batch", the lane's id, its task), the release it names has not happened on the reads (the PR is not merged), and the line does not name that work as not held | **held** → On hold: one line per hold, naming the held lanes and what releases them; no prompt box, however ready the lane is (Baylee, 2026-11-10, 601dfdb9: "even though we can do them, we shouldn't right now"). The escape applies first: a later item the hold does not cover makes the lane ready for it |
| Otherwise | **ready** → Start: give a prompt |

**The escape** (one rule for the your-step-on-his-own-step, your-call and
waiting rows, the second data lane's included, where the item picked must not be a data batch; not the
ready-PR row, not the routine's row): when the lane's
line names a later `next:` item that does not depend on what the first item
waits on, the lane is **ready for that item**: its entry goes under Start with
a prompt that says `starting at <id>`, where `<id>` is the first 8-hex id that
item names (lane C's "Then C5 network-adequacy 615b2152; C6 …" → 615b2152;
lane H's "Then, ordered by MBN leverage: the guide-gap counter line (9a9911a9
item 4(iii)); …" → 9a9911a9), and the prompt's `(<why>)` names what the
first item waits on (the step, the cards, the other lane's item). An item
depends on the wait when it names the thing waited on (its id, its lane, "the
codes") or is introduced by "after", "once" or "when" that thing; "then" alone
is order, not dependence. The reading is dispatch's, at medium confidence: the
record's cleanup list says so ("dispatch's reading: 615b2152 does not wait on
6c527868"), and a lane session that finds otherwise says so in its baton. A lane whose first
item is done (its PR merged, its task done) prompts the same way.

For a lane with the infrastructure queue (read 7, lane H) the starting item
is, in this order: START HERE when it names a free open item; else the
baton's first later `next:` item that does not depend on the wait (the escape
above); else the queue's pick (`starting at <pick id>`). The wait goes on the
constraint line only when it bears on the item. A hold START HERE states for
the lane itself ("the only lane H work until green") is escaped only when
every item the hold names is tagged or owned by another lane on the reads;
otherwise the lane stays waiting on it and the cleanup names the item that is
lane H's own. An empty or unread queue leaves the lane where the baton puts
it. A lane H archive names the pick in START HERE (lanes.md, Exit), so the
three converge.

**`first`, `since` and `offered`** (the prompt entry in Step 4's block, read
back by read 6). For a ready lane: when the last block carried this lane's
prompt (as `ready` or `prompted`) and nothing since that block's `first` shows
the lane archived (no record tagged `lane-<x>`, no PR of the lane merged), it
is offered again: `offered` one higher, `since` carried, `first` this run's
time; otherwise (the lane was in another state, or a record or merge came
after `first`) `offered` is 1 and `since` and `first` are both this run's
time. For a prompted lane all four fields are carried unchanged. This run's
time is `date -u +%Y-%m-%dT%H:%MZ` (the script refuses a `first` or `since`
without the Z). The count lives in the record, not on screen (Baylee,
2026-11-07): the weekly read is where a lane he keeps skipping shows; the lane
stays in Start (ready work is ready).

**Residual risk, stated.** A session that runs more than two hours with no
PR push and no decision reads ready again after its `prompted` expires, and
its prompt prints a second time with the offered count up; a lane-tagged
decision or a push keeps it running. The other invisible case is a session no
dispatch prompted; it is not printed (Baylee, 2026-11-07: only what he needs to
run the prompts), and a lane he opened himself is his to know.

A stale decision (6 hours or older) with no record after it means a session
ended without archiving, not one still running: the lane is judged on the rows
below. When such a decision is tagged `lane-<x>` and is also newer than the
lane's baton, the baton missed that session's work: a prompt for the lane gets
the constraint line "Reconcile first: <decision ids> came after the baton with
no record; read <the PR's head, if any> before START HERE.", and the lane line
names them. A dependency with an alternative ("wait for e70fc434, or name each new
card by hand") is ready, and the alternative is the prompt's constraint line.
A `CARD` row line whose card is answered does not hold the lane: the record's
cleanup says "card <id> answered; the row line is stale" (and Step 2 lands it). Cards that
the START HERE item itself produced (a design turn delivered on its PR) leave
that item with Baylee; the lane is ready for the line's next item the cards do
not gate, and the prompt names it.

The row's lane line and the baton disagree → the newer wins (lanes.md,
Layout); read 9's `row-line:` check says which is newer where it can tell
(older, newer), and "names another session" where it cannot: only then read
the two by eye. A lane session that has opened no PR and logged nothing yet, and that
no dispatch prompted, looks ready (the residual risk above).

## Step 2 — Clean up (upkeep only)

May do, in this turn, each as upkeep (the repo's `.claude/policy.json`, upkeep row):

- **A dirty upkeep PR of a lane that is not running:** merge main into its
  head (Code: fetch the branch, `git merge origin/main`; a merge, never a
  rebase), resolve a handoff-only conflict with
  `node .claude/skills/chat-archive/scripts/handoff-merge.mjs --lane <x>`, push.
  Any other conflicted path: stop, leave the PR, and list it in the record's
  cleanup ("#n dirty on <path>: its lane's next session merges main").
- **A ready upkeep PR** whose Go or ruling is on record and that meets
  close-at-land's three ruled-upkeep conditions (G3 green, one revert undoes
  it): merge it and promote it as close-at-land "Merge request" step 3 says.
  A refused merge call becomes his step in Step 3 (counted, S2).
- **A superseded draft:** close it when its work is already on main (a
  `Merged #m` line in the row names it as included, or its `owns:` task is
  done or dropped), with one comment naming what superseded it. Closing is
  reversible (reopen). **In a chat session with a repo attached the close is
  refused** (the classifier's "External System Writes", ledger ef32bdd3: #104 twice,
  the comment too): make no close or comment call there; list it as his one-line step
  in Step 3 ("Close #n on GitHub: the Close pull request button at the bottom of the
  page; its work is on main via #m") and never retry it reworded. A Code session
  still closes it; a refusal there is counted (S2).
- **His answer, given in chat or on record but not applied** (Baylee,
  2026-11-04, f49acabc: "if I answer in chat you should take that answer as if
  I'd entered it on the adjudicate page"): record it on the card with
  `sitting.py card-sql --card <id> --option <x> --notes "<his words; the decision id>" --at <when he answered> --via chat`,
  run with Supabase `execute_sql` on the Grove project, and read it back in the
  done list. Then do its follow-ups in the same turn: the task notes it settles,
  and the row text it made stale (re-read the row, change only that text,
  verify the write by an exact compare). A built branch his yes lands (a
  `card-open` task with a `branch:` line) is landed here as close-at-land "On
  his answer" says: the PR opened ready under his answer, merged when green. A
  plan or doc change it calls for is done here when it is upkeep, else filed as
  a task for the owning lane.
- **Work found undone:** anything the reads show should have been done the
  first time (a step marked open that the record shows done, a follow-up no
  task carries) is done here when it is upkeep, else filed as a Grove task in
  the same turn. It is never put to Baylee as a step of his.

May not:

- mark ready or merge a direction PR, or any PR whose class is unclear: that is
  his step in Step 3; the one exception is a built branch his card's yes lands
  (Step 2's "His answer" bullet; close-at-land "On his answer", claim first), and
  in a chat session with a repo attached that merge call may be refused and
  falls back to his tap (S2);
- re-word, fill in or compose a Go, or copy one from the row's lane line: a
  prompt carries the Go read 9 prints on the lane's `go:` line, verbatim, or
  carries none (Step 3, "Go");
- send a second data session while one is live. A lane is a data lane by the
  item it would work, not by its name (docs/lanes/DESIGN.md: "a lane whose Go
  applies data"): its START HERE item (the START HERE text up to its first
  "Then"; what follows is later items), or the item the escape picks, names an
  `mNNNN` batch to draft, apply or publish, or its row line or baton carries a
  Go sentence (no Go, no apply: `.claude/policy.json` `harness.go`). Data lanes share the live data set, so each is exclusive with
  every other: at most one data prompt per dispatch, and none while a data lane
  is running or prompted. When two are ready, the slot goes by rank (Baylee's
  eaa8913f: "I don't want a low-priority task to kick off just because it can"):
  the START HERE item's ISSUES rank (its own "rank N", else the lane's list
  entry naming its batch or id), then a health red (1eb2c1f1), then off-list;
  equal keys by row order (read 9 prints the order). The second is waiting
  ("after lane A archives"). A data START HERE that a lower rank or an
  off-list item puts ahead of the lane's free list pick is a correction for
  that lane (read 9's `rank-order` line): on its prompt's constraint line. A lane whose item says "No data batch" or is a
  library, tooling or design session (MBN lane E's library work) is not a data
  lane: it is ready beside a running one, with the constraint "Library work
  only: no data batch while lane <x>'s <mNNNN> is open." (5737a18a; three
  dispatches on 2026-11-05 held the then lane F's library session about 26 hours;
  MBN has one data lane, A, since F merged into it, f21b91ed step 5);
- touch a running lane's PR, write any lane's baton, or rewrite the row's lane
  lines (the lane's own archive does; f2826d9d). The one exception is the text
  his answer made stale (above);
- re-file a task's list or project_ref: a filing fault the queue names (read
  7) goes in the record's cleanup list, and the session that works the task
  re-files it.

## Step 3 — Output (this order, nothing else)

**The output is the prompts, plus only what Baylee needs to run them
properly** (his direction, 2026-11-07: "When I do a dispatch I expect to get a
bunch of prompts, and I really only need to know what I need to know to do them
properly"). No line says what a session will do, why a lane is in its state, its
list rank, its offered count or what Step 2 cleaned up: the prompt and the row
carry the work, the record (Step 4) carries the rest. Groups keep the order of
a830496b (what he does, most to least); lanes keep the row's order inside one.

~~~
**On hold** until backlog mode (#602) is merged: A, B and C (data), guide work.

**Start** (paste each into its own new session; they can all run at once)
- **A** · you merge at the end (no Go on record)
  ```
  Work on MBN, lane A: the project row's lane A START HERE line. Apply and publish from data-draft-r's draft PR #511. Archive.
  ```
- **C**
  ```
  Work on MBN, lane C: the project row's lane C line, starting at 615b2152 (6c527868 still open). Archive.
  ```
- **E** · then yours: <his step> <link>
  ```
  …
  ```
- **H** · printed 23:21; skip it if that session is open
  ```
  …
  ```

**Your step:** merge #n, <what it lands, in a few words> (recommendation: merge)
1. Open https://github.com/fairbay/<repo>/pull/<n>
2. <each tap and what he should see, from GitHub's current docs; about how long>

**Your call:** "<card 1's question, in his words>" (recommendation: <option label>)
1. Open https://vault.bayleemiller.org/adjudicate
2. <find the card by that question, tap the option; about how long>

Not now: B, F (wait on lane A). Running: D.
Record <id 8>
~~~

- **Start:** each ready lane's letter and its prompt box. A note follows the
  letter (after " · ", a few words) only when he has something to do around the
  session: a tap or merge it will leave him (no Go on record), his step that
  comes right after it ("then yours: …", with the link), or an order between
  two Start lanes when one truly must go first. Never the session's work, its
  evidence, a recommendation or a ranking ("start here first" read as an order
  on 2026-11-07, and he had rightly started all six at once). A prompted lane
  (no session seen since its box was printed) is in Start too, its carried box
  unchanged and its note "printed HH:MM; skip it if that session is open"
  (aaf31319): he cannot tell an unstarted lane from a quiet one, and a second
  round trip to ask for the box costs more than one line.
- **Your step:** each item as numbered steps with the link and the
  recommendation (global Rule 7, 309b9f9c: the whole step every time, even when
  an earlier dispatch printed it; an id only in brackets after the steps): a ready PR that keeps his tap, a real-world step a lane's START HERE
  waits on, a refused cleanup call (S2); the lane letter in front when there is
  one. Never his step: a card or step his answer on record already settles
  (Step 2 applies it), or work the reads found undone (Step 2 does it or files
  a task). None → `**Your step:** none`.
- **Your call:** each open card that gates a lane or gates none, by its
  question in plain words, with its recommendation and the numbered steps to
  answer it (global Rule 7; the card id only in brackets; a built branch's card
  names what the branch shows). None →
  `**Your call:** none`.
- **On hold:** first, one line per `HOLD (` row line that holds a lane: what
  is held (lane letters, and the kind of work in a word) and what releases it,
  worded as the event ("until #602 is merged"). No prompt box for a held lane,
  and no reason beyond the release. When the release is his step (a merge, a
  card), it is also under Your step with its numbered steps. A HOLD line whose
  release has happened on the reads (the PR merged) holds nothing: Step 2
  drops it from the row as upkeep and the record's cleanup says so. No hold →
  the line is left out (601dfdb9; Grove 0490bec3).
- **Not now / Running:** one line. "Not now" (the state table's "Waiting, not
  on you" group; its quoted reasons go to the record) lists the waiting lanes' letters,
  each with at most a few words when the word helps him know when it frees
  ("wait on lane A"; worded as the event, never a fact that expires before it).
  "Running" lists the letters of lanes with running evidence (state **running**);
  prompted lanes print in Start instead. No copy box for a running lane: a
  second session of one lane is the collision the lanes exist to prevent
  (lanes.md: one session at a time). Either part with no lane is left out.
- **Record:** the last line, once Step 4 has the id.
- **`reprint lane X`** as his reply, in the dispatching session, prints that
  lane's carried prompt verbatim and nothing else; it is not a second dispatch
  (Step 4), re-reads nothing and changes no record (the lane stays prompted
  until the two hours pass). Every prompted lane's box is already in Start
  (aaf31319), so this is a fallback: it prints the same box again. In a later session the reply has no block to read: he runs
  dispatch again.
- **`go H`** (Baylee, 2026-11-09, decision 45e6dfb0): when lane H is in Start,
  its entry's note adds "or reply `go H`". On that reply, after Step 4's record
  is logged, the dispatching session becomes lane H's session. It works H's
  printed prompt in place, exactly as a new session would: the baton, START
  HERE, then the archive into MBN with a `lane-h` record. That record ends H's
  prompted window the usual way, so the next dispatch reads H as running or
  archived, never as unstarted. He pastes H's box or replies `go H`, not both
  (one session per lane). Dispatch's reads stay in context and are not
  repeated. Lookback aaaefdd1 (due 2026-11-23) compares its cost against
  fresh H sessions.
- **Prompt:** at most four lines in one copy box, from the template
  `Work on <short name>, lane <X>: the project row's lane <X> START HERE line. <one-line constraint if any>. Archive.`
  The row stays the source, so the prompt stays short; "lane <X>" in it loads
  the baton (the lane gate). A lane whose line names another repo for its work
  (MBN's lane H: `fairbay/ops`) gets `Work on fairbay/ops for MBN lane H: MBN's
  project row lane H START HERE line is the source. Archive into MBN: update
  MBN's lane H row line and log the record with project_ref
  fairbay/medicaid-benefits-navigator, tags session-record, lane-h.` (ops
  declares no lanes, so neither the lane gate nor a baton path does this on
  its own; ops #87 archived into ops and left MBN's line stale). When the line
  has no START HERE, or its START HERE item is done (its PR merged, its task
  done), left with Baylee (cards it produced, his step) or waiting with a later
  item ready (the escape), name the starting item instead: `… lane <X>: the
  project row's lane <X> line, starting at <id> (<why, a few words>). Archive.`;
  in the other-repo form, `Work on fairbay/ops for MBN lane H: MBN's project
  row lane H line, starting at <id> (<why>), is the source. Archive into MBN: …`
  with the same tail. When the starting item is the queue's pick, the repo is
  the pick's `project_ref` (a filing fault: the project_ref wins, the record
  names it): `Work on fairbay/grove for MBN lane H: MBN's project row lane H
  line, starting at 0eeb2807 (START HERE waits on lane E's 323b4415), is the
  source. Archive into MBN: update MBN's lane H row line and log the record
  with project_ref fairbay/medicaid-benefits-navigator, tags session-record,
  lane-h.`
- **Go:** read from one place, the lane's `go:` line in read 9's output.
  lane_state.py takes it from the Opening line of the lane's baton START HERE
  (`Opening line: "lane F: Go: …"`), the place policy-check (f) holds to the
  repo's `harness.go`, and holds it to `harness.go` again (only `mNNNN`
  filled); it never reads a Go from the row's lane line, which no check holds
  (89437cec; MBN trust chain G12). The prompt is `Work on <short name>, `
  followed by that line verbatim (`lane <X>: Go: …`), its own closing
  "archive." standing for the template's, and a constraint on the second line
  if any. Dispatch never fills the sentence in and never computes a batch
  number. No `go:` line → no Go, and the lane's `check: no Go copied: …` says
  why (the baton carries none; `harness.go` could not be read; its Go is not
  `harness.go`; the row line is newer than a baton whose Go it does not repeat,
  as after an archive with no work PR, whose row line nothing checks); that
  lane's merge falls back to Baylee's tap (S2). On a data lane that is a miss by its last archive
  (close-at-land step 8 writes the Go into the baton; policy-check (f) gates it
  since Grove 6179636b): the Start note says "asks you for a Go", and the record's
  cleanup names the lane's archive. A `check: row Go differs from the baton's`
  is a correction for that lane's archive (the cleanup names it). With `lane
  state: unread`, read the Go from the baton by eye and compare it with
  `harness.go`; never take the row's.
- A lane with an open draft that is not running: the constraint line is
  "Continue draft #<n>." A running or waiting lane gets no new prompt; a
  prompted lane gets none either, only its carried box printed again.
- **Next from the list** (read 7) is not printed. Dispatch still runs it and
  writes each lane's pick in the record's cleanup list ("C: list rank 23;
  START HERE rank 21"); the lane's own session names its rank in its START HERE
  line (lanes.md, Exit 6). A START HERE that names a rank the list says waits
  (checked with `--rank <n>`) is a correction that lane's session needs: it goes
  on the prompt's constraint line ("START HERE's rank 21 waits on card
  c0f62795."). A correction to the row (a `CARD` line whose card is answered)
  goes to the cleanup list and Step 2.

No briefing, no decisions list, no narration of the reads, no cleanup report:
Step 2's work is in the record; it reaches his screen only as his step.

## Step 4 — Record and stop

In the same turn, after the output: write what the run printed to a JSON file
in the scratchpad **with the Write tool** (a heredoc raises an approval card:
global rules, "Shell Commands That Raise Approval Cards"), then the session
record (chat-archive `references/session-record.md`, Step 3e), built by
`session_report.py --record` with `--kind upkeep`, `--repo` the dispatched
repo, Step 2's merges in `--prs` (each `self`, or `ask` under his answer), no
`--lane`, `--dispatch <file>` and `--lanes <the declared lanes, comma-separated>`;
tags `session-record` and `dispatch`. The file:

```json
{"lanes": {"a": "running", "b": "step", "c": "ready", "d": "ready", "e": "call", "h": "prompted"},
 "prompts": {"c": {"text": "Work on MBN, lane C: …", "first": "2026-11-05T02:40Z", "since": "2026-11-03T22:40Z", "offered": 2},
             "d": {"text": "Work on MBN, lane D: …", "first": "2026-11-05T02:40Z", "since": "2026-11-05T02:40Z", "offered": 1},
             "h": {"text": "Work on fairbay/ops for MBN lane H: …", "first": "2026-11-04T23:50Z", "since": "2026-11-04T23:50Z", "offered": 1}},
 "steps": [{"lane": "b", "text": "merge #470"}, {"lane": "d", "text": "then yours: the standing-rules line"}],
 "calls": [{"lane": "e", "text": "cards 50d24cec 683a9c08"}, {"lane": null, "text": "card 03e655d9"}],
 "waiting": [{"lane": null, "text": "the routine's draft of m1351"}],
 "running": [{"lane": "h", "text": "prompted 23:50"}, {"lane": "a", "text": "#464, pushed 01:26"}],
 "cleanup": ["ops #113 merged"]}
```

`lanes` names every declared lane once with its state (`ready`, `prompted`,
`step`, `call`, `waiting`, `running`, `held`); `held` names each held lane
with the hold and its release; `prompts` holds the prompt of every
ready lane as printed and of every prompted lane as carried, each with
`first`, `since` and `offered` as the rule above sets them; the other lists
are one entry per item: a step or call noted on a Start entry ("then yours:
…") goes in `steps` or `calls` with that lane's letter; `waiting` names waiting
lanes and `running` names prompted and running lanes, every such lane once,
each with its reason in full (the screen shows a running lane's letter only,
and a prompted lane's box in Start); `cleanup`
carries Step 2's work, the list picks and dispatch's readings. The script refuses a malformed block (exit 2 with the reason:
a lane missing or unknown, a state not in the list, a prompt not in the
template or a Go or naming another lane, a `first` or `since` without the Z, a
ready or prompted lane with no prompt, a list line whose lane is in another
state) and stores it as `dispatch` in the record's context with a hash per
prompt; every record also carries `opening_hash`, so a weekly read can count
which prompts were pasted unchanged. Read it back once and end the output with
"Record <id 8>".
Dispatch writes no handoff file and no row line except Phase 0's promotions.
The session is done after one or two turns, unless he replies `go H`, which
continues it as lane H's session (Step 3). A second "dispatch" in the same
session re-reads everything (Step 1), never answers from the first turn's
reads, and logs a record that supersedes the first (`supersedes=`), so read 6
finds one record per run.
