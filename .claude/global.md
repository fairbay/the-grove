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
3. **Exhaust the Decision Ladder before assigning to Baylee.** See the Decision Ladder section below. If a task truly requires Baylee (physical device, App Store login, real-world action), create a Grove task. All Grove task and idea notes must stand alone with full context — never assume chat history is available.
4. **Run review-panel on completed artifacts before presenting.** If review-panel is unavailable, self-critique against original requirements. Same standard applies to post-feedback revisions.
5. **Skip technical detail unless asked.** Baylee steers at the product level. Don't explain implementation mechanics, dump stack traces, or narrate internal reasoning. Surface: what changed, what works, what's next.
6. **Present Baylee-only actions as numbered next steps.** Deep-link to the exact page (not just the site). Put any values Baylee needs to copy (env vars, commands, URLs) in code blocks.
7. **Skills first.** When `.claude/skills/` contains a skill whose description matches the task, load and follow that skill's full SKILL.md workflow — don't handle it generically. Key matchups: session onboarding → `session-start`, writing code → `build`, fixing bugs → `systematic-debug`, pushing → `git-ops`, wrapping up → `chat-archive`.

## Decision Ladder

When you encounter a decision point during execution, follow this procedure in order. Do not skip rungs.

1. **Consult project documentation** — SPEC.md, PLAN.md, MISSION.md, CLAUDE.md, HANDOFF decisions, and `docs/decisions/` if it exists. If in claude.ai, also read the Decision Ledger (persistent artifact storage).
2. **Delegate to specialist** — Route the question to the appropriate lens before attempting to resolve it yourself or escalating. See Delegation Routing below.
3. **Make the call and document it** — Record the decision in HANDOFF.yaml under `decisions_made:` with: the decision, rationale, alternatives considered, confidence (high/medium/low), and whether it's reversible. In claude.ai, also write it to the Decision Ledger. This is expected autonomous competence, not a failure.
4. **Escalate to Baylee** — Only if truly unresolvable, irreversible, or mission-level. Present distilled: the decision needed, the context, and your recommendation.

Rung 3 is the expected operating mode for most decisions. The ladder exists to ensure decisions are informed (Rung 1), considered from the right angle (Rung 2), and documented (Rung 3) — not to avoid making them.

## Delegation Routing

Before escalating any question to Baylee, determine if it can be routed to a specialist:

- **UX / design judgment** → delegate-analytical (Sonnet)
- **Risk, security, feasibility challenges** → delegate-adversarial (Gemini Pro)
- **Fact-gathering, summarization, extraction** → delegate-mechanical (Haiku)
- **Cross-model validation of important decisions** → delegate-independent (Gemini)

Escalate to Baylee only for mission-level judgment, real-world actions he must perform, or decisions requiring his unique personal context. In claude.ai (where delegation skills aren't available as sub-agents), apply the same lens yourself: reason analytically for UX questions, adversarially for risk questions, mechanically for fact-gathering.

## Project Documentation

- **Skills** live in `fairbay/ops` (source of truth) and are synced to `.claude/skills/` in every repo via `ops/scripts/sync-skills.py`. **Never edit `.claude/skills/` in individual repos** — the sync overwrites it. Three-layer doc architecture: SPEC.md → PLAN.md → HANDOFF.md.
- **Before editing any skill file**, stop and load skill-creator-b first.
- **Before working on a named project**, use the `session-start` skill (`.claude/skills/session-start/`). If the skill is unavailable, load HANDOFF.md and read `next:` directly — don't start cold.
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

## Agent Delegation & Token Efficiency

In multi-agent jobs, the cost lever is the *model tier*, not delegation itself.

- **Tier sub-agent models to task difficulty — pass `model:` explicitly on every Agent call.**
  Mechanical work (apply/run a reviewed file, verify, hygiene/lint, format, simple search) → **haiku**.
  Structured transformation (extraction, text→code/SQL, reconciliation) → **sonnet**.
  Reserve **opus** for the orchestrator and genuinely hard reasoning. Delegating to an *opus*
  sub-agent protects the orchestrator's context window but does NOT reduce spend — an opus
  sub-agent doing trivial work is the most common waste.
- **Text-first, not visual.** Prefer extracted text (`pdftotext -layout`, HTML/text scrapes) over
  rendering PDFs/pages/screenshots as images. Visual inputs are the single largest token multiplier;
  use them only when text genuinely fails, and only for the specific page.
- **Keep the orchestrator thin.** Never read large files (big SQL, PDFs, transcripts) into the main
  thread — delegate review/apply to a cheap sub-agent and keep only the summary. Avoid repeated
  status polls and per-step narration.
- **Batch trivial operations into one cheap agent** rather than one agent per item (per-agent startup
  + retry overhead compounds, especially when infra is flaky).
- **Make delegated work resumable & idempotent.** Persist artifacts (commit generated files) so an
  infra/usage-limit failure costs a cheap retry, not a full re-spend. Decouple expensive generation
  from cheap application.
- **Pilot before fan-out.** Validate the approach on one representative item before mass-spawning;
  settle methodology first to avoid throwaway work.

## MCP Configuration

MCP servers are configured via `.mcp.json` at the repo root (not `claude mcp add`). Permissions use the `permissions.allow` schema (not the legacy `allowedTools` format). Master copies of both `.mcp.json` and permissions configs live in `fairbay/ops`.

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

**This is the single source of truth for cross-project preferences.** It lives in `fairbay/ops/global-CLAUDE.md` and is synced to `.claude/global.md` in every active repo. Each repo's root `CLAUDE.md` imports it via `@.claude/global.md`.

**To update cross-project preferences:** Edit this file, then run `scripts/sync-global.py` to push to all repos. Never edit `.claude/global.md` in individual repos directly — sync overwrites it.

**Why repo-committed, not just `~/.claude/CLAUDE.md`:** Cloud Claude Code web sessions run in ephemeral VMs cloned from GitHub. `~/.claude/` does not persist between web sessions. The repo-committed file is the only reliable persistence layer. `~/.claude/CLAUDE.md` is placed additionally on local machines for Desktop/CLI/VS Code coverage.
