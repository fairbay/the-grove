# Close-at-land — hand off a PR so the chat can be dropped

The mini archive that runs when a draft PR's work is finished. It writes the
handoff and the Grove markers **into the state the world will be in once the PR
merges**, says so honestly until it has, then marks the PR ready. After step 8
nothing the next session needs lives only in this chat. Design:
`fairbay/ops` docs/land-and-leave-SPEC.md §7.1, §7.2, §7.7.

**If you are about to mark a PR ready any other way, stop.** `ccr/ready_for_review`,
`gh pr ready`, or the GitHub button without this procedure leaves a ready PR with
no handoff and no markers. The next gate reports it as G6b. Only close-at-land
makes a PR ready.

## Contents

- Marker grammar
- Opening a draft (owner task, T1)
- Close-at-land steps 1–8 (T3)
- Merge request (§7.2)
- File a card (direction that is not a fork)
- Promotion after a merge
- Land-at-push: push_and_merge (§7.7)
- Re-run safety

## Marker grammar

Exact text, one per line. Grove search (`q=`) is fuzzy, so it only narrows the
candidates; match these patterns on each line of the full notes
(`compact=false`) before acting on any of them.

| Marker | Where | Pattern |
|---|---|---|
| Owner | task notes | `^owns: fairbay/<repo>#<n>$` |
| Landing | task notes | `^landing: fairbay/<repo>#<n>$` |
| Landing | project row `next_actions` line | `^LANDING fairbay/<repo>#<n>: <text>` |
| Origin | notes of an item close-at-land created | `^from: fairbay/<repo>#<n>$` |
| On a card | the owner task's notes, first line (tag `card-open`) | `^card: <card id 8>` (then free text) |
| On a card | the owner task's notes | `^branch: fairbay/<repo>@<branch>$` |
| On a card | project row `next_actions` line | `^CARD <card id 8> (<text>): <text>` |

Never copy an `owns:`, `landing:`, `card:` or `branch:` line into another task's notes (a follow-up
task that quotes its parent would complete on the parent's merge). Page Grove
searches (`limit=100`) until a page comes back short.

## Opening a draft (owner task, T1)

Every surface pushes `claude/*` branches (Baylee's ruling 3fa9a61e). When work that changes a repo starts:

1. Run the gate first (session-start Phase 0). New work starts from a clean state.
2. Commit, push, open the PR **as a draft** (git-ops `push_to_pr()` does both;
   repo CLAUDE.md may name another call; MBN:
   `gh api repos/fairbay/<repo>/pulls -f title=… -f head=<branch> -f base=main -f body=… -F draft=true`).
3. **Owner task, same turn.** Add the line `owns: fairbay/<repo>#<n>` to the Grove
   task this work belongs to (`grove_update_task`, notes), or create one
   (`grove_create_task`, notes start with the owner line, contractor-grade body).
   Without it the next gate reports the draft as G7, unowned.

Order matters: draft first, then the owner task, so the line names a real number.

**Direction work that will wait on a card opens no draft** ("File a card" below):
push the branch as the work goes, and give the owner task the lines `card: <id>` and
`branch: fairbay/<repo>@<branch>` instead of `owns:`. Cut the branch from
`origin/main`, never from another waiting branch: work that needs a waiting change
waits for that card's answer. A draft already open when the work turns out to be such
an item stays open and keeps its `owns:` line (else the gate calls it unowned, G7);
the task then also carries `pr: fairbay/<repo>#<n>` and the session that reads his
answer lands that PR.

## Close-at-land steps 1–8 (T3)

**Preconditions.**
- The PR is a draft and has an owner task.
- No other Claude PR in this repo is ready (I3). Run
  `pr_state.py report --repo fairbay/<repo>` (`.claude/skills/session-start/scripts/`,
  synced into every repo): any row G3–G6b other than this PR → ask
  Baylee about that PR (merge or close) in one tap and act only on his answer,
  even when another session opened it; or keep this one in draft. Two ready PRs
  would both rewrite HANDOFF.yaml. The standing-rules PR of step 2 is the one
  exception: it is merged before step 3, so it never overlaps. Where landing.yaml declares
  `lanes:`, only a ready PR of this session's lane blocks (`references/lanes.md`, Exit 3).

**Steps, in order. Each is safe to re-run.**

1. **Route open items.** Scan the session: real work → Grove task; unconfirmed or
   ambiguous → HANDOFF `next:` only; a judgment call with options → adjudication.
   Every item created here carries `from: fairbay/<repo>#<n>`. Before creating,
   search for an item with that line and the same title; update it instead.
2. **Standing rules land now, separately.** A ruling Baylee made or changed this
   session goes to `main` by its own docs-only PR (CLAUDE.md "Baylee's standing
   rules" plus the superseding Grove decision), not in this PR. Rulings belong to
   the session and stand even if the PR never merges. That PR comes from its own
   branch on every surface: body starts `Standing rules:`,
   opened ready (no owner task, no trailer: it is not a work PR), and merged at
   Baylee's tap before step 3. Left unmerged, the gate shows it as G6b, which is
   right: a ruling that never reached `main`.
3. **HANDOFF.yaml on the PR branch.** First merge main once, in every repo
   (`git fetch origin main && git merge origin/main`; with `lanes:` declared this
   is also where the baton merge happens, `references/lanes.md`, Exit 1–2): the PR
   run that follows then tests the head merged with the main of this minute, and
   the landed tree on main is the one it proved, so the main-branch guard in MBN's
   `smoke.yml` skips the second suite (docs/ci-efficiency/DESIGN.md §5). With
   `lanes:` declared, then write only this lane's file and `progress` line; the
   rest of this step applies to that file. `meta.landing: fairbay/<repo>#<n>`. `done:`
   in pending tense ("Lands with #n: …"). This is the session's last baton write in the
   repo: what happens after the merge goes only to the Grove row ("No archive-only PR"
   below), so `next:` names the work after this PR as well. `next:` pruned per
   `handoff-schema.md`: carry forward every open item a previous session left,
   even one outside this PR's work. Decisions in `decisions_made:`.
   **A PR outside the repo's own workstream** (a cross-cutting rule change from
   an ops session, say) keeps the baton it finds: it sets `meta.landing`,
   `meta.generated` and `meta.surface` (naming whose baton the rest is), writes
   its own `done:` line, and adds one line pointing at the previous session's
   `done:` (its detail lives in Grove). It prunes from `next:` only items it
   verified are complete, and leaves `progress:` and every other section as they
   were. MBN #368 (S1) is the worked example.
4. **Grove markers.**
   - Project row: replace or prepend `LANDING fairbay/<repo>#<n>: <what lands>`
     in `next_actions` with one script call, never the whole array in tool
     arguments (b22bca05): write the line to a file, then
     `python3 .claude/skills/grove/scripts/grove.py lines <project id> --set "LANDING fairbay/<repo>#<n>:" <file>`
     (add `--replace "Lane <X>, " <file>` for a lanes repo's row line, which must
     already exist; `--drop <prefix>` for a line this PR retires; ops run in the order
     typed). It re-reads the row right before the write (the window for another
     session's write narrows to one round trip; no compare-and-swap, f2826d9d), refuses
     a prefix that matches two lines, and compares the stored array after; exit 0 and
     `"written": true` is the check, and a `set (prepended)` in `ops` for a line that
     should have existed means a wrong prefix. Needs `$GROVE_TOKEN` (Code sessions,
     routines). A chat without it, or an API error (exit 1), prepends one line server-side
     through the Supabase connector on the Grove project:
     `select project_update(id, owner_id, jsonb_build_object('next_actions', to_jsonb(array_prepend('<line>', next_actions))), 'claude-web') from public.project where id = '<project id>';`
     (atomic against the current row; a replace is `array_replace(next_actions, '<old line>', '<new line>')`).
   - Every task this PR completes: add `landing: fairbay/<repo>#<n>` to its
     notes and **leave it open**. It completes on merge (promotion).
   - Log decisions (`grove_log_decision`) as usual.
5. **Commit, then run the repo's `pre_ready` commands.** First commit everything
   in an ordinary commit (`git add -A`), so the checks see every file: a file
   created since the last commit is invisible to strip-working-files. Then run
   `pre_ready` from `.claude/landing.yaml` (MBN:
   `node scripts/batch/strip-working-files.mjs --apply`, then `npm run test:v4`;
   plus the suites MBN CLAUDE.md names for app, test or data changes). Any
   failure: stop, the PR stays a draft, fix it. A line that fails with
   `ERR_MODULE_NOT_FOUND` is a stale install, not a broken check (main added a
   devDependency after the container was built; MBN js-yaml, ledger f3739b05, three
   sightings 2026-11-05): run `npm install --no-audit --no-fund`, restore
   `package-lock.json` if that changed it (`git checkout -- package-lock.json`; it is
   another lane's version drift), and run the line again.

   **Policy check, every repo with a `.claude/policy.json`** (decision routing,
   `docs/decision-routing/DESIGN.md` §5): `node .claude/skills/chat-archive/scripts/policy-check.mjs`
   exits 0 — the policy parses, every `policy:` pointer names a class and a route its
   sentence names, no rule sentence routes work to Baylee uncited (S7), and the entry hook
   cuts nothing of the handoff with a worst-case PR table (S8). A repo's `pre_ready` names
   it; where it does not, run it here anyway. It runs before the close-at-land commit, so
   nothing lands on the branch after the trailer. An S8 failure means `next:` is a backlog:
   keep 3-5 items and park the rest with a location (`references/handoff-schema.md`). On a
   red S7 or S8, prose and policy both bind and the stricter reading wins. **Backstop:** the
   handoff is not pushed while `python3 .claude/skills/session-start/scripts/session_handoff.py measure`
   exits 1, in any repo, whatever its `pre_ready` says.

   **Size gate, every repo, policy or not** (2026-10-13: MBN #361 went up at
   14,686 added lines, 13,687 of them two JSON files of working output). Read
   `git diff --shortstat origin/main...HEAD` and the largest added files
   (`git diff --numstat origin/main...HEAD | sort -rn | head`):
   - Output a script regenerates is never committed: gitignore it, and the
     plan or handoff names the command that rebuilds it.
   - A record that must land is written one record per line (no pretty-printed
     JSON arrays).
   - A file over about 2,000 added lines, or a binary over 1 MB, lands only
     with its reason stated in the PR body.
6. **The close-at-land commit.** Stage what remains (`git add -A`: the index
   changes strip-working-files made; it moved working files to
   `.git/info/exclude`). Check: `git status --porcelain` is empty, and
   strip-working-files without `--apply` exits 0 (where the repo has it). If
   `pre_ready` changed nothing (or the repo has none): amend the step-5 commit when
   it is still unpushed; when it is already pushed (the Stop hook asks for a push at
   every turn end, or the PR was opened from it), make the trailer its own empty
   commit (`git commit --allow-empty`), never a force-push (e3154f13).
   Commit with the trailer as its own line in the last paragraph (the gate matches
   `Close-at-land: ` followed by a date, at the start of a line):

   ```
   Close-at-land: <now, ISO-8601 UTC, e.g. 2026-10-14T13:40:00Z>
   ```

   Push. **After this commit, nothing more goes on this branch.** A later
   commit (the Stop hook asks for one whenever files changed) turns the PR
   R-dirty (G6).
7. **Mark ready, then leave the branch.** Confirm the PR's remote head carries
   the trailer (`pr_state.py report` row for #n has `"cal": true`; if not, push
   first). **Wait for the pushed head's draft-time runs first** (ledger d2c768ec: MBN
   #442, ops #114): until `gh api repos/fairbay/<repo>/commits/<head sha>/check-runs --jq .total_count`
   is above 0 (poll every 10 s, at most 2 minutes). A ready call in the same second as
   the push lets the push's run, which still sees a draft, cancel the ready run through
   the workflow's concurrency group, and every check on the ready head then reads
   skipped or cancelled. Then `gh api -X POST repos/fairbay/<repo>/pulls/<n>/ccr/ready_for_review`.
   If it happened anyway, convert to draft (`ccr/convert_to_draft`) and mark ready once
   more, never an empty commit.
   **In a chat session with a repo attached, skip that call**: the auto-mode
   classifier refused it on every try (#91, #92, #93; ledger 62ab0083, encoded
   2026-10-26). Go straight to the merge request below; on Baylee's yes the
   ready call and the merge both run under his answer. A Code session still
   makes the call, and a refusal there is counted (S2) and never re-worded.
   **In the same turn, before the tap or any further edit,** move off the PR
   branch: `git fetch origin main && git checkout -b <new branch> origin/main`.
   A session bound to one branch name instead waits for the merge (or the
   close), then starts that name again from `main`. The remote still holds the
   squashed-away commits (MBN keeps merged branches), so `git fetch origin
   <branch> && git merge FETCH_HEAD` once before the first push. Never force-push.
8. **Next-step line:** "#n is ready. Merge to land it: <link>." From here the chat
   can be dropped. Then go to the merge request below; the session itself goes on.

   **The last line of every close-out is one of two sentences** (Baylee, 2026-10-23
   and 2026-10-26: he should know at a glance when a thread needs nothing more from
   him, and a failure after that point must make noise somewhere else). After the merge,
   the promotion and the session record, end the turn with exactly one of:
   - `Safe to leave. Yours next: <one item with its page or link, or "nothing">.` —
     only when every check this session started has finished green, the handoff is on
     main, the Grove markers are promoted and the record id is in hand.
   - `Not safe to leave: <what is still running or unverified>; a failure shows up as
     <where>.` — a check still running (sync.yml, unit.yml on main) is named with its
     noise channel: GitHub emails the merge actor on a failed run, the next session's
     entry gate lists main's red head (G2), and the weekly read's Runs section prints
     the newest sync and rules conclusions. Never let a running check be the last word
     without saying so.
   "Nothing pending from me" and "say which when it's done" are not close-out lines.

   **The Go sentence rides in the Next-step line.** When the repo's
   `.claude/policy.json` carries a `harness` note (a Code data session's
   apply, publish and merge are refused by the auto-mode classifier until a
   user message names the exact action), the archive writes the next session's
   Go sentence into the Next-step line verbatim, as the policy's `harness.go`
   states it (read from the file, never quoted from memory), the batch id filled in (in a lanes repo prefixed with the
   lane, `lane A: Go: …`, so the lane gate loads the baton); when the next session
   is not a data batch (a library session, a build), the line names that work
   and no Go. Baylee's opening message then carries his consent and the next
   session asks no blocking question at start. What the Go covers changes only by his ruling; a refusal
   after it falls back to the tap and is counted (S2).

   **In a lanes repo the same Go also ends the baton's START HERE item and the
   row's lane line**, as `Opening line: "lane A: Go: …"`: dispatch writes the
   prompts he pastes and copies a Go only from there, never composing one, so a
   Go left only in the chat line never reaches the next session (Grove 6179636b:
   no baton ever carried one, and lane A sat on a Go question 01:19Z to ~10:40Z
   on 2026-11-08). policy-check (f) fails a baton whose START HERE says "a data
   batch" or "a data session" without it. The id is the next free one at archive
   time; a session that finds it taken uses the next and says so (a refusal then
   is S2, as above).

## Merge request (§7.2)

1. Read the PR's row: `pr_state.py report --repo fairbay/<repo>` (row for #n).
2. Ask one tap (Code: AskUserQuestion; chat: `ask_user_input_v0`):

   | Row | Question | Pre-selected | Other options |
   |---|---|---|---|
   | G3 (green, or not run) | "Merge #n now?" | Merge | Wait |
   | G4 (checks pending) | keep working; ask once the checks settle | — | — |
   | G5 (failed) | not offered: back to draft (`ccr/convert_to_draft`), fix, close-at-land again | — | — |
   | G5b (Actions minutes out) | "Merge #n on the local tests?" | Merge on local tests | Wait |

   In a `merge_policy: self` repo the session may merge without a tap where the
   platform allows it; a refused merge call falls back to the tap.

   **Ruled upkeep merges without a tap** (Baylee, 2026-10-19, adjudication
   ffea5247; `policy: upkeep` in the repo's `.claude/policy.json`) in a
   `merge_policy: policy` or `self` repo, when all three hold; a `tap` repo, or
   one whose policy file is missing (pr_state reports the fallback), keeps the
   tap for every PR:
   1. The PR only carries out a ruling Baylee already made, or is upkeep: a fix,
      cleanup or follow-up to what already shipped, with no change of direction.
   2. It was verified: row G3 with the checks green, and in a `deploy_check:
      vercel` repo the preview checked as well. G4 waits for the checks; G5 and
      G5b (no checks ran) keep the tap.
   3. One revert undoes it: no data migration or deletion, no outward step (a
      publish, an email, a payment).

   Then skip the question and go to step 3, and name the ruling (card ID) or the
   upkeep in the report line. A new design, a new feature, a change of direction,
   or a ruling read past its plain words keeps the tap (`policy: direction`,
   `policy: owner_context`).
   When the session has nothing else ongoing or planned, ask "Archive now?"
   after the merge instead. The auto-mode classifier may refuse the merge
   call (Code sessions, and chat sessions with repos attached: observed
   2026-10-20, MBN #391): the refusal falls back to the tap, is counted in the
   session record (signal S2), and is never re-worded mid-session. The
   fallback tap is the table's question, so when nothing else is planned it
   is "Merge and archive", pre-selected — never a bare "merge" followed by a
   second question for the archive (2026-10-20: it cost Baylee a turn).

   **A green non-major bot PR rides in the same question.** When the gate shows
   a G9 row (Dependabot, green, no major bump), fold it into this session's one
   merge question ("Merge #n and Dependabot #m?") or into the ruled-upkeep merge
   above; never a separate offer or a separate tap. G10–G12 keep their own
   gate rows.

   **Merge and archive** (Baylee, 2026-10-18). When the session has no other
   work ongoing or planned once this PR lands (it was the last item, or the
   repo's rules end the session after it, such as MBN's one data batch per
   session), add the option "Merge and archive" to the G3 or G5b question and
   pre-select it ahead of "Merge". One answer then merges and archives, so
   Baylee never spends a second turn asking for the archive. While other work
   remains, ask as in the table.
3. **On yes** (Merge, or Merge and archive):
   - Merge, pinned to the head the tap was about, so a moved head aborts (F4):
     `gh api -X PUT repos/fairbay/<repo>/pulls/<n>/merge -f merge_method=<policy merge_method> -f sha=<head sha>`.
   - Deploy check (`deploy_check: vercel`): `pr_state.py check <n>` →
     `deploy_state` of the merge commit. `pending`: check again in a minute;
     still nothing after about 2 minutes, or `failure`: the repo CLAUDE.md
     runbook (MBN: "After a merge, check that Vercel built it").
   - Promote (below).
   - **Merge and archive:** after the promotion, run the full archive (SKILL.md
     Steps 1–10) in the same turn without asking again. When this merge request
     already came from inside the archive (Step 9's close-at-land), finish the
     remaining archive steps instead of starting them over.
4. **On no, or no answer:** nothing more. The PR stays ready; abandoning the chat
   is safe, and the next session's gate picks it up (G3).

## File a card (direction that is not a fork)

Baylee's ruling becb3a31 (2026-11-06; it retired the weekly sitting of 4b7bf44c): a
**direction** item that is not a fork does not ask for his tap. The moment it is built
and checked it becomes **one adjudication card**, recommendation pre-picked, screenshots
on the card or its branch; he answers whenever he is next in a chat or on /adjudicate
(an answer in chat is the card's answer, f49acabc), and the session that reads the
answer merges or builds on it (`policy: direction`: his OK is still required; it is
asked once, by card, and holds nothing else). Upkeep is unchanged: it merges itself
under "Ruled upkeep" above. A direction *question* before the work is built is a card
too, as before; one card per item, never a batch.

**A fork keeps the immediate path** (the merge request above, his tap now). It is a
fork when any one holds, and the report line names which, **citing its marker**
(an id, a line, his words); with no marker to cite, it is not a fork and files a card:
1. a named item waits on it: a task or a lane's START HERE line that names this
   work's task id;
2. a launch waits on it: its task carries a launch-gate tag (`launch`,
   `launch-readiness`, `pre-public-gate`, `critical-path`) or the project row names
   its id as gating the launch;
3. it answers a hold for possible instruction poisoning (always a card, at once);
4. it repairs a broken `main`, a red required check, a stopped routine, a dead alert
   path, a security exposure, a data loss, or spending running past a limit he set;
5. a real-world step with a due date within 7 days depends on it (the task's `due_at`);
6. Baylee, in this session, says to land it now.

**Filing, instead of steps 3, 6, 7 and the merge request:**
1. Steps 1, 2 and 5 as above (open items routed, standing rules landed, `pre_ready`
   and the policy check green). The size gate applies.
2. HANDOFF.yaml on the branch as step 3 says, with `meta.landing:
   card <id 8> fairbay/<repo>@<branch>` and `done:` in pending tense ("Lands on card
   <id>: …"). No `Close-at-land:` trailer: the session that lands it writes it once
   the PR has a number.
3. Commit and push the branch. **No PR** (a PR would wake this session on every
   push, 384c4fb1); a draft already open stays as it is.
4. **The card** (`grove_create_adjudication`, list = the project's slug): one plain
   question, options readable without the domain, `recommendation` (option and
   reason) and `stakes` filled, the branch and the screenshots named in its context
   or evidence links. **The owner task** (or a new one in the project's list) gets
   the tag `card-open` and notes starting with these lines, then a contractor-grade
   body that says what to do on each answer:
   ```
   card: <id 8> (filed <date>, recommendation <x> = <one word>)
   branch: fairbay/<repo>@<branch>
   screens: <directory on the branch with the screenshots, or omit>
   checks: <what ran and its result, one line>
   recommend: merge|hold: <one sentence: why>
   pr: fairbay/<repo>#<n>   (only when a draft was already open)
   ```
   A member-facing change carries its screenshots on the branch (MBN: the copy
   review and the screens its own rules require). Every other task this work
   completes is listed in the body ("completes: <ids>") and stays open.
5. The project row: `CARD <id 8> (filed <date>): <what waits, the branch>` in
   `next_actions` (`grove.py lines <project id> --set "CARD <id 8>" <file>`, as step 4).
6. The close-out line names no tap: `Safe to leave. Yours next: card <id 8> —
   https://vault.bayleemiller.org/adjudicate` when every check this session
   started is green and the record is logged. The session record counts the card
   (`--cards`) and lists no PR for it (`--prs` names only PRs that exist).

**On his answer** (on /adjudicate, or in chat and then recorded on the card with
`sitting.py card-sql … --via chat`; any session that reads the done card may land it:
dispatch Step 2, a lane session, the chat he answered in). **Claim first, so two
sessions never land one branch:** re-read the owner task; a `landing:` line, or a
`claimed:` line under two hours old, means another session has it: stop. Otherwise
add `claimed: <session URL> <UTC time>` to its notes, then look the branch up
(`gh api "repos/fairbay/<repo>/pulls?state=all&head=fairbay:<branch>"`): a merged PR
means it already landed (promote it); an open one is the PR to use. Then, with a yes:
merge `main` into the branch, run `pre_ready` and the policy check, open the PR
**ready** with the body "Ruled on card <id> <date>: <his words>" (or mark the
existing draft ready), turn `card:` into `landing: fairbay/<repo>#<n>` on the owner
task and give each task it completes its `landing:` line, replace the row's `CARD`
line with `LANDING fairbay/<repo>#<n>: …`, add the `Close-at-land:` trailer, and
merge pinned to the head once the checks are green (his answer is the Go; a refused
call, which a chat session with a repo attached should expect, falls back to the tap,
S2, never re-worded). With a no, or another option: do what the task body says for it,
record his words on the task, drop or re-scope it, and leave the branch. Two waiting
branches in one repo both rewrite its handoff: land them one at a time, `main` merged
into each first.

## Promotion after a merge

Run in-session after a merge, and at entry by session-start Phase 0 for every
merged PR a marker names (S2: Baylee merged on GitHub after the chat ended).

1. `pr_state.py check <n> --repo fairbay/<repo>` → `state: merged`, `merge_sha`,
   `deploy_state`, `commits_after_cal`.
2. Project row: rewrite each
   `LANDING fairbay/<repo>#<n>: <text>` to `Merged #<n> <date> (<merge sha 8>): <text>`
   with `grove.py lines <project id> --rewrite "LANDING fairbay/<repo>#<n>:" "Merged #<n> <date> (<sha 8>):"`
   (it re-reads the row and verifies the write; step 4 says when to use SQL instead).
3. Each open task whose notes carry `landing: fairbay/<repo>#<n>`:
   `grove_complete_task`. A task Baylee already closed stays as it is.
4. Deploy, in-session right after a merge only (above). At entry the gate's G2
   checks main's head instead: a later successful build supersedes an earlier
   miss, and a merge still building is not a failure.
5. `commits_after_cal` not empty (merged from R-dirty) → a review item listing
   those commits.

Once rewritten, the markers no longer match, so a second run does nothing.
Closed-unmerged rollback (`NOT LANDED #n`) arrives with rollout step 4; until
then leave a closed PR's markers alone and name them in the report.

## Land-at-push: push_and_merge (§7.7)

No session pushes to `main` (Baylee's ruling 3fa9a61e, 2026-10-21): chat
sessions and content-batch archives open a PR like any other. **No archive-only
PR** (Grove f21b91ed step 5, 2026-11-06): the baton rides the work PR (step 3,
written for the merged state); a session whose archive would change only handoff
files (HANDOFF.yaml, `handoffs/lane-*.yaml`), because its work already merged or
it made none, opens no PR and writes its state to the Grove project row instead
(lanes: its lane line, `references/lanes.md` "No archive-only PR"; else its
`next_actions` and `last_session`). The repo's handoff then trails the row: at
entry the newer of the two wins (session-start Phase 2–3), and the next work PR
writes the handoff from the row. The one
land-at-push path left is an ops change through `push_and_merge`, which
merges its own PR in the same call. For it, run steps 1–3, and step 4's
decision logging, with no markers and no trailer. If `push_and_merge` cannot
merge, the PR it leaves is ready without a trailer (G6b): convert it to draft
(`ccr/convert_to_draft`) and hand it off with close-at-land, or ask the merge
tap at once. The handoff rides in the same commit and `done:` is in
past tense. The gate still runs at the next entry.

## Re-run safety

- Interrupted after step 6, before step 7: the PR's **remote** head carries the
  trailer (`cal: true`) → skip to step 7. Only the local head has it → push, then step 7.
- Interrupted before step 6: re-run from step 1. Steps 3–4 overwrite and the
  `from:` search updates rather than duplicates.
- Interrupted between merge and promotion: the next gate promotes (T10).
