---
name: git-ops
description: >
  GitHub interface — "push this", "commit this", "create a repo", "push fix to
  live site", "what's in fairbay/X". Not for new-host setup (→ ship-it) or
  prototyping (→ build).
metadata:
  version: "2026-06-16-01"
---
**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# git-ops — push, read, list, create, delete on GitHub

Direct GitHub access via Git Data API or native git CLI. One commit per push, atomic. Works identically in Claude.ai chat (PAT-authenticated) and Claude Code (proxy-authenticated) — `scripts/git_push.py` auto-detects.

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
4. Push via `scripts/git_push.py` — one atomic commit.
5. Report the commit diff URL: `https://github.com/<owner>/<repo>/commit/<sha>`.
6. If the repo is Vercel-deployed and the change is user-visible, verify the deploy. See `references/vercel-mcp.md`.

The diff URL is Baylee's review mechanism. Never push before presenting — `present_files` is the in-flight check.

## Setup

### Claude.ai chat

PAT lives in Claude's memory edits. Set the env var before the first call:

```python
import os
os.environ["GITHUB_PAT"] = "<token from memory>"
```

Then import the helper:

```python
import sys
for _p in [".claude/skills/git-ops/scripts", "/mnt/skills/user/git-ops/scripts"]:
    if __import__("os").path.isdir(_p): sys.path.insert(0, _p); break
from git_push import push_files, read_file, list_files, delete_repo, api
```

### Claude Code / Routines

The repo is cloned and the git proxy handles auth. `push_files`, `read_file`, and `list_files` auto-detect the local clone and use the native git CLI — no PAT setup needed. The interface is identical to the chat path.

Token resolution order (chat path only): `$GITHUB_PAT` env var → `$GITHUB_PAT_PATH` → `/home/claude/github-pat.txt`.

## The four operations

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
`.claude/settings.json` (SessionStart hook template in CONVENTIONS.md), and
all skills from `fairbay/ops/.claude/skills/`. Skills must land
before the first Claude Code session — don't defer to `sync-skills.py`.
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

- **Push to `main`.** No feature branches or PRs unless Baylee asks.
- **Bump the patch version** in `package.json` and any visible UI version display in the same commit.
- **Regenerate `package-lock.json`** (`npm install`) if `dependencies` / `devDependencies` changed, before committing.
- **Reply with the commit diff URL** — that's Baylee's review surface.

## Common gotchas

Placed near the operations above, summarized here:

- Branch may be `master`, not `main`. Check with `api("GET", f"/repos/{r}")["default_branch"]` if a push 404s.
- Remote paths use forward slashes only. No leading `/`.
- Don't rewrite the push sequence from scratch — the bundled script handles blob/tree/commit/ref correctly.
- For binary or > 1MB reads, the contents endpoint returns base64 — `read_file` only handles UTF-8 text.
- **Egress proxy auth flap (claude.ai containers).** Symptom: valid PAT + bursty 401 "Requires authentication" + GitHub request-ids present in response. Cause: transparent egress proxy intermittently drops the Authorization header. This is NOT a PAT expiry — don't tell Baylee to regenerate a healthy token. `api()` retries 8 times with backoff; `push_files()` falls back to native git transport (shallow clone with `x-access-token:PAT@github.com`) on 401 exhaustion. If the flap persists across sessions, Baylee may want to report to Anthropic.

## Secret hygiene

- The PAT lives in Claude's memory edits in chat sessions. NOT in this skill, NOT in commits, NOT in user-visible output.
- If it leaks, rotate at https://github.com/settings/personal-access-tokens and update the memory edit. No skill rebuild needed.
- In Claude Code / Routines, the proxy handles auth — no token is stored or transmitted by the skill.

## Integration

- **→ ship-it:** When new-host setup is the goal (pick host, configure, verify live).
- **← build, architect, idea-scout, ship-it, chat-archive:** When those skills push inside their own workflows, they follow `references/push-protocol.md` (this skill) and call `scripts/git_push.py` through it.
- **→ Vercel verification:** see `references/vercel-mcp.md` for the post-push deploy-state check.

## References

- `scripts/git_push.py` — the helper (reusable Python module + CLI).
- `references/push-protocol.md` — the disciplined push protocol other skills follow when their workflow reaches a push step.
- `references/vercel-mcp.md` — checking deploy state after a push.
