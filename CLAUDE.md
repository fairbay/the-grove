<!-- SHARED:START -->
# Global Development Preferences

## Identity & Setup
- **Fairbay** — solo builder brand. `fairbay` is a GitHub User account (NOT an Org). Use `POST /user/repos`, not `/orgs/fairbay/repos`.
- **Baylee does not write code.** Claude is the sole coder across all surfaces. Baylee reviews, approves, and steers.
- **Three Claude surfaces** operate on Fairbay projects:
  - **Claude Code** — command-line agent with direct filesystem and git access. Reads this file. Best for repo-level builds, multi-file changes, debugging, testing, and git operations.
  - **Claude.ai Chat** — skills-driven sessions with connected MCP tools (Grove, Google Calendar, Gmail, Google Drive, Vercel, Hugging Face). Best for planning, architecture, idea evaluation, communication, research, artifacts, and skill-triggered builds.
  - **Routines** — API-triggered autonomous runs (e.g., scout-r, skill-worker-r). Fire-and-forget batch work with no interactive feedback.
- **Deploys via Vercel** — push to `main` → Vercel auto-deploy for connected repos.
- **Grove** is the central task/idea system (Supabase + Vercel API). MCP at `vault.bayleemiller.org/api/mcp`. All tasks and ideas go here — no iOS Reminders, no per-repo TODO.md for capture.
- **Skills** live in `fairbay/baylee-skills`. Source of truth. Three-layer doc architecture: SPEC.md (requirements), PLAN.md (technical approach), HANDOFF.md (session context).

## Git Workflow
- **Push to `main`** — no feature branches or PRs unless explicitly requested. Commit and push directly to main.
- **Version bump on every push** — increment the patch version in package.json (and any UI version displays) with every commit.
- **Lock file integrity** — after changing dependency sections, regenerate the lockfile with `npm install` before committing.
- **Always provide a link** to the commit on GitHub when completing work.

## Code Quality (do on every change, not as separate cleanup)
- **Only export what's consumed externally** — module-internal functions stay unexported.
- **Remove dead code immediately** — unused components, functions, CSS, config deleted in the same commit they become dead.
- **Deduplicate on sight** — same logic in 2+ places → extract a shared helper immediately.
- **Don't send unused data to APIs** — if a field isn't read by the endpoint, don't include it in the request payload.
- **CSS housekeeping** — when removing a component, also remove its associated keyframes, animation classes, and style rules in the same commit.
- **Trace feature plumbing end-to-end** — UI selection → state → API call → server handling → response → rendering. If any link is missing, the feature silently does nothing.

## Architecture Principles
- **Client-side generation > API generation** for anything deterministic. If you can generate it from data the API already returns (art, formatting, derived UI state), do it client-side.
- **Keep dev and production config in sync** — same model, same max_tokens, same parameters. Update both together.
- **Prompt caching** — for Anthropic API integrations, use `cache_control: { type: "ephemeral" }` on system prompts that don't change between calls.
- **Strip accumulated waste from context** — if historical messages contain large rendered content (images, SVG, formatted output), strip it before sending to the API.
- **Compact prompts** — prefer terse instruction language in system prompts. Remove filler words, redundant phrasing, excessive examples. Every token costs money and latency.

## Vercel Deployment
- **SSE streaming requires config** — serverless functions need `export const config = { supportsResponseStreaming: true }` to actually stream.
- **Runtime dependencies in `dependencies`** — packages used by serverless functions must be in `dependencies`, not `devDependencies`. Vercel only installs production deps at runtime.

## CSS / Layout
- **Flexbox scrolling** — `h-screen` (not `min-h-screen`) on the flex container + `min-h-0` on the scrollable flex child for `overflow-y-auto` to work.
- **Sticky headers in flex layouts** — use `shrink-0` on fixed headers within a `h-screen flex flex-col` layout, not `sticky` positioning.

## Testing & Validation
- **Test before pushing** — run syntax checks (`python -c`, `node -c`, `JSON.parse`) on generated files before committing.
- **Validate end-to-end after deploy** — call endpoints, check logs, verify behavior. Don't hand work back without self-testing.
- **Read PLAN.md before executing work** in any repo that has one. The plan prescribes technical approach; SPEC.md prescribes requirements.

## Communication Style
- Provide commit links after every completed unit of work.
- Keep summaries concise — tables for multi-item changes.
- When investigating, show the diagnosis before the fix.
- Don't promise future actions — do them first, then mention they're done.

<!-- SHARED:END -->

# the-grove

Nature-themed walking portfolio where each idea grows from seed to fruit-bearing tree. First-person perspective with infinite scroll loop.

**Live at:** [bayleemiller.org](https://bayleemiller.org)

## Architecture

- **Vite + React + Tailwind** — SPA with two views.
- **Garden** (`src/App.jsx`) — Walking perspective with SVG plants, perspective projection, click-to-modal details.
- **Vault Dashboard** (`/vault`) — Table view of all ideas with filters, sort, search.
- **Router** (`src/GroveRouter.jsx`) — Routes between garden and vault, fetches data, maps vault fields to garden props.
- **Data** (`public/vault.json`) — Single source of truth. Only `portfolio_visible: true` entries appear in the garden.

## Plant growth stages

| Status | Plant | Scale |
|--------|-------|-------|
| raw | Seed | 0.2x |
| scouted | Sprout | 0.35x |
| building | Sapling | 0.55x |
| in-dev | Young Tree | 0.75x |
| deployed | Flowering | 0.9x |
| shipped | Bearing Fruit | 1.0x |
| parked | Dormant | 0.6x |
| killed | Composted | 0.15x |

Pink flowers = impact score. Red fruit = business score. Counts relative to the highest-scoring project.

## Updating the portfolio

1. Update `public/vault.json` (add ideas, change statuses, toggle `portfolio_visible`)
2. Commit and push

Future: vault.json will be replaced by a live Grove API read (Phase C2) so the portfolio updates automatically when ideas change status in Grove.

## Deployment

Deployed at `bayleemiller.org` via Vercel.
