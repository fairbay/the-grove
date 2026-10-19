---
name: init-repo
description: >
  Set up .claude/ infrastructure in a repo — "init claude", "set up skills",
  "add claude config". Auto-fires from ship-it when .claude/ is missing.
  Not for deployment (→ ship-it) or skill editing (→ skill-creator-b).
metadata:
  version: "2026-10-19-02"
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

**`.claude/settings.json`** — Copy the two managed hook groups verbatim from
`fairbay/ops/.claude/settings.json`: the SessionStart entry marked
`fairbay-managed:entry-gate` and the UserPromptSubmit entry marked
`fairbay-managed:capture`. Never retype them; the sync keeps them current from
then on (docs/hook-delivery/DESIGN.md §3.5).

**`.claude/skills/`** — Read all files from `fairbay/ops/.claude/skills/`
and push them to the target repo. Do this in the same commit as the other
files — don't defer to a future `sync.py` run.

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
- **The hooks run scripts that ship with the skills** (session-start and
  chat-archive `scripts/`): no download, no token. Skills and hooks land in the
  same commit.

## Integration

- **← ship-it:** Phase 3 step 6 routes here when `.claude/` is missing.
- **← git-ops:** After repo creation, init-repo sets up infrastructure.
- **→ sync.py:** After init, the repo is auto-discovered by future
  sync runs (it now has `.claude/global.md`).
