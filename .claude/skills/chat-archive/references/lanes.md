# Lanes — one baton per lane

Only for a repo whose `.claude/landing.yaml` declares `lanes:` (MBN: `[a, b, c, d, e, f, h]`).
Without the key nothing here applies. Design and rule-set pass: `fairbay/ops` docs/lanes/DESIGN.md.

## Contents

- Layout
- Entry (session-start)
- Exit (chat-archive Step 9, close-at-land)
- After ready
- Limits and residuals

## Layout

| File | Holds | Written by |
|---|---|---|
| `HANDOFF.yaml` | `meta` (static: project, `layout: lanes`, a pointer) and `progress:`, one key per lane, a blank line between keys | each lane, its own `progress` line only |
| `handoffs/lane-<x>.yaml` | the lane's baton in the usual schema (`references/handoff-schema.md`): `meta` (lane, landing, session), its own `progress` detail, `done`, `next`, `carried_forward`, `decisions_made`, `watch_outs`, `parked` | that lane's session only |

- A `progress` line is one line of at most 200 characters (every lane's line rides every startup payload). It leads with the cross-lane figures as
  that lane last measured them (MBN: launch readiness, wording) and a date. Detail (guard,
  detector, session) goes in the lane file's own `progress:`.
- The Grove project row's lane line is the live cross-surface view (MBN PLAN.md "Tracks and lanes").
  When it and the lane file disagree, the newer one wins (session-start Phase 3's timestamp rule).
- Lanes run one session at a time. Work found for another lane is a Grove task tagged `lane-<x>`,
  never a line in that lane's file.
- **Dispatch** ("dispatch MBN" as a first message, session-start `references/dispatch.md`) reads
  these files, the row and the PRs in one turn and prints each lane's next prompt; it writes no baton.

## Entry (session-start)

1. **The lane is named in the first message** ("lane A", "lane A2"). The SessionStart hook shows
   HANDOFF.yaml's `progress` and a lane index (each lane's first `next:` item). The lane gate
   (`fairbay-managed:lane-gate`, a UserPromptSubmit hook: `session_handoff.py lane`) then injects
   that lane's `meta`, `next` and `carried_forward`, once per session.
2. **No baton injected** (a multi-repo or chat session, no lane named, the hook did not run): read
   `handoffs/lane-<x>.yaml` yourself for the lane the work belongs to. If the lane is unclear, the
   index and the project row's lane lines settle it; ask only if they do not.
3. Read back the lane's `next:` and show the project row's lane line beside it.
4. **Phase 0, a ready PR's baton:** for a Claude PR in G3–G5b, read its lane file from the PR head
   (`gh api "repos/fairbay/<repo>/contents/handoffs/lane-<x>.yaml?ref=<head_ref>" -H "Accept: application/vnd.github.raw"`)
   when its `meta.landing` names that PR.
5. **Another lane's ready PR is information, not a tap.** It does not block this session's work:
   two lanes' batons never touch the same line. A ready PR of this session's own lane is handled
   as Phase 0 says for any ready PR.

## Exit (chat-archive Step 9, close-at-land)

1. **Merge main first, once, before the baton is written** (close-at-land step 3):
   `git fetch origin main && git merge origin/main`. Only handoff files conflicted:
   `node .claude/skills/chat-archive/scripts/handoff-merge.mjs --lane <x>`. It takes this lane's
   file from the branch, every other lane's from main, and HANDOFF.yaml from main with this lane's
   `progress` line kept. It refuses (exit 1, nothing resolved for that path) when main changed this
   lane's own file or line since the merge base: another session of the lane landed. Read main's
   copy and write the baton on top of it; a re-run without that changes nothing. A branch cut
   before the split takes main's HANDOFF.yaml, and the script prints the branch's old `next:`:
   carry this lane's items into `write --lane <x>`, the rest into Grove tasks. Any other
   conflicted path is code, resolved as code. Never resolve a handoff file by hand.
2. **Write only this lane's baton:**
   `python3 .claude/skills/session-start/scripts/session_handoff.py write --lane <x>`, the body as
   JSON on stdin. A body's `progress_line` replaces only `  <x>:` in HANDOFF.yaml. A plain `write`
   refuses here (exit 2). The S8 backstop measures the startup payload and every lane's baton.
3. **close-at-land with lanes:** `meta.landing` goes in the lane file. Precondition I3 is per lane:
   a ready Claude PR blocks only when it touches this lane's file or line:
   `gh api "repos/fairbay/<repo>/pulls/<m>/files" --paginate --jq '.[].filename' | grep '^handoffs/lane-'`
   for each other ready row (G3–G6b), plus its HANDOFF.yaml patch. A PR outside every lane (a
   standing-rules PR, an ops rule change) writes no handoff file; its Grove `LANDING` marker is its
   record.
4. **policy-check** (step 5) also checks the lanes (check (e)): HANDOFF.yaml holds only `meta` and
   `progress`; keys are declared lanes, blank-separated, at most 200 characters, no duplicate top-level key; every lane file
   names a declared lane; the change touches at most one lane's baton against `origin/main`.
5. **The Next-step line names the lane:** `lane A: ` followed by the Go sentence verbatim (step 8).
   The lane word is what loads the baton next time; the Go sentence itself is Baylee's wording and
   is not changed.

## After ready

Handoff files no longer conflict between lanes. Other shared files still can (package.json's
version, CLAUDE.md, a rules file). A ready PR that goes dirty is put back to draft
(`ccr/convert_to_draft`), main is merged as in Exit step 1, and close-at-land runs again. At most
two such rounds; a third dirty state goes to Baylee with the ledger (global-CLAUDE.md "Loops and
Spin-Out").

## Limits and residuals

- The lane gate matches "lane" followed by a declared id. A routine's or scheduled task's prompt
  that names a lane loads that baton too (UserPromptSubmit has no origin field; accepted, as for
  the capture gate). A sentence like "the fast lane a bit" can load lane A once; harmless.
- The once-per-session state lives in the git dir (`fairbay-lanes.json`). A container restart or a
  new `session_id` loads the baton again on the next naming; harmless.
- A ruleset or branch protection that requires branches to be up to date would report every
  waiting lane PR as `behind` (pr_state: Failed). Do not enable that option on a lanes repo.
