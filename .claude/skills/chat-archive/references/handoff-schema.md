# Handoff schema reference

Two handoff types share a core YAML structure. The next session's `session-start`
skill is the primary consumer — keep YAML compact and parseable by key.

## Type decision

- **Build handoff** — session involved code changes in a product repo.
  `HANDOFF.yaml` lands at the repo root.
- **Session handoff** — strategic work, audits, skill updates, research,
  architectural decisions not tied to a single build. Pushes to
  `fairbay/operating-manual/handoffs/YYYY-MM-DD-<slug>.yaml` via git-ops.
- **Both** — touched a product repo AND did strategic work. Generate both.

If in doubt, generate a session handoff. Cost of unnecessary: ~30s. Cost of
missing: minutes of search reconstruction next session.

**Heuristic:** If the only repo touched was `fairbay/baylee-skills`, this is a
session handoff. Build handoffs are for product code repos. Skill updates are
strategic/infrastructure work captured in session handoffs via `skills_changed`.

## Format: YAML

Both handoff types are YAML. Handoffs are by Claude, for Claude — the next
instance is the primary consumer. YAML is more token-efficient than markdown
and parseable by key rather than heading heuristics. No human-readable
companion file — YAML with comment headers renders cleanly on GitHub.

Build handoffs add `files_changed`, `architecture`, `known_bugs`. Session
handoffs add `memory_edits`, `skills_changed`.

```yaml
# Handoff: <title>

meta:
  generated: "YYYY-MM-DDTHH:MM:SSZ"
  project: "repo-or-topic-name"
  type: build  # "build" or "session"
  session_chat_id: null  # include if available

done:
  - "Rewrote api/analyze.js for two-stage pipeline"
  - "Fixed 504 timeout via image trimming in prepare.js"

decisions:
  - decision: "Two-stage analysis: prepare.js assembles, analyze.js sends"
    rationale: "Separates rate-limited photo fetching from Claude API call"

parked:
  - item: "Street View integration"
    location: "Grove task abc123"

next:
  - "Build the cache layer (Step 4 of PLAN.md)"
  - "Run calibration suite against 5 known listings"

context:
  relevant_repos:
    - "fairbay/listing-lens-api"
  blocking_on: []

# --- Build handoff sections ---
files_changed:
  - path: "api/analyze.js"
    action: "rewritten"
    summary: "Accepts pre-assembled image package, no photo fetching"

architecture: |
  Two-stage pipeline: prepare.js assembles image package with
  cc_ft_768 variants, analyze.js sends to Claude. Rate limiting
  at prepare stage. Max 60 images after trimming.

known_bugs:
  - bug: "504 on >80 images"
    root_cause: "Vercel 60s timeout"
    workaround: "Trimmed to 60 in prepare.js"

# --- Session handoff sections ---
# memory_edits:
#   - edit_number: 17
#     action: "replaced"
#     content: "Updated behavioral interrupt for chat-status"
# skills_changed:
#   - skill: "chat-status"
#     action: "rewritten"
#     summary: "Removed artifact generation, added always-emit trigger"

learnings:
  - type: "meta"
    finding: "Research before building visual artifacts for ephemeral data"
  - type: "tactical"
    finding: "YAML handoffs save ~40% tokens vs markdown for machine consumption"
```

## CLAUDE.md maintenance (conditional)

Before pushing the handoff, check whether this session changed any of:

- Repo structure (new directories, renamed files, removed modules)
- Stack or dependencies (new framework, swapped library, added service)
- Deployment config (new Vercel project, changed domain, new env vars)
- Architecture (new API endpoints, changed data flow, added MCP tools)
- Project conventions or "what's live / what's in development" state

If YES for any affected repo with a CLAUDE.md: read the current CLAUDE.md via
git-ops, update the relevant sections, and include it in the handoff commit.
If the repo lacks a CLAUDE.md and the changes warrant one, create it (use
existing project CLAUDE.md files as templates).

If NO: skip. Most sessions don't trigger this — don't force it.

## Delivery

- **Build handoff:** push `HANDOFF.yaml` AND all session artifacts (prototype
  source, specs, review prompts, design docs) to the project repo via
  **git-ops** in a single atomic commit. Session artifacts belong alongside the
  code — they're reference material for future sessions. Place artifacts in
  appropriate directories (`docs/` for specs, `public/` for client-facing
  code). Report the commit diff URL.
- **Session handoff:** push to
  `fairbay/operating-manual/handoffs/YYYY-MM-DD-<slug>.yaml` via **git-ops** in
  a single commit. The next instance reads it with
  `read_file("fairbay/operating-manual", "handoffs/YYYY-MM-DD-<slug>.yaml")` —
  no download, no upload, no copy-paste. Report the commit diff URL.

**Slug guidance:** 2-4 kebab-case words describing the session topic
(`capture-architecture`, `listing-lens-v6-extraction`,
`skill-routing-update`). Keep under 40 chars total.

## Resumption convention (no blurb needed)

The handoff (HANDOFF.yaml or session-handoff in operating-manual) is the
single source of truth for resumption. **Do not generate a session-start
blurb.** When Baylee says "work on [project]", `session-start` handles
onboarding: resolves repo, loads handoff, reads PLAN.md, presents orientation.
chat-archive's job ends at pushing the handoff.

**Prep steps still apply.** If Baylee needs to add a repo or set an env var
before next session, state that in the response body (plain text, not a code
block). These are instructions for Baylee, not onboarding context for Claude.

The Section 5 "Next step:" line phrases continuation as:
`**Next step:** When ready, start a new chat and say "work on [project]."`
Add any prep steps on the following line.
