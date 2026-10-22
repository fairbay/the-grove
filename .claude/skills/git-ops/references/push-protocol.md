# Push protocol — for skills calling git_push.py inside a workflow

Other skills (build, architect, ship-it, idea-scout, chat-archive) reach a step where they need to push. This file is the disciplined push protocol they follow: test → present → push atomically → report diff → verify deploy when applicable.

It is **not user-facing**. When Baylee says "push this" or "deploy this", git-ops or ship-it handle it directly — this protocol fires only as part of another skill's workflow.

The actual push mechanism is `scripts/git_push.py` (in git-ops). Don't re-implement the blob/tree/commit/ref dance — it's solved.

## Contents

1. Behavioral interrupt
2. Inventory the commit
3. Test what's testable
4. Present before pushing
5. Push atomically
6. Report the diff URL
7. Verify deploy
8. Don't ask before pushing
9. Failure handling
10. Deprecated patterns
11. Branch hygiene after squash-merge

## 1. Behavioral interrupt

**If you are about to call `push_to_pr()` from inside another skill's workflow without `present_files` first, stop.** Tool budget pressure, long sessions, and "obvious" diffs are not exceptions. Baylee reviews via commit diff URL after the fact — `present_files` is the in-flight check that keeps presents-before-pushes intact.

## 2. Inventory the commit

List every file going into this push:
- Repo path (destination)
- Source (generated, edited, deleted)

If more files might land in this same session for the same repo, batch them. One atomic commit beats three small ones — easier to review, easier to revert.

## 3. Test what's testable

Before pushing, verify what you can:
- `python -c "import x"` for Python imports
- `node -c x.js` for JS syntax
- `json.loads(open(x).read())` for JSON
- `npm run build` if deploy hinges on a build artifact

State what you verified inline — "Pushed 2 files: linted clean, ESM export confirmed" beats "pushed."

If a file was inferred from pieced-together conversation, fetch the current version with `read_file()` from git-ops first. Pushing a fragment overwrites work.

## 4. Present before pushing

Call `present_files` for every file in the commit. Baylee sees the actual contents in chat **before** they land in the repo.

If the file list is long (5+), present the most important and note which others are included. Don't skip the step itself.

## 5. Push atomically

Delegate to git-ops:

```python
from git_push import push_to_pr
sha, url, pr = push_to_pr("fairbay/<repo>", "claude/<topic>", "<message>", files,
                          body="<what and why>")
```

One commit, all files, on a `claude/*` branch with a draft PR (opened if the branch has none). `push_files()` refuses any branch outside `claude/*`, `main` included: every surface lands by pull request (Baylee's ruling 3fa9a61e, 2026-10-21). Deletions go in via `{ path, delete: true }`-style tree entries (see `scripts/git_push.py`).

CLAUDE.md push conventions — apply on every push from any skill:

- **Land by PR from every surface**: chat, Code and routines push `claude/*` branches and land through the PR (below). A handoff-only archive is a PR too.
- **Bump the patch version** in `package.json` and any visible UI version display in the same commit. Without this, "is my new code live?" is guesswork.
- **Regenerate `package-lock.json`** (`npm install`) if dependency sections changed, before committing — Vercel installs from the lockfile.

### Landing the PR

`push_and_merge()` is the one-call landing for a `self`-policy repo (ops; it refuses any other):

```python
from git_push import push_and_merge

sha, url = push_and_merge("fairbay/<repo>", "<message>", files)
```

This creates a temp `claude/auto-*` branch, pushes, creates a PR, squash-merges,
and deletes the branch — all in one call. The returned SHA and URL point to the
merge commit on `main`. If the merge fails (merge conflict, a refusal), the
error message includes the PR URL: hand it off with close-at-land, or ask the
merge tap at once.

**Which path, by repo policy** (`.claude/landing.yaml`, `merge_policy`):
- `self` (ops): `push_and_merge()` for small infrastructure changes, as above.
- `policy` (MBN): the repo's `.claude/policy.json` decides — ruled upkeep
  merges itself under close-at-land's three conditions (`policy: upkeep`), a
  change of direction keeps the tap (`policy: direction`); with the file
  missing pr_state reports the fallback and every PR keeps the tap.
- `tap` (a product repo without a policy file; every PR keeps the tap), or any work spanning more than one turn: a
  draft PR plus an owner task when the work starts, and close-at-land to hand it
  off (chat-archive `references/close-at-land.md`). Never mark such a PR ready
  any other way.

#### PR routes through the session proxy

GraphQL is refused in chat and Code sessions; the refusal names the proxy's
own routes. Probed 2026-10-13 from a chat session with fairbay/ops and
medicaid-benefits-navigator attached.

| Route | Result |
|---|---|
| `POST /repos/{o}/{r}/pulls/{n}/ccr/ready_for_review` | Works. |
| `POST /repos/{o}/{r}/pulls/{n}/ccr/convert_to_draft` | Works. The only way back to draft without GraphQL; GitHub's public REST has none. |
| `PUT\|DELETE /repos/{o}/{r}/pulls/{n}/ccr/auto_merge` | 422 "Auto merge is not allowed for this repository" on Free private repos. |
| `GET /repos/{o}/{r}/pulls/{n}/ccr/review_threads` | Named by the proxy, not tested. |
| `POST /repos/{o}/{r}/pulls/{n}/ccr/comments/{id}/resolve` and `/unresolve` | Named by the proxy, not tested. |
| `PUT /repos/{o}/{r}/pulls/{n}/merge` | Works from chat with repos attached, after Baylee's in-conversation tap. A Code-tab session refused an unapproved merge on 2026-10-10 ("Merge Without Review"). |

## 6. Report the diff URL

Always reply with the commit diff link. This is the primary review mechanism.

Format:

> Pushed 3 files to fairbay/&lt;repo&gt; — [diff](https://github.com/fairbay/&lt;repo&gt;/commit/&lt;sha&gt;)

Include the Vercel project URL too if the repo is connected and the change is user-visible.

## 7. Verify deploy (when applicable)

If the repo is Vercel-deployed and the change is user-facing, verify once the PR has merged: call `verify_live()` with the merge sha, the live URL and the version string the PR bumped:

```python
from git_push import verify_live
verdict = verify_live(merge_sha, merge_url,
                      verify_url="https://<app>.vercel.app", expect="v<bumped>")
```

- `VERIFIED_LIVE` → report verdict + diff URL in one line. Done — zero Vercel MCP calls.
- `TIMEOUT_STALE` / `UNREACHABLE` → escalate to the MCP diagnosis chain in `vercel-mcp.md` (`list_deployments` by commit sha → build logs on `ERROR`).

Skip verification for: doc-only commits, archive repos, vault-data pushes that don't affect a UI, or commits Baylee labelled WIP. Don't chase flaky builds more than once — two failures in a row, surface and stop.

## 8. Don't ask before pushing

Baylee reviews via commit diff after the fact. Asking "should I push?" breaks the pattern — `present_files` already gave him the in-flight view, and the diff URL gives him the post-flight one. Push autonomously.

The exception is Tier 3 destructive operations (cross-repo file deletions, repo deletes, force-push) — those route through git-ops with explicit plan-confirm.

## 9. Failure handling

Two attempts max. After the second failure, surface to Baylee.

| Symptom | Cause | Action |
|---|---|---|
| `refused: push to 'main'` | A push aimed outside `claude/*` (ruling 3fa9a61e) | Push the branch with `push_to_pr()`; never retry under another path |
| 422 on push | Base mismatch (`main` vs `master`) or path issue | Check `default_branch`; pass `base=`; retry once |
| 404 on push | Repo missing or PAT/proxy lost access | Stop; report to Baylee |
| 5xx on push | Transient GitHub | Retry once with backoff |
| Build ERROR on Vercel | Code issue | Fetch logs, surface to Baylee — don't loop |

## 10. Deprecated patterns

The previous `pushcraft.vercel.app/api/auto-push` endpoint, `SECRET.txt` token file, `stash-confirm.html` fallback, and `vault-push` proxy are gone. If you see those names in memory edits or older skills, ignore them and use `git_push.py` directly.

## 11. Branch hygiene after squash-merge

This applies to every session: work lands via a branch + PR squash-merged to `main`.

A squash-merge puts a single **new** commit on `main` — it does not fast-forward your branch. Your branch still holds the original pre-squash commits, so it is now diverged from `main`. Reusing it for the next PR makes git treat your already-merged changes as new, and any file the next PR re-touches conflicts against `main`'s squashed copy.

**Rule: after a PR is squash-merged, stop committing on that branch.** Before the next unit of work, reset to the merged `main`:

```
git fetch origin main
git checkout -B <branch> origin/main   # or: git switch -c <fresh-branch> origin/main
```

Either way the next PR diffs cleanly. This is what caused the self-conflict on `baylee-skills#20` — one branch reused across `#18`/`#19`/`#20` squash-merges.

**Recovering an already-diverged branch:** `git merge origin/main`, resolve the re-touched files to *your branch's* version (it's the cumulative-correct state), commit, push.

**Multiple concurrent sessions:** two Code sessions on the same repo should use separate branches (they get auto-named ones) and avoid editing the same files — especially shared ones like `CLAUDE.md`. Squash-merges from one make the other's branch stale; each session resets to `main` per the rule above before new work.
