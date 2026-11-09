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
itself, even when one lane's item looks small. Run it in a Code session: a chat
may have no transcript on disk (ledger 521aac68: none in two chats on
2026-11-03), and then its record is self-reported and the weekly read cannot
count it; a chat that runs it still writes Step 4's block by hand.

**If you are about to read a prior chat (`recent_chats`,
`conversation_search`) to find out where the lanes stand, stop.** The row, the
batons, the PRs and the session records are the state; a chat is a lossy copy.

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
   lines (built work waiting on his answer; close-at-land "File a card"). Keep
   `updated_at`.
2. **Open PRs:** Phase 0's report (`pr_state.py report --repo fairbay/<repo>`
   without `--table`, the dispatched repo's own copy; chat: the GitHub list),
   and for a lane whose line names another repo (MBN's lane H: `fairbay/ops`),
   that repo's open PRs too. For each PR, its lane: the
   `handoffs/lane-<x>.yaml` it changes (`pulls/<n>/files`, as lanes.md Exit 3),
   else "lane <X>" in its title or branch, else the lane tag of its `owns:`
   task (G8 lookup as in Phase 0). None of these → "outside every lane". A
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
   (`wrong_question`) is the consuming lane's job, not dispatch's.
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

**Finding a task by its short id.** `grove_get` needs the full UUID and
`grove_list_tasks` has no id filter: `grove_list_tasks(q=<8 hex>, compact=false,
limit=10)`, kept where `id` starts with the prefix; no hit → `q=` two words of
the title the line gives, same check. Not found → treat the item as open and say
so in the lane's line.

**Lane state, per lane** (first match wins; "fresh" means under 6 hours old).
The state names the group the lane prints in (Step 3).

| Evidence | State → group |
|---|---|
| A draft PR of the lane with a fresh head (`head_age_days` < 0.25), or a fresh decision tagged `lane-<x>` (not a record) newer than the lane's last record | **running** → Running (name the PR or decision) |
| The last dispatch's block (read 6) carries a prompt for the lane whose `first` is under **2 hours** old, and nothing since that `first` shows the lane archived: no newer record tagged `lane-<x>`, no PR of the lane merged after it | **prompted** → Running ("prompted HH:MM, nothing seen yet"); its prompt is carried in Step 4's block unchanged (same `text`, `first`, `since`, `offered`), not printed |
| A ready PR of the lane that Step 2 may not merge (direction, or a class that is unclear) | **your step** → Your step: the merge, with its link and the recommendation |
| Its START HERE item is Baylee's own step ("Baylee reviews …", a page or list he answers, a real-world step), its precondition, when the line states one ("when …", "once …"), holds on the reads, and nothing on record shows it done | **your step** → Your step: the step with its link. Escape below |
| An open card gates it (read 5), or its START HERE waits on open cards ("once the cards are answered"), or a `CARD <id>` row line or an open `card-open` task names its built branch (close-at-land "File a card") | **your call** → Your call: the card ids and the link, with the branch. Escape below |
| Its START HERE waits on another lane's item ("wait for lane D's e70fc434") that is still open, with no alternative given, or on his step whose precondition does not hold; or its line names no open item; or its baton cannot be read | **waiting** → Waiting, not on you: the item and its lane, "nothing queued", or the read error. Escape below |
| It is the lane data-draft-r drafts for (MBN lane A: the brief's precondition 2 reads lane A's START HERE), its START HERE batch `<id>` has an open draft PR titled "… (drafted by data-draft-r)", and nothing shows that PR's batch applied | **ready** → Start: the apply session for that PR, constraint "Apply and publish from data-draft-r's draft PR #<n>." (the Go verbatim as always, or none); never a prompt that drafts the same batch (5737a18a) |
| The same lane, no such PR yet, and the routine holds `<id>`: lane H's or the row's line says data-draft-r drafts `<id>`, or a `claude/data-*-<id>` branch has a head under 6 hours old (read 2), and no session record of the routine's run on `<id>` is logged yet (read 4: a decision beginning `session-record` that names `data-draft-r <id>`). Once that record is logged, the run has ended: a branch it left with no PR is the routine's stopped draft, and lane A is judged as any data lane, its prompt carrying "Continue from data-draft-r's stopped <id> draft on <branch>; its record <id 8> names the stop." (2026-11-05: run 3 stopped at the live step, record 290d34c1). An older branch with no PR and no such record is not the routine's (the proxy cannot delete branches): this row does not apply, and the lane's prompt carries "Branch <name> has no PR: reconcile it first." | **waiting** → Waiting, not on you: "the routine's draft of <id>". While this row holds, the routine counts as a running data lane for every other lane (Step 2's exclusion) |
| It is a data lane (Step 2's definition) while another data lane is running or prompted, the routine's draft included (the row above); or it is the second of two ready data lanes (Step 2's tie-break) | **waiting** → Waiting, not on you: "after lane A archives" or "after the routine's draft of <id>". Escape below, to an item that is not a data batch. A data lane whose batch names the id the routine holds (lane B's batch 1 named m1351 on 2026-11-05), when it is prompted later, carries "<id> is data-draft-r's: check the next free id before you draft." |
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
Layout). A lane session that has opened no PR and logged nothing yet, and that
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
- re-word, fill in or compose a Go: a prompt carries the Go sentence verbatim
  from the row's lane line or the lane's baton, or carries none;
- send a second data session while one is live. A lane is a data lane by the
  item it would work, not by its name (docs/lanes/DESIGN.md: "a lane whose Go
  applies data"): its START HERE item (the START HERE text up to its first
  "Then"; what follows is later items), or the item the escape picks, names an
  `mNNNN` batch to draft, apply or publish, or its row line or baton carries a
  Go sentence (no Go, no apply: `.claude/policy.json` `harness.go`). Data lanes share the live data set, so each is exclusive with
  every other: at most one data prompt per dispatch, and none while a data lane
  is running or prompted. When two are ready, the first is the one whose row
  line carries a Go; both or neither, the row's order. The second is waiting
  ("after lane A archives"). A lane whose item says "No data batch" or is a
  library, tooling or design session (MBN lane E's library work) is not a data
  lane: it is ready beside a running one, with the constraint "Library work
  only: no data batch while lane <x>'s <mNNNN> is open." (5737a18a; three
  dispatches on 2026-11-05 held the then lane F's library session about 26 hours;
  MBN has one data lane, A, since F merged into it, f21b91ed step 5);
- touch a running lane's PR, write any lane's baton, or rewrite the row's lane
  lines (the lane's own archive does; f2826d9d). The one exception is the text
  his answer made stale (above).

## Step 3 — Output (this order, nothing else)

**The output is the prompts, plus only what Baylee needs to run them
properly** (his direction, 2026-11-07: "When I do a dispatch I expect to get a
bunch of prompts, and I really only need to know what I need to know to do them
properly"). No line says what a session will do, why a lane is in its state, its
list rank, its offered count or what Step 2 cleaned up: the prompt and the row
carry the work, the record (Step 4) carries the rest. Groups keep the order of
a830496b (what he does, most to least); lanes keep the row's order inside one.

~~~
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

**Your step:** merge #n (recommendation: merge) https://github.com/fairbay/<repo>/pull/<n>
**Your call:** cards 50d24cec, 683a9c08 https://vault.bayleemiller.org/adjudicate

Not now: B, F (wait on lane A). Running: H (if you didn't start it, reply `reprint lane H`).
Record <id 8>
~~~

- **Start:** each ready lane's letter and its prompt box. A note follows the
  letter (after " · ", a few words) only when he has something to do around the
  session: a tap or merge it will leave him (no Go on record), his step that
  comes right after it ("then yours: …", with the link), or an order between
  two Start lanes when one truly must go first. Never the session's work, its
  evidence, a recommendation or a ranking ("start here first" read as an order
  on 2026-11-07, and he had rightly started all six at once).
- **Your step:** one line per item, the link and the recommendation, nothing
  else: a ready PR that keeps his tap, a real-world step a lane's START HERE
  waits on, a refused cleanup call (S2); the lane letter in front when there is
  one. Never his step: a card or step his answer on record already settles
  (Step 2 applies it), or work the reads found undone (Step 2 does it or files
  a task). None → `**Your step:** none`.
- **Your call:** the open card ids that gate a lane or gate none, with the
  adjudicate link (a built branch's card names its branch). None →
  `**Your call:** none`.
- **Not now / Running:** one line. "Not now" (the state table's "Waiting, not
  on you" group; its quoted reasons go to the record) lists the waiting lanes' letters,
  each with at most a few words when the word helps him know when it frees
  ("wait on lane A"; worded as the event, never a fact that expires before it).
  "Running" lists running and prompted lanes' letters; a prompted lane adds
  "if you didn't start it, reply `reprint lane <X>`". No copy box for either: a
  second session of one lane is the collision the lanes exist to prevent
  (lanes.md: one session at a time). Either part with no lane is left out.
- **Record:** the last line, once Step 4 has the id.
- **`reprint lane X`** as his reply, in the dispatching session, prints that
  lane's carried prompt verbatim and nothing else; it is not a second dispatch
  (Step 4), re-reads nothing and changes no record (the lane stays prompted
  until the two hours pass). For a lane already in Start it prints the same
  box again. In a later session the reply has no block to read: he runs
  dispatch again.
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
  with the same tail.
- **Go:** a lane whose line or baton carries a Go sentence (`Opening line: "lane
  F: Go: …"`): the prompt is `Work on <short name>, lane <X>: Go: …` with the
  sentence verbatim, its own closing "archive." standing for the template's,
  and a constraint on the second line if any. The row's or baton's sentence
  wins over policy.json's `harness.go`: the lane's archive filled that
  template in (batch number, ruled words); dispatch never fills it, and never
  computes a batch number. Neither has one → no Go; that lane's merge falls back
  to Baylee's tap (S2). On a data lane that is a miss by its last archive
  (close-at-land step 8 writes the Go into the baton; policy-check (f) gates it
  since Grove 6179636b): the Start note says "asks you for a Go", and the record's
  cleanup names the lane's archive.
- A lane with an open draft that is not running: the constraint line is
  "Continue draft #<n>." A running, prompted or waiting lane gets no new prompt.
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
`step`, `call`, `waiting`, `running`); `prompts` holds the prompt of every
ready lane as printed and of every prompted lane as carried, each with
`first`, `since` and `offered` as the rule above sets them; the other lists
are one entry per item: a step or call noted on a Start entry ("then yours:
…") goes in `steps` or `calls` with that lane's letter; `waiting` names waiting
lanes and `running` names prompted and running lanes, every such lane once,
each with its reason in full (the screen shows only the letters); `cleanup`
carries Step 2's work, the list picks and dispatch's readings. The script refuses a malformed block (exit 2 with the reason:
a lane missing or unknown, a state not in the list, a prompt not in the
template or a Go or naming another lane, a `first` or `since` without the Z, a
ready or prompted lane with no prompt, a list line whose lane is in another
state) and stores it as `dispatch` in the record's context with a hash per
prompt; every record also carries `opening_hash`, so a weekly read can count
which prompts were pasted unchanged. Read it back once and end the output with
"Record <id 8>".
Dispatch writes no handoff file and no row line except Phase 0's promotions.
The session is done after one or two turns: a second "dispatch" in the same
session re-reads everything (Step 1), never answers from the first turn's
reads, and logs a record that supersedes the first (`supersedes=`), so read 6
finds one record per run.
