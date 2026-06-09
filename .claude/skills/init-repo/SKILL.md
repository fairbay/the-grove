---
name: init-repo
description: >
  Set up .claude/ infrastructure in a repo — "init claude", "set up skills",
  "add claude config". Auto-fires from ship-it when .claude/ is missing.
  Not for deployment (→ ship-it) or skill editing (→ skill-creator-b).
metadata:
  version: "2026-06-09-01"
---

# init-repo — bootstrap .claude/ infrastructure in a repository

Set up the Claude Code infrastructure that makes a repo first-class in
Baylee's system: global preferences, settings with SessionStart hook, and
all synced skills. Without this, a repo's first Claude Code session starts
cold — no skills, no preferences, no handoff continuity.

## When this fires

- **From ship-it:** Phase 3 step 6 checks for `.claude/global.md`. If missing,
  routes here before proceeding with deploy.
- **From git-ops:** After `create` — new repos need infrastructure before
  their first Claude Code session.
- **Direct:** "init claude in this repo", "set up skills for X".

## Workflow

### 1. Check current state

Read the repo (via git-ops or local filesystem) for existing `.claude/` files.
Skip any step whose artifact already exists.

| File | Purpose | Source of truth |
|------|---------|-----------------|
| `.claude/global.md` | Cross-project preferences | `fairbay/ops/global-CLAUDE.md` |
| `CLAUDE.md` | Repo-level instructions | Must start with `@.claude/global.md` |
| `.claude/settings.json` | Hooks, permissions | CONVENTIONS.md § Session-continuity gates |
| `.claude/skills/*` | All 22+ skills | `fairbay/ops/.claude/skills/` |

### 2. Generate files

**`.claude/global.md`** — Copy verbatim from `fairbay/ops/global-CLAUDE.md`.
Do not customize per repo.

**`CLAUDE.md`** (if missing) — Create with:
```markdown
@.claude/global.md

# [repo-name]

[One-line description of what this repo is.]
```

**`.claude/settings.json`** — Create with the SessionStart hook from
CONVENTIONS.md:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "sh -c 'P=\"$HOME/.local/bin/session_handoff.py\"; if [ ! -f \"$P\" ]; then mkdir -p \"$(dirname \"$P\")\" && curl -fsSL -H \"Authorization: Bearer $GITHUB_PAT\" https://raw.githubusercontent.com/fairbay/ops/main/scripts/session_handoff.py -o \"$P\" 2>/dev/null; fi; [ -f \"$P\" ] && exec python3 \"$P\" inject; exit 0'"
          }
        ]
      }
    ]
  }
}
```

**`.claude/skills/`** — Read all files from `fairbay/ops/.claude/skills/`
and push them to the target repo. Do this in the same commit as the other
files — don't defer to a future `sync-skills.py` run.

### 3. Push

Push all files in a single atomic commit via git-ops:
`"init: add .claude/ infrastructure (global, settings, skills)"`

### 4. Verify

Confirm the push succeeded. Report what was created vs. what already existed.

## Gotchas

- **Don't customize global.md per repo.** The sync script overwrites it.
  Repo-specific instructions go in the root `CLAUDE.md`.
- **Skills must land before the first Claude Code session.** A session that
  starts without skills discovers none of the workflows.
- **The SessionStart hook needs `$GITHUB_PAT` at runtime.** It's available
  in Claude Code cloud sessions via env vars. The hook self-bootstraps — no
  setup script dependency.

## Integration

- **← ship-it:** Phase 3 step 6 routes here when `.claude/` is missing.
- **← git-ops:** After repo creation, init-repo sets up infrastructure.
- **→ sync-skills.py:** After init, the repo is auto-discovered by future
  sync runs (it now has `.claude/global.md`).
