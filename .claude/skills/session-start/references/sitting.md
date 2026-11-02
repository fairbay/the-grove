# Sitting — one chat a week where Baylee rules the queue

Architecture run 75cbc21d, build item 2 (`fairbay/ops` docs/architecture-run/04-PROPOSAL.md
§8; Baylee's ruling 4b7bf44c, 2026-10-28). Between sittings, sessions queue
non-urgent direction work instead of asking him (close-at-land "Queue for the
sitting"). Once a week he opens a chat, rules everything in one answer, and this
session merges what he approved under it. The sitting counts as **one interrupt**
toward SC-001 (≤15 a week); the decisions ruled inside it are reported beside it.

## Contents

- Trigger
- Step 1 — Read (one pass)
- Step 2 — The page (one message, then wait)
- Step 3 — Apply his answer
- Step 4 — Record, archive, stop

## Trigger

"run the sitting", "the sitting", "weekly sitting" as the **first message of a
session**. Like dispatch, it replaces Phases 0–5: no briefing, no work queue. It
does no other work, even when an item looks small. The same words mid-session are
chat-status. MBN's older numbered "sittings" (a set of cards, tag `sitting-<n>`)
are cards: they show here with the rest.

**If you are about to read a prior chat to find out what waits, stop.** The queue
tasks, the cards, the decisions and the branches are the state.

## Step 1 — Read (one pass)

Attach `fairbay/ops` (push) and every repo a queue item names (push), each with
`add_repo`; `register_repo_root` for ops. Make the reads in parallel. Save each
result to the scratchpad as returned (no hand edits) and keep the row count each
tool reported:

1. **Since** — the newest decision tagged `sitting` and `session-record`
   (`grove_list_decisions(project_ref="fairbay/ops", current_only=false,
   limit=50)`, compact): its date. None → 7 days ago.
2. **Queue** → `queue.json`: `grove_list_tasks(tag="sitting-queue",
   status="open", compact=false, limit=100)`.
3. **Cards** → `cards.json`: `grove_list_adjudications(status="open", limit=100)`,
   no list filter (every project). A task tagged `adjudication` with no options is
   listed as "not offered", never ruled.
4. **Decisions** → `decisions.json`: one Supabase `execute_sql` on the Grove
   project (`rhaueykqbtftaeosfldz`); save the `rows` array, and `n` is its count.
   It returns only what the digest and the counter read (session records with
   their counting fields, contested calls, reversals, and every call a record in
   the window showed), not every decision of the week:
   ```sql
   with recs as (select context from decision where created_at >= '<since>' and 'session-record' = any(tags) and pg_input_is_valid(context, 'jsonb')),
   shown as (select distinct jsonb_array_elements_text(coalesce(context::jsonb->'calls_shown', '[]'::jsonb)) p from recs),
   picked as (select d.* from decision d where d.created_at >= '<since>' and ('session-record' = any(d.tags) or 'contested' = any(d.tags) or 'reversal' = any(d.tags)
     or exists (select 1 from shown where length(shown.p) >= 8 and d.id::text like shown.p || '%')))
   select count(*) n, json_agg(json_build_object('id', id, 'decision', left(decision, 160), 'tags', tags, 'confidence', confidence,
     'superseded_by', superseded_by, 'project_ref', project_ref, 'created_at', created_at,
     'context', case when 'session-record' = any(tags) and pg_input_is_valid(context, 'jsonb') then (select jsonb_object_agg(k, v)
       from jsonb_each(context::jsonb) e(k, v) where k in ('record','date','repo','lane','asks','refusals','merges','calls_shown','source','interrupts','start','prs','landed','cache_read_m')) end)
     order by created_at) rows from picked;
   ```
5. **His steps** → `baylee.json`: `grove_list_tasks(tag="baylee", status="open",
   compact=false, limit=100)`.
6. **Each queue item's branch** (`git fetch origin <branch>`):
   - It exists. Missing → "branch gone", never offered.
   - **Its PRs:** `gh api "repos/fairbay/<repo>/pulls?state=all&head=fairbay:<branch>"`. A merged one → the
     item already landed: complete its queue task (`landed as #n`), never offer it. An open one the
     task does not name → add `pr: fairbay/<repo>#<n>` to the task and land through it.
   - **Stacked:** for each other queued branch of the same repo, `git merge-base --is-ancestor
     origin/<other> origin/<this>` exits 0 → this item carries the other's commits. Say so on the
     page ("contains Q<k>"); it may merge only if Q<k> merges first in the same answer, else it waits.
7. **Screens** — for an item with `screens:`, list that directory on the branch
   (`git ls-tree --name-only origin/<branch> <dir>/`) and **Read each image**, so it
   shows inline in the page. More than 6 → the first 6 by file name; say how many more.

Then (a count that differs from the tool's exits 2: redo that dump):

```bash
python3 .claude/skills/chat-archive/scripts/sitting.py page \
  --queue queue.json --cards cards.json --decisions decisions.json --baylee baylee.json \
  --ledger docs/cost-ledger.md --since <since> --until <today> --key-out key.json \
  --expect queue=<n>,cards=<n>,decisions=<n>,baylee=<n>
```

## Step 2 — The page (one message, then wait)

The script's page, verbatim, with three things added in place:

- each queue item's screens, shown inline under it (Step 1.7);
- under **Your real-world steps**, a draft for each R item, send-ready: the email
  or message text (email-craft rules: his voice, the recipient, the subject), or
  the exact clicks with the deep link. Only the R items; the rest stay in Grove;
- a **fork** line if any queue item now meets a fork condition (close-at-land,
  "Queue for the sitting"): it is still on the page; say why it should not wait
  another week.

End the message with the page's answer line. Ask nothing else. Do not use
AskUserQuestion: it caps at four questions and the page can hold more; his reply
in prose is the answer (counted as one prose ask).

## Step 3 — Apply his answer

```bash
python3 .claude/skills/chat-archive/scripts/sitting.py answer --key key.json --text "<his reply, verbatim>"
```

Exit 3 → the reply settled nothing: say so in one line and wait. Otherwise send
the `echo` lines as one message (what will happen to each item; unsettled ones
and anything not read are listed last), then, in the same turn, apply the plan, **one repo at a time and one PR at a time within a repo** (each landing
rewrites that repo's handoff). His answer is the Go for every step below; a
refused call falls back to a tap, is counted (S2) and is never re-worded.

**`merge` (a queue item):**
1. `git checkout -B <branch> origin/<branch> && git merge origin/main`. A conflict
   in a handoff file only: a lanes repo runs
   `node .claude/skills/chat-archive/scripts/handoff-merge.mjs --lane <x>`;
   otherwise keep main's file and carry the branch's own `done:` line, its new
   `next:` items and its `decisions_made:` onto it (close-at-land step 3: every open
   item is carried forward). Any other
   conflicted path: abort the merge, the item stays queued with a note line
   `dirty <date>: <path>`, and the page's answer is not stretched to cover a fix.
2. Run the repo's `pre_ready` (`.claude/landing.yaml`) and the policy check, as
   close-at-land step 5.
3. Open the PR **ready** (not a draft: the checks run now). An item with a `pr:`
   line already has a draft: mark it ready now, under his answer
   (`gh api -X POST repos/fairbay/<repo>/pulls/<n>/ccr/ready_for_review`), so its
   checks run before the wait. A refusal (chat sessions see it, close-at-land step
   7) makes that item a tap: say "Q<k> is ready on GitHub: merge it there", count it
   (S2), and go on with the rest. Before opening, re-run Step 1.6's PR lookup: a PR
   for the branch already open is used, never a second one. Otherwise:
   `gh api repos/fairbay/<repo>/pulls -f title=<item title> -f head=<branch> -f base=main -f body=<summary, "Ruled at the sitting <date>: <his words for it>", the queue task id>`.
4. Markers for #n: on the queue task and on every task whose notes carry
   `sits: fairbay/<repo>@<branch>`, add `landing: fairbay/<repo>#<n>`; the project
   row gets `LANDING fairbay/<repo>#<n>: <title>` in place of its
   `SITTING fairbay/<repo>@<branch>` line (re-read the row first).
5. The close-at-land commit: the handoff's `meta.landing` becomes
   `fairbay/<repo>#<n>`, then the `Close-at-land: <now>` trailer commit; push.
6. Wait for the checks (`pr_state.py check <n>`, about once a minute, **cap 20
   minutes**). G3 → merge pinned to the head sha (close-at-land "Merge request"
   step 3), deploy check, promotion. G5 (red) → close the PR with one comment, the
   item stays queued with `failed <date>: <check>`; its fix is a new session's
   work, not this one's. Still pending at the cap → leave it ready; the next
   entry gate shows it (G3/G4) and a later session merges it under this answer
   (name the answer in the row's LANDING line).

**`hold`:** add `held <date>: <his note>` to the queue task; it stays queued.
**`drop`:** drop the queue task (`grove_drop_task`) with `dropped at the sitting
<date>: <his note>` in its notes; leave the branch.
**`option:<x>` (a card):** `sitting.py card-sql --card <id> --option <x> --notes "<his words>" --at <now>`
and run it with Supabase `execute_sql` on the Grove project
(`rhaueykqbtftaeosfldz`); read the card back (`grove_list_adjudications(status="done")`
shows it with its resolution). A card ruled by a note with no option is
`--option none` and takes the wrong-question tags (session-record.md,
"Reversals and wrong questions"). A card's consequences are the owning
project's next session's work, not the sitting's.
**`reverse` (a digest call):** a superseding decision tagged `reversal`
(session-record.md, "Reversals and wrong questions"). Undoing it is done here
only when one revert or one note does it; otherwise a Grove task for the owning
project, priority 2.
**`done` (an R item):** `grove_complete_task`. **`later`:** nothing.
**`unsettled`:** nothing. It shows again next week.

Bound: one pass over the plan. Nothing is retried except as Step 3.6 says.

**What the interrupt count shows.** The sitting is one prose ask; a merge under it
costs nothing (`session_report.py`: "a merge under his answer is inside the ask").
A merge or ready call the classifier refuses becomes a tap and counts as one more,
the same as anywhere else; the record shows it, and repeated refusals are a ledger
note for running the sitting as a Code session instead.

## Step 4 — Record, archive, stop

1. **Session record** (chat-archive `references/session-record.md`, Step 3e):
   `session_report.py --record --kind direction --repo fairbay/ops --asks-prose 1`,
   with every PR opened in `--prs` as `ask` (merged under his answer) or `pending`
   (left ready at the cap). `--cards` stays empty: cards here are ruled, not filed.
   Log it with tags `session-record` and `sitting`, and end the decision text with
   one `rulings:` line: "queue m merged / h held / d dropped; cards c; reversals r;
   unsettled u". That line is the decisions count SC-001 reports beside the one
   interrupt (4b7bf44c).
2. Reply with one short table (item, ruling, result, link), the record id, and the
   close-out line (close-at-land step 8): `Safe to leave. Yours next: <an R item not
   done, else the next sitting in a week>.` or `Not safe to leave: …`.

The chat is then done. A second "sitting" in the same chat re-reads everything
(Step 1); it never answers from the first page.
