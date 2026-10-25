# Dispatch — one turn that reads the lanes and prints each lane's next prompt

For a repo whose `.claude/landing.yaml` declares `lanes:` (MBN). Grove task
cb0d5901: the chat that planned the lanes became the dispatcher by default, and
every "check on the sessions and give me prompts" turn paid for its whole
context. Everything that turn read is in Grove and the repo, so a fresh chat
can do it in one turn and then be thrown away. Rules for what dispatch may
clean up: `fairbay/ops` docs/lanes/DESIGN.md §8.

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
itself, even when one lane's item looks small.

**If you are about to read a prior chat (`recent_chats`,
`conversation_search`) to find out where the lanes stand, stop.** The row, the
batons, the PRs and the session records are the state; a chat is a lossy copy.

## Step 1 — Read (one pass, no prior chat)

Make the reads in parallel where the surface allows. Code: the CWD clone
(`git fetch origin main` first; read files as `git show origin/main:<path>`).
Chat: attach the repo (read) and use git-ops.

1. **Project row:** `grove_list_projects(slug=<slug>, compact=false)`. Lane
   lines are the `next_actions` items that start `Lane <X>,` for a lane
   `landing.yaml` declares (a `Lane G,` line for an undeclared lane is not a
   lane: its steps show only as taps a lane waits on), plus the "Baylee's
   sittings" line. Keep `updated_at`.
2. **Open PRs:** Phase 0's report (`pr_state.py report --repo fairbay/<repo>`
   without `--table`, the dispatched repo's own copy; chat: the GitHub list),
   and for a lane whose line names another repo (MBN's lane H: `fairbay/ops`),
   that repo's open PRs too. For each PR, its lane: the
   `handoffs/lane-<x>.yaml` it changes (`pulls/<n>/files`, as lanes.md Exit 3),
   else "lane <X>" in its title or branch, else the lane tag of its `owns:`
   task (G8 lookup as in Phase 0). None of these → "outside every lane".
   Phase 0's promotion of merged `LANDING` markers runs as usual (open tasks
   and the row's `LANDING` lines); Phase 0's previous-session record check
   does not (dispatch has no single previous session).
3. **Batons:** each `handoffs/lane-<x>.yaml` of the declared lanes: `meta`
   (session, generated, landing) and the first `next:` item.
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
   sitting is answered only when its cards are in the done list. A card gates a
   lane when its tags carry `lane-<x>` or its question names an 8-hex id the
   lane's first open item names (cards from a design turn cite its task:
   "Conditional cards (2cdca464), …"). The card's own id in a lane line is a
   carry, not a gate. A card that gates no lane is still a tap. Tagging a card
   answered by note (`wrong_question`) is the consuming lane's job, not
   dispatch's.

**Finding a task by its short id.** `grove_get` needs the full UUID and
`grove_list_tasks` has no id filter: `grove_list_tasks(q=<8 hex>, compact=false,
limit=10)`, kept where `id` starts with the prefix; no hit → `q=` two words of
the title the line gives, same check. Not found → treat the item as open and say
so in the lane's line.

**Lane state, per lane** (first match wins; "fresh" means under 6 hours old):

| Evidence | State |
|---|---|
| A draft PR of the lane with a fresh head (`head_age_days` < 0.25), or a fresh decision tagged `lane-<x>` (not a record) newer than the lane's last record | **running** (name the PR or decision) |
| A ready PR of the lane | **waits on** its merge (a tap, or cleanup below) |
| An open card gates it (step 5) and the line names no next item the card does not gate, or its START HERE waits on a sitting with an open card ("once the cards are answered") | **waits on** those cards (ids) |
| Its START HERE waits on another lane's item ("wait for lane D's e70fc434") that is still open, with no alternative given | **waits on** that item |
| Otherwise | **ready**: give a prompt |

A stale decision (6 hours or older) with no record after it means a session
ended without archiving, not one still running: the lane is judged on the rows
below. A dependency with an alternative ("wait for e70fc434, or name each new
card by hand") is ready, and the alternative is the prompt's constraint line.
A sitting the row marks OPEN whose cards are all answered does not hold the
lane: its line says "sitting <n> answered; the row line is stale". Cards that
the START HERE item itself produced (a design turn delivered on its PR) leave
that item with Baylee; the lane is ready for the line's next item the cards do
not gate, and the prompt names it.

The row's lane line and the baton disagree → the newer wins (lanes.md,
Layout). A lane session that has opened no PR and logged nothing yet looks
ready; the hold section says so (Step 3).

## Step 2 — Clean up (upkeep only)

May do, in this turn, each as upkeep (the repo's `.claude/policy.json`, upkeep row):

- **A dirty upkeep PR of a lane that is not running:** merge main into its
  head (Code: fetch the branch, `git merge origin/main`; a merge, never a
  rebase), resolve a handoff-only conflict with
  `node .claude/skills/chat-archive/scripts/handoff-merge.mjs --lane <x>`, push.
  Any other conflicted path: stop, leave the PR, and list it in the lane's line
  ("#n dirty on <path>: its lane's next session merges main").
- **A ready upkeep PR** whose Go or ruling is on record and that meets
  close-at-land's three ruled-upkeep conditions (G3 green, one revert undoes
  it): merge it and promote it as close-at-land "Merge request" step 3 says.
  A refused merge call becomes a tap in Step 3 (counted, S2).
- **A superseded draft:** close it when its work is already on main (a
  `Merged #m` line in the row names it as included, or its `owns:` task is
  done or dropped), with one comment naming what superseded it. Closing is
  reversible (reopen).

May not:

- mark ready or merge a direction PR, or any PR whose class is unclear: that is
  a tap in Step 3;
- re-word, fill in or compose a Go: a prompt carries the Go sentence verbatim
  from the row's lane line or the lane's baton, or carries none;
- send a second data session while one is live: a data lane (MBN: lane A or
  lane F, or any lane whose row line carries a Go sentence; they share the live
  data set) is exclusive with every other data lane. At most one data prompt
  per dispatch, and none while a data lane is running. When two data lanes are
  ready, the first is the one whose row line carries a Go; both or neither, the
  row's order. The second gets no prompt, only the Hold line;
- touch a running lane's PR, write any lane's baton, or rewrite the row's lane
  lines (the lane's own archive does; f2826d9d).

## Step 3 — Output (this order, nothing else)

~~~
**Taps for Baylee**
1. <what, recommendation first> — <deep link>
(or "Taps: none")

**Lanes**
- **A** — <one line of state: last done, or what it waits on>
  ```
  Work on MBN, lane A: the project row's lane A START HERE line. Archive.
  ```
- **C** — running (#412, pushed 40 minutes ago)
- **B** — waits on sitting 3 (cards 50d24cec, 683a9c08)

**Hold**
- <a condition that stops a prompt above from being pasted, or "None">
~~~

- **Taps:** a ready PR that keeps the tap (`https://github.com/fairbay/<repo>/pull/<n>`),
  open cards that gate a lane (`vault.bayleemiller.org/adjudicate`, ids named),
  a real-world step a lane's START HERE waits on. Numbered, one line each.
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
  has no START HERE, or its START
  HERE item is done (its PR merged, its task done) or left with Baylee (cards
  it produced), name the starting item instead: `… lane <X>: the project row's
  lane <X> line, starting at <id> (<why, a few words>). Archive.`
- **Go:** a lane whose line or baton carries a Go sentence (`Opening line: "lane
  F: Go: …"`): the prompt is `Work on <short name>, lane <X>: Go: …` with the
  sentence verbatim, its own closing "archive." standing for the template's,
  and a constraint on the second line if any. The row's or baton's sentence
  wins over policy.json's `harness.go`: the lane's archive filled that
  template in (batch number, ruled words); dispatch never fills it, and never
  computes a batch number. Neither has one → no Go; that lane's merge falls back
  to Baylee's tap (S2), which is expected.
- A lane with an open draft that is not running: the constraint line is
  "Continue draft #<n>." A lane that is running or waits gets no prompt.
- **Lane line:** the state and its evidence in one line; a correction to the
  row (a stale OPEN sitting) goes there too.
- **Hold:** the data-lane exclusion as "lane <second> after lane <first>
  archives" (the event, never a fact that expires before it: "only after
  m1317 has published" was stale the moment the batch landed); "a lane
  session started without a PR does not show here:
  skip a lane you know is open"; a fresh decision newer than the row that
  names no lane (a session may be mid-work: name it); a PR left dirty on code.

No briefing, no decisions list, no narration of the reads.

## Step 4 — Record and stop

In the same turn, after the output: the session record (chat-archive
`references/session-record.md`, Step 3e) with `kind: upkeep`, `repo` the
dispatched repo, tags `session-record` and `dispatch`, `merges` counting
Step 2's merges, `asks: 0`, `source: self-reported` (a dispatch is counted by
recall; no usage report). Read it back once and end the output with
"Session record: <id 8>". Dispatch writes no handoff file and no row line
except Phase 0's promotions. The chat is done after one or two turns: a
second "dispatch" in the same chat re-reads everything (Step 1), never
answers from the first turn's reads.
