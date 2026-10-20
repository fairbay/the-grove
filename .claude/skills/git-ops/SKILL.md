---
name: git-ops
description: >
  Write to GitHub: "push this", "commit this", "create a repo",
  "what's in fairbay/X", or any task leaving files for a fairbay/* repo.
  Not for host setup (→ ship-it) or prototyping (→ build).
metadata:
  version: "2026-10-20-01"
---
**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# git-ops — push, read, list, create, delete on GitHub

Direct GitHub access via Git Data API or native git CLI. One commit per push, atomic. Works identically in Claude.ai chat and Claude Code (both proxy-authenticated for attached repos) — `scripts/git_push.py` auto-detects.

## When this fires

User-facing GitHub repo operations. The user wants the *push* (or read, or create) to happen — not deployment, not a prototype.

- "push this" / "commit this" → push files to a fairbay/* repo
- "push the fix to main" → existing repo update; Vercel auto-deploys as a side effect
- "create a repo for X" → spin up a new fairbay/* repo
- "what's in fairbay/foo?" / "read README from idea-vault" → repo read
- "delete the test repo" → Tier 3 destructive, plan-confirm first

Route elsewhere when:
- The user wants **new-host setup** (pick a host, configure, verify live) → ship-it
- The push happens **inside another skill's workflow** (build, architect, idea-scout, ship-it, chat-archive) → those skills follow `references/push-protocol.md` (in this skill), which calls `scripts/git_push.py`

Pushes to **already-live sites** stay here — Vercel auto-deploys on push, so a fix to a live repo is just a git-ops push.

## The push workflow

1. Write files to disk locally.
2. Test what's testable — `python -c`, `node -c`, `JSON.parse`, build runs. State what you verified inline.
3. `present_files` so Baylee can see what's landing **before** it lands.
4. Push via `scripts/git_push.py` — one atomic commit. For deploy-relevant pushes, call `push_and_verify()` instead of `push_files()` — same push plus live-URL deploy verification in one call.
5. Report the commit diff URL: `https://github.com/<owner>/<repo>/commit/<sha>`.
6. If `push_and_verify()` returned `TIMEOUT_STALE` or `UNREACHABLE` (or you used plain `push_files()` and need to check), escalate to the Vercel MCP diagnosis chain — `references/vercel-mcp.md`. The happy path needs zero MCP calls.

The diff URL is Baylee's review mechanism. Never push before presenting — `present_files` is the in-flight check.

## Setup

### Claude.ai chat

**No PAT.** The session's proxy authenticates GitHub for every repo attached
to the session. **If you are about to read `GITHUB_PAT` from Supabase Vault
(`vault.decrypted_secrets`), stop:** it puts a write-scoped token in the
transcript, which the "never read a key" rule forbids, and the proxy makes it
unnecessary.

1. Attach the repo: `add_repo(owner="fairbay", repo=<repo>, access="push")`
   (`access="read"` for read-only work). Skip if it's already attached.
2. For repeated reads or multi-file work, clone it shallow as the `add_repo`
   result says, then `register_repo_root`. `push_files`/`read_file`/
   `list_files` detect the clone and use native git through the proxy.
   Without a clone they use the API with the proxy's credentials.
3. Import the helper:

```python
import sys
for _p in [".claude/skills/git-ops/scripts", "/mnt/skills/user/git-ops/scripts"]:
    if __import__("os").path.isdir(_p): sys.path.insert(0, _p); break
from git_push import push_files, read_file, list_files, delete_repo, api
```

If `add_repo` is refused or missing, use the GitHub connector's tools if the
session has them; otherwise tell Baylee which repo needs attaching. Never
fall back to a stored token.

### Claude Code / Routines

The repo is cloned and the git proxy handles auth. `push_files`, `read_file`, and `list_files` auto-detect the local clone and use the native git CLI — no PAT setup needed. The interface is identical to the chat path.

API-path auth order: `$GITHUB_PAT` env var → `$GITHUB_PAT_PATH` → `/home/claude/github-pat.txt` → the session proxy (placeholder token; the proxy injects credentials for attached repos).

## The five operations

### Push (atomic multi-file commit)

```python
from git_push import push_files

files = [
    ("README.md", "/home/claude/readme.md"),  # (remote_path, local_path)
    ("src/app.py", "/home/claude/app.py"),
    ("data.json", b'{"key": "value"}'),       # bytes work too
]
sha, url = push_files("fairbay/my-repo", "main", "Commit message", files)
# url → https://github.com/fairbay/my-repo/commit/<sha>
```

One commit, one parent, all files atomic. Six API calls in the chat path; one git push in the clone path.

### Push + verify (deploy-relevant pushes)

```python
from git_push import push_and_verify

verdict = push_and_verify(
    "fairbay/my-repo", "main", "fix: nav crash (v2.4.1)", files,
    verify_url="https://myapp.vercel.app",   # or an /api/health endpoint
    expect="v2.4.1",                          # the version string this commit bumps
)
# verdict["state"] -> VERIFIED_LIVE | TIMEOUT_STALE | UNREACHABLE | PUSHED
```

One call collapses push → wait → poll → confirm. `expect` should be the
version string the same commit bumped — that is what makes a 200 mean "this
code is live", not "some code is live". `VERIFIED_LIVE` → report the verdict
and diff URL in one line, done. `TIMEOUT_STALE` / `UNREACHABLE` → run the
MCP diagnosis chain in `references/vercel-mcp.md`. Defaults: 180s timeout,
15s poll interval, 25s initial wait for Vercel pickup.

### Read

```python
content = read_file("fairbay/idea-vault", "ideas.json")  # str, UTF-8
```

For binary files or > 1MB, call `api()` directly with the contents endpoint and decode the base64 yourself.

### List

```python
paths = list_files("fairbay/idea-vault", "archive")
```

### Create a repo

```python
from git_push import api
code, body = api("POST", "/user/repos", {
    "name": "new-repo",
    "private": True,
    "auto_init": True,  # required — empty repos break the Git Data API
})
```

`fairbay` is a GitHub User account, not an Org. Use `/user/repos`, not `/orgs/fairbay/repos`. The `/orgs/...` path returns 404.

**After creation — Claude infrastructure.** When a new repo will be used
with Claude Code, push the `.claude/` infrastructure in the same session:
`.claude/global.md` (from `fairbay/ops/global-CLAUDE.md`),
`.claude/settings.json` (the managed hook entries, copied from `fairbay/ops/.claude/settings.json`), and
all skills from `fairbay/ops/.claude/skills/`. Skills must land
before the first Claude Code session — don't defer to `sync.py`.
Same procedure as ship-it Phase 3 step 6.

### Delete a repo (Tier 3 — destructive)

Plan and confirm before calling. `delete_repo` is irreversible.

```python
from git_push import delete_repo
delete_repo("fairbay/test-repo")
```

For deleting **files** (not repos), push with `sha: null` in the tree entry — see comments in `scripts/git_push.py`.

## Conventions for every push

The full push-time discipline (test → present → push → diff URL → optional verify) lives in `references/push-protocol.md` — other skills load that file when they push inside their workflows. When the user calls git-ops directly, these still apply:

- **Push to `main`** from chat. Code web sessions: `claude/*` branch, draft PR with an owner task, ready only via close-at-land (`references/push-protocol.md` §5).
- **Size gate before any PR goes ready:** no regenerable output, records one per line, a file over ~2,000 added lines or a binary over 1 MB only with a stated reason (chat-archive `references/close-at-land.md` step 5).
- **Bump the patch version** in `package.json` and any visible UI version display in the same commit.
- **Regenerate `package-lock.json`** (`npm install`) if `dependencies` / `devDependencies` changed, before committing.
- **Reply with the commit diff URL** — that's Baylee's review surface.

## Common gotchas

Placed near the operations above, summarized here:

- **NEVER use raw `git commit` / `git push` in chat sessions.** Always use `push_files()`. The function hardcodes the commit author identity to match the Vercel Hobby team owner. Raw git commands use whatever identity is in the container's git config (usually wrong), causing Vercel to BLOCK production deploys on private repos. This applies even when you've already cloned the repo — the clone is for reading, `push_files()` is for writing.
- Files already inside the clone may be passed by path as `(remote_path, local_path)`: `_push_via_cli` skips the copy when both are the same file. If the clone is on a different branch than the one you target, the push refuses with a clear error instead of pushing a ref that lacks the commit; check out the target branch first.
- Branch may be `master`, not `main`. Check with `api("GET", f"/repos/{r}")["default_branch"]` if a push 404s.
- Remote paths use forward slashes only. No leading `/`.
- Don't rewrite the push sequence from scratch — the bundled script handles blob/tree/commit/ref correctly.
- For binary or > 1MB reads, the contents endpoint returns base64 — `read_file` only handles UTF-8 text.
- **Egress proxy auth flap (claude.ai containers).** Symptom: valid PAT + bursty 401 "Requires authentication" + GitHub request-ids present in response. Cause: transparent egress proxy intermittently drops the Authorization header. This is NOT a PAT expiry — don't tell Baylee to regenerate a healthy token. `api()` retries 8 times with backoff; `push_files()` falls back to native git transport (shallow clone with `x-access-token:PAT@github.com`) on 401 exhaustion. If the flap persists across sessions, Baylee may want to report to Anthropic.
- **Cloud session limits: `gh api --paginate` fails through the session proxy.** The second page is requested by numeric repository id and the proxy answers 403 "Numeric-ID repository paths (repositories/{id}/...) are not supported through this proxy." The first page returns, so counts silently cover only the newest 100 rows. Page by hand instead: add `per_page=100&page=N` to the path and loop until a page comes back empty (or its last row is older than the window you need).

- **Cloud Code sessions refuse force-pushes**, `--force-with-lease` included, even to the session's own branch after its PR squash-merged. Without rewriting history: restart the branch from `origin/main`, then `git merge -s ours --no-edit origin/<branch>`, so the push is a fast-forward.
- **Mass removals need Baylee's explicit yes first** (the classifier refused a 246-file deletion until he approved in chat). Before pushing one, build from a `git archive HEAD` copy: files left on disk hide a missing input.

## Secret hygiene

- No session handles the GitHub PAT. Chat and Code go through the session proxy (attached repos); Routines use their clone. The PAT's remaining homes are the `GH_PAT` Actions secret on `fairbay/ops` (the sync workflow) and any Routine environment that sets `GITHUB_PAT`.
- To rotate it, make a new token at https://github.com/settings/personal-access-tokens, update `GH_PAT` (https://github.com/fairbay/ops/settings/secrets/actions) and the Routine environments, then revoke the old one.

## Integration

- **→ ship-it:** When new-host setup is the goal (pick host, configure, verify live).
- **← build, architect, idea-scout, ship-it, chat-archive:** When those skills push inside their own workflows, they follow `references/push-protocol.md` (this skill) and call `scripts/git_push.py` through it.
- **→ Vercel verification:** see `references/vercel-mcp.md` for the post-push deploy-state check.

## References

- `scripts/git_push.py` — the helper (reusable Python module + CLI).
- `references/push-protocol.md` — the disciplined push protocol other skills follow when their workflow reaches a push step.
- `references/vercel-mcp.md` — checking deploy state after a push.
