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
- Promotion after a merge
- Direct-to-main sessions (§7.7)
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

Never copy an `owns:` or `landing:` line into another task's notes (a follow-up
task that quotes its parent would complete on the parent's merge). Page Grove
searches (`limit=100`) until a page comes back short.

## Opening a draft (owner task, T1)

Code web sessions push `claude/*` branches. When work that changes a repo starts:

1. Run the gate first (session-start Phase 0). New work starts from a clean state.
2. Commit, push, open the PR **as a draft** (repo CLAUDE.md has the call; MBN:
   `gh api repos/fairbay/<repo>/pulls -f title=… -f head=<branch> -f base=main -f body=… -F draft=true`).
3. **Owner task, same turn.** Add the line `owns: fairbay/<repo>#<n>` to the Grove
   task this work belongs to (`grove_update_task`, notes), or create one
   (`grove_create_task`, notes start with the owner line, contractor-grade body).
   Without it the next gate reports the draft as G7, unowned.

Order matters: draft first, then the owner task, so the line names a real number.

## Close-at-land steps 1–8 (T3)

**Preconditions.**
- The PR is a draft and has an owner task.
- No other Claude PR in this repo is ready (I3). Run
  `pr_state.py report --repo fairbay/<repo>` (`.claude/skills/session-start/scripts/`,
  synced into every repo): any row G3–G6b other than this PR → ask
  Baylee about that PR (merge or close) in one tap and act only on his answer,
  even when another session opened it; or keep this one in draft. Two ready PRs
  would both rewrite HANDOFF.yaml. The standing-rules PR of step 2 is the one
  exception: it is merged before step 3, so it never overlaps.

**Steps, in order. Each is safe to re-run.**

1. **Route open items.** Scan the session: real work → Grove task; unconfirmed or
   ambiguous → HANDOFF `next:` only; a judgment call with options → adjudication.
   Every item created here carries `from: fairbay/<repo>#<n>`. Before creating,
   search for an item with that line and the same title; update it instead.
2. **Standing rules land now, separately.** A ruling Baylee made or changed this
   session goes to `main` by its own docs-only push (CLAUDE.md "Baylee's standing
   rules" plus the superseding Grove decision), not in this PR. Rulings belong to
   the session and stand even if the PR never merges. In a Code session that
   push is its own small PR from its own branch: body starts `Standing rules:`,
   opened ready (no owner task, no trailer: it is not a work PR), and merged at
   Baylee's tap before step 3. Left unmerged, the gate shows it as G6b, which is
   right: a ruling that never reached `main`.
3. **HANDOFF.yaml on the PR branch.** `meta.landing: fairbay/<repo>#<n>`. `done:`
   in pending tense ("Lands with #n: …"). `next:` pruned per
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
   - Project row: replace or append `LANDING fairbay/<repo>#<n>: <what lands>`
     in `next_actions` (`grove_update_project`; the array replaces the old one,
     so send every line). Re-read the row with `grove_get` in the same turn,
     right before the update, so another session's newer lines are kept.
   - Every task this PR completes: add `landing: fairbay/<repo>#<n>` to its
     notes and **leave it open**. It completes on merge (promotion).
   - Log decisions (`grove_log_decision`) as usual.
5. **Commit, then run the repo's `pre_ready` commands.** First commit everything
   in an ordinary commit (`git add -A`), so the checks see every file: a file
   created since the last commit is invisible to strip-working-files. Then run
   `pre_ready` from `.claude/landing.yaml` (MBN:
   `node scripts/batch/strip-working-files.mjs --apply`, then `npm run test:v4`;
   plus the suites MBN CLAUDE.md names for app, test or data changes). Any
   failure: stop, the PR stays a draft, fix it.

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
   strip-working-files without `--apply` exits 0 (where the repo has it). Keep the
   step-5 commit local until here: if `pre_ready` changed nothing (or the repo has
   none), `git commit --amend` that unpushed commit instead of making an empty one.
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
   first). Then `gh api -X POST repos/fairbay/<repo>/pulls/<n>/ccr/ready_for_review`.
   **In the same turn, before the tap or any further edit,** move off the PR
   branch: `git fetch origin main && git checkout -b <new branch> origin/main`.
   A session bound to one branch name instead waits for the merge (or the
   close), then starts that name again from `main`. The remote still holds the
   squashed-away commits (MBN keeps merged branches), so `git fetch origin
   <branch> && git merge FETCH_HEAD` once before the first push. Never force-push.
8. **Next-step line:** "#n is ready. Merge to land it: <link>." From here the chat
   can be dropped. Then go to the merge request below; the session itself goes on.

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

## Promotion after a merge

Run in-session after a merge, and at entry by session-start Phase 0 for every
merged PR a marker names (S2: Baylee merged on GitHub after the chat ended).

1. `pr_state.py check <n> --repo fairbay/<repo>` → `state: merged`, `merge_sha`,
   `deploy_state`, `commits_after_cal`.
2. Project row (re-read it right before the update): rewrite each
   `LANDING fairbay/<repo>#<n>: <text>` to `Merged #<n> <date> (<merge sha 8>): <text>`.
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

## Direct-to-main sessions (§7.7)

Chat pushes through git-ops, ops changes through `push_and_merge`,
content-batch archives: landing happens at the push. Run steps 1–3, and step 4's
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
