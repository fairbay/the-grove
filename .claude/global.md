# Fairbay — Global Preferences

## Identity & Workflow

Fairbay is a solo builder brand. `fairbay` is a GitHub **User** account (not an Org) — use `POST /user/repos`, not `/orgs/fairbay/repos`.

**Baylee does not write code.** Claude is the sole coder across all surfaces. Baylee reviews, approves, and steers. Three Claude surfaces operate on Fairbay projects:

- **Claude Code** — filesystem, git, builds, debugging, testing, deploys. Best for repo-level work, multi-file changes, and git operations.
- **Claude.ai Chat** — planning, architecture, idea evaluation, communication, research, artifacts, skills. Best for cross-project thinking and skill-driven workflows.
- **Routines** — API-triggered fire-and-forget batch work (e.g., scout-r, skill-worker-r). No interactive feedback. Convention: `-r` suffix on Routine names.

## Non-Negotiable Rules

1. **Aggressive asymmetric labor loading.** Every task defaults to Claude doing the work. Never design steps where Baylee runs commands, scripts, curl, or manual verification. If Claude has the tooling, Claude does it.
2. **Do it first, mention after.** Never promise a future action — execute, then report the result.
3. **Try to accomplish tasks directly before assigning to Baylee.** If truly impossible (requires physical device, App Store login, etc.), create a Grove task. All Grove task and idea notes must stand alone with full context — never assume chat history is available.
4. **Run review-panel on completed artifacts before presenting.** If review-panel is unavailable, self-critique against original requirements. Same standard applies to post-feedback revisions.
5. **Skip technical detail unless asked.** Baylee steers at the product level. Don't explain implementation mechanics, dump stack traces, or narrate internal reasoning. Surface: what changed, what works, what's next.
6. **Present Baylee-only actions as numbered next steps.** Deep-link to the exact page (not just the site). Put any values Baylee needs to copy (env vars, commands, URLs) in code blocks.

## Project Documentation

- **Skills** live in `fairbay/baylee-skills` (source of truth) and are synced to `.claude/skills/` in every repo via `code-extensions/scripts/sync-skills.py`. **Never edit `.claude/skills/` in individual repos** — the sync overwrites it. Three-layer doc architecture: SPEC.md → PLAN.md → HANDOFF.md.
- **Before editing any skill file**, stop and load skill-creator-b first.
- **Before working on a named project**, load its HANDOFF.md and read `next:` first — don't start cold.
- **Read PLAN.md before executing work** in any repo that has one. PLAN prescribes technical approach; SPEC prescribes requirements. "Build" tasks reference PLAN only. "Test," "debug," or "fix" tasks reference both PLAN and SPEC.
- **If work reveals a spec, plan, or skill is wrong**, flag the conflict and propose the update — don't modify upstream artifacts without confirmation.

## Task & Idea Capture

**Grove** is the central system (Supabase + Vercel API). MCP at `vault.bayleemiller.org/api/mcp`. ALL tasks and ideas go here — no iOS Reminders, no per-repo TODO.md.

## Git Workflow

- Push to `main` directly — no feature branches or PRs unless explicitly requested.
- Version bump (patch) in package.json on every push.
- Regenerate lockfile with `npm install` after dependency changes, before committing.
- Provide a commit link after every completed unit of work.

## Code Quality (every change, not separate cleanup)

- Only export what's consumed externally.
- Remove dead code in the same commit it becomes dead.
- Deduplicate on sight — same logic in 2+ places → shared helper.
- Don't send unused data to APIs.
- CSS housekeeping — remove associated keyframes/styles when removing a component.
- Trace feature plumbing end-to-end: UI → state → API → server → response → render. Missing links = silent failures.

## Architecture Principles

- Client-side generation > API generation for anything deterministic.
- Keep dev and production config in sync — same model, same params.
- Prompt caching — use `cache_control: { type: "ephemeral" }` on stable system prompts.
- Strip accumulated waste from context (large rendered content in message history).
- Compact prompts — terse instruction language, no filler.

## MCP Configuration

MCP servers are configured via `.mcp.json` at the repo root (not `claude mcp add`). Permissions use the `permissions.allow` schema (not the legacy `allowedTools` format). Master copies of both `.mcp.json` and permissions configs live in `fairbay/code-extensions`.

## Vercel Deployment

- Deploys via push to `main` → Vercel auto-deploy for connected repos.
- SSE streaming requires `export const config = { supportsResponseStreaming: true }`.
- Runtime packages in `dependencies`, not `devDependencies`.

## CSS / Layout

- Flexbox scrolling: `h-screen` (not `min-h-screen`) + `min-h-0` on scrollable flex child.
- Sticky headers in flex layouts: `shrink-0`, not `sticky`.

## Testing & Validation

- Test before pushing — syntax checks (`python -c`, `node -c`, `JSON.parse`) on generated files.
- Validate end-to-end after deploy — call endpoints, check logs, verify behavior.
- Never make Baylee the test runner. If Claude has access to the endpoint, database, or deploy pipeline, Claude runs the verification.

## Communication Style

- Concise summaries — tables for multi-item changes.
- Diagnosis before fix when investigating.
- Don't promise future actions — do them first.

## Cost Assumptions

- Apple Developer Program ($99/yr) is a sunk cost. Never penalize scores, viability, or cost analysis for requiring it. Treat as $0.

## About This File

**This is the single source of truth for cross-project preferences.** It lives in `fairbay/code-extensions/global-CLAUDE.md` and is synced to `.claude/global.md` in every active repo. Each repo's root `CLAUDE.md` imports it via `@.claude/global.md`.

**To update cross-project preferences:** Edit this file in code-extensions, then run `scripts/sync-global.py` to push to all repos. Never edit `.claude/global.md` in individual repos directly — sync overwrites it.

**Why repo-committed, not just `~/.claude/CLAUDE.md`:** Cloud Claude Code web sessions run in ephemeral VMs cloned from GitHub. `~/.claude/` does not persist between web sessions. The repo-committed file is the only reliable persistence layer. `~/.claude/CLAUDE.md` is placed additionally on local machines for Desktop/CLI/VS Code coverage.
