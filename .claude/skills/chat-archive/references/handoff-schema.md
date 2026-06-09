# Handoff schema reference

Two handoff types share a core YAML structure. The next session's `session-start`
skill is the primary consumer — keep YAML compact and parseable by key.

## Core principle: the handoff is a baton, not a journal

A HANDOFF.yaml captures **what the next session needs to start working**. It is
not a changelog, not a project history, not an architecture doc, and not a
knowledge base. Every section is ephemeral — written by one session, consumed by
the next, then overwritten. Information that needs to persist across many
sessions belongs in the project's durable docs (CLAUDE.md, SPEC.md, PLAN.md,
docs/), not in the handoff.

**If a section is growing across sessions, something is being appended that
should have been encoded elsewhere and cleared.**

## Type decision

- **Build handoff** — session involved code changes in a product repo.
  `HANDOFF.yaml` lands at the repo root.
- **Session handoff** — strategic work, audits, skill updates, research,
  architectural decisions not tied to a single build. Pushes to
  `fairbay/ops/handoffs/YYYY-MM-DD-<slug>.yaml` via git-ops.
- **Both** — touched a product repo AND did strategic work. Generate both.

If in doubt, generate a session handoff. Cost of unnecessary: ~30s. Cost of
missing: minutes of search reconstruction next session.

**Heuristic:** If the only repo touched was `fairbay/ops`, this is a
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

decisions_made:
  - decision: "Switched to two-stage pipeline (prepare → analyze)"
    rationale: "Single-stage hit Vercel 60s timeout on large listings"
    alternatives: "Edge function (complex), background job (needs queue)"
    confidence: high
    reversible: true

next:
  - "Build the cache layer (Step 4 of PLAN.md)"
  - "Run calibration suite against 5 known listings"

context:
  relevant_repos:
    - "fairbay/listing-lens-api"
  blocking_on: []

# --- Build handoff sections (include only when non-empty) ---
files_changed:
  - path: "api/analyze.js"
    action: "rewritten"
    summary: "Accepts pre-assembled image package, no photo fetching"

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
```

## Section rules

Each section has a specific scope. Violating scope causes unbounded growth.

### `done:` — last session only, 1-3 items

Summarize what **this session** shipped. 1-3 bullet points. The next session's
`session-start` shows "most recent only, 1-3 lines" — anything beyond that is
never read. A prior session's `done:` items are replaced wholesale, not
appended to.

**Anti-pattern:** Accumulating every completed item across sessions. This turns
the handoff into a changelog that costs hundreds of tokens and provides zero
value. If you find yourself adding to existing `done:` items rather than
replacing them, stop — you're building a journal.

### `next:` — actionable items for the next session

Concrete work the next session should pick up. Prune aggressively:

- **Completed items** (verified via repo state, DB, or deploy) → remove.
- **Stale items** (superseded by later work or decisions) → remove.
- **Backlog items** (valid but not next-session priority) → move to a Grove
  task or PLAN.md, remove from handoff.

If `next:` has more than ~5 items, it's a backlog, not a handoff. Promote the
top 3-5 to `next:`, park the rest.

### `decisions_made:` — Rung 3 autonomous decisions for next-session review

Session-specific decisions made autonomously via the Decision Ladder (Rung 3).
These are NOT permanent architectural decisions — those go in project docs
(CLAUDE.md, SPEC.md, PLAN.md). These are the calls Claude made this session
that Baylee should see, especially low-confidence or irreversible ones.

Each entry is a structured object:

```yaml
decisions_made:
  - decision: "Used Upstash KV instead of Supabase for session cache"
    rationale: "Free tier sufficient, simpler auth, avoids second DB dependency"
    alternatives: "Supabase (heavier), in-memory (no persistence)"
    confidence: medium  # high | medium | low
    reversible: true    # true | false
```

**What goes here:** Every Rung 3 decision from the session — architectural
choices, scope calls, library picks, tradeoff resolutions. Not trivial
implementation details (variable names, file organization).

**Consumed by session-start.** The next session's Phase 5 orientation surfaces
these, flagging low-confidence and irreversible decisions for Baylee to review
or override. After review, they're cleared — not accumulated.

**Permanent decisions still go to project docs.** If a decision is significant
enough to outlive this handoff (architecture, stack choice, design principle),
encode it in CLAUDE.md or SPEC.md in the same commit. The `decisions_made:`
entry is the review copy — the project doc is the durable record.

### `architecture:` — omit when CLAUDE.md is current

The `architecture:` field exists for the case where an architecture change
happened this session and CLAUDE.md hasn't been updated yet. If CLAUDE.md
already reflects the current architecture (which it should — see "CLAUDE.md
maintenance" below), omit this section entirely.

**Anti-pattern:** Duplicating CLAUDE.md's architecture section in the handoff.
This creates two sources of truth that inevitably diverge.

### `learnings:` — omit; encode via encoding gate

The chat-archive encoding gate (step 3b') routes each learning to its durable
home: memory edit, skill update, Grove task, or CLAUDE.md. After encoding, the
learning is done — it does not also go in the handoff.

**Anti-pattern:** Accumulating learnings across sessions. If learnings are
present in a handoff, either the encoding gate didn't run or a session appended
without clearing. The correct state after a properly closed session is: no
learnings in the handoff.

### `files_changed:` — structured objects, last session only

When included, use the proper object format:

```yaml
files_changed:
  - path: "api/analyze.js"
    action: "rewritten"
    summary: "Accepts pre-assembled image package"
```

Not bare path strings. This section covers the **current session's** changes
only — it's replaced each session, not appended to. Omit entirely if the file
changes don't help orient the next session (e.g., routine seed file additions).

### `known_bugs:` — active bugs only

Bugs that have been fixed → remove. Bugs that have been parked → move to a
Grove task and remove. Only open, relevant bugs belong here.

### `parked:` — items moved out of scope with a location

Each item needs a `location:` (Grove task ID, PLAN.md section, etc.) so it can
be found. Items without a location are orphans. Clean up before pushing.

### `context:` — optional ambient state

`blocking_on:`, `relevant_repos:`, and optionally `notes:` for anything the
next session needs that doesn't fit elsewhere. Keep minimal.

## CLAUDE.md maintenance (conditional)

Before pushing the handoff, check whether this session changed any of:

- Repo structure (new directories, renamed files, removed modules)
- Stack or dependencies (new framework, swapped library, added service)
- Deployment config (new Vercel project, changed domain, new env vars)
- Architecture (new API endpoints, changed data flow, added MCP tools)
- Key decisions or project conventions
- Project state ("what's live / what's in development")

If YES for any affected repo with a CLAUDE.md: read the current CLAUDE.md via
git-ops, update the relevant sections, and include it in the handoff commit.
If the repo lacks a CLAUDE.md and the changes warrant one, create it (use
existing project CLAUDE.md files as templates).

If NO: skip. Most sessions don't trigger this — don't force it.

**This is the encoding path for decisions and architecture.** When a session
makes a significant decision or changes architecture, CLAUDE.md is updated in
the same commit as the handoff — not deferred to the next session.

## Delivery

- **Build handoff:** push `HANDOFF.yaml` AND all session artifacts (prototype
  source, specs, review prompts, design docs) to the project repo via
  **git-ops** in a single atomic commit. Session artifacts belong alongside the
  code — they're reference material for future sessions. Place artifacts in
  appropriate directories (`docs/` for specs, `public/` for client-facing
  code). Report the commit diff URL.
- **Session handoff:** push to
  `fairbay/ops/handoffs/YYYY-MM-DD-<slug>.yaml` via **git-ops** in
  a single commit. The next instance reads it with
  `read_file("fairbay/ops", "handoffs/YYYY-MM-DD-<slug>.yaml")` —
  no download, no upload, no copy-paste. Report the commit diff URL.

**Push-failure fallback:** if git-ops push fails after one retry, update the
project's Grove idea or task notes with the handoff YAML content. Prefix with
`## Session Handoff (YYYY-MM-DD)`. Tell Baylee the handoff landed in Grove.
Session-start's Phase 2 checks Grove idea notes as a fallback source.

**Slug guidance:** 2-4 kebab-case words describing the session topic
(`capture-architecture`, `listing-lens-v6-extraction`,
`skill-routing-update`). Keep under 40 chars total.

## Resumption convention (no blurb needed)

The handoff (HANDOFF.yaml in the project repo or session handoff in ops) is the
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
