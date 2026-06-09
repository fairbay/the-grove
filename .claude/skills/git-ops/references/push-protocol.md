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

**If you are about to call `push_files()` from inside another skill's workflow without `present_files` first, stop.** Tool budget pressure, long sessions, and "obvious" diffs are not exceptions. Baylee reviews via commit diff URL after the fact — `present_files` is the in-flight check that keeps presents-before-pushes intact.

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
from git_push import push_files
sha, url = push_files("fairbay/<repo>", "main", "<message>", files)
```

One commit, all files. Deletions go in via `{ path, delete: true }`-style tree entries (see `scripts/git_push.py`).

CLAUDE.md push conventions — apply on every push from any skill:

- **Push to `main`.** No feature branches or PRs unless Baylee asked.
- **Bump the patch version** in `package.json` and any visible UI version display in the same commit. Without this, "is my new code live?" is guesswork.
- **Regenerate `package-lock.json`** (`npm install`) if dependency sections changed, before committing — Vercel installs from the lockfile.

### Claude Code web sessions (claude/* branch restriction)

Claude Code web sessions are forced to push to `claude/*` branches — direct
push to `main` is blocked. Use `push_and_merge()` as the default push path
for these sessions:

```python
from git_push import push_and_merge

sha, url = push_and_merge("fairbay/<repo>", "<message>", files)
```

This creates a temp branch, pushes, creates a PR, squash-merges, and deletes
the branch — all in one call. The returned SHA and URL point to the merge
commit on `main`. Vercel auto-deploys from the merge.

**When to use:** Any push from a Claude Code web session to a repo where
you want changes on `main`. The function auto-detects the need — if you're
already on a `claude/*` branch, this is the right path.

**Fallback:** If the merge fails (merge conflict, branch protection), the
error message includes the PR URL. Report it to Baylee — the PR is open
and can be manually merged.

## 6. Report the diff URL

Always reply with the commit diff link. This is the primary review mechanism.

Format:

> Pushed 3 files to fairbay/&lt;repo&gt; — [diff](https://github.com/fairbay/&lt;repo&gt;/commit/&lt;sha&gt;)

Include the Vercel project URL too if the repo is connected and the change is user-visible.

## 7. Verify deploy (when applicable)

If the repo is Vercel-deployed and the change is user-facing, verify the deploy state. The flow is in `vercel-mcp.md` (this same references/ directory):

1. `Vercel:list_deployments` filtered by `meta.githubCommitSha`.
2. Wait if `BUILDING` or `QUEUED`.
3. On `ERROR`, fetch `Vercel:get_deployment_build_logs` and surface to Baylee.
4. On `READY`, report the URL.

Skip verification for: doc-only commits, archive repos, vault-data pushes that don't affect a UI, or commits Baylee labelled WIP. Don't chase flaky builds more than once — two failures in a row, surface and stop.

## 8. Don't ask before pushing

Baylee reviews via commit diff after the fact. Asking "should I push?" breaks the pattern — `present_files` already gave him the in-flight view, and the diff URL gives him the post-flight one. Push autonomously.

The exception is Tier 3 destructive operations (cross-repo file deletions, repo deletes, force-push) — those route through git-ops with explicit plan-confirm.

## 9. Failure handling

Two attempts max. After the second failure, surface to Baylee.

| Symptom | Cause | Action |
|---|---|---|
| 422 on push | Branch mismatch (`main` vs `master`) or path issue | Check `default_branch`; fix and retry once |
| 404 on push | Repo missing or PAT/proxy lost access | Stop; report to Baylee |
| 5xx on push | Transient GitHub | Retry once with backoff |
| Build ERROR on Vercel | Code issue | Fetch logs, surface to Baylee — don't loop |

## 10. Deprecated patterns

The previous `pushcraft.vercel.app/api/auto-push` endpoint, `SECRET.txt` token file, `stash-confirm.html` fallback, and `vault-push` proxy are gone. If you see those names in memory edits or older skills, ignore them and use `git_push.py` directly.

## 11. Branch hygiene after squash-merge

This applies to cloud Claude Code / web sessions, where work lands via a branch + PR squash-merged to `main` (not the direct-to-`main` push of chat sessions).

A squash-merge puts a single **new** commit on `main` — it does not fast-forward your branch. Your branch still holds the original pre-squash commits, so it is now diverged from `main`. Reusing it for the next PR makes git treat your already-merged changes as new, and any file the next PR re-touches conflicts against `main`'s squashed copy.

**Rule: after a PR is squash-merged, stop committing on that branch.** Before the next unit of work, reset to the merged `main`:

```
git fetch origin main
git checkout -B <branch> origin/main   # or: git switch -c <fresh-branch> origin/main
```

Either way the next PR diffs cleanly. This is what caused the self-conflict on `baylee-skills#20` — one branch reused across `#18`/`#19`/`#20` squash-merges.

**Recovering an already-diverged branch:** `git merge origin/main`, resolve the re-touched files to *your branch's* version (it's the cumulative-correct state), commit, push.

**Multiple concurrent sessions:** two Code sessions on the same repo should use separate branches (they get auto-named ones) and avoid editing the same files — especially shared ones like `CLAUDE.md`. Squash-merges from one make the other's branch stale; each session resets to `main` per the rule above before new work.
