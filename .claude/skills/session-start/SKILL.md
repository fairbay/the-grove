---
name: session-start
description: >
  Session onboarding — "work on [project]", "continue [project]", "keep working
  on X", or pasting a handoff. Loads handoff + PLAN. Not for mid-session
  (→ chat-status) or archive (→ chat-archive).
metadata:
  version: "2026-06-09-01"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# session-start — orient a new session from handoff state

Fires on the first message of a session when Baylee references prior work —
whether it's a named project, a Grove idea, or any topic with continuation
intent. Loads the handoff, checks freshness, reads PLAN.md, and presents
what's next — so the session starts ready to work, not reconstructing context
turn by turn.

**If you are about to start answering Baylee's question before loading the
handoff, stop.** Run Phase 1 first. The instinct to jump into problem-solving
skips the handoff, which forces context reconstruction later in the session
at higher cost.

## Trigger shapes

Fires for:
- "work on grove-web", "work on listing lens"
- "continue [project]", "resume [project]", "pick up where we left off"
- "keep working on X", "back to X", "let's continue X"
- Any first message with continuation intent about prior work — named project,
  Grove idea, research topic, or any work that had a previous session. Does not
  need to be an established project with a repo.

Does NOT fire for:
- Mid-session topic shifts → chat-status
- "archive this", session-end signals → chat-archive
- A fresh idea with no prior work → idea-scout
- Generic greetings without a project reference → respond normally

## Phase 1 — Resolve project → repo (or Grove idea)

Map the project name to a GitHub repo or Grove idea. Not all work has a repo —
pre-repo ideas, research, and early-stage projects resolve to Grove ideas
instead.

Resolution order depends on surface:

1. **Memory (chat) / CWD repo (Code).** In chat, use known project↔repo
   mappings from userMemories. In Code, the CWD repo IS the project — skip
   to Phase 2.
2. **Grove ideas.** Search Grove ideas via MCP (`grove_list_ideas`) for the name.
   Ideas with `repo` or `github` fields resolve to a repo directly. Ideas
   without a repo field are pre-repo — note the idea ID and proceed. The
   idea's notes may serve as context in Phase 2.
3. **Repo name match.** Try `fairbay/<kebab-case-project-name>` via git-ops
   `list_files`. If it exists, use it.
4. **Proceed or ask.** If the work likely has a repo (established product, prior
   builds), ask Baylee one direct question: "Which repo is this in?" If the
   work is pre-repo (new idea, research, early exploration), note this and
   proceed to Phase 2 — no repo is needed.

If a project name maps to multiple repos (e.g. "Grove" → `grove`, `grove-web`,
`grove-api`), pick the one with the most recent HANDOFF.yaml. If still
ambiguous, ask.

## Phase 2 — Load handoff

Resolution order — use the first that resolves:

1. **Inline handoff.** If Baylee pasted a handoff document in the conversation
   (a chat-archive blurb, YAML with `meta.generated`, or markdown with handoff
   frontmatter), use it as the primary source. Still run Phase 3 against it —
   a pasted handoff from 5 days ago should be flagged just like a repo
   handoff would be.
2. **Build handoff:** `HANDOFF.yaml` in the repo root via git-ops.
3. **Session handoff:** list `fairbay/ops/handoffs/` via git-ops,
   filter filenames containing the project slug, read the most recent by date
   prefix.
4. **Project BRIEF.md:** If the repo has a `BRIEF.md` at root (created by the
   build skill's lightweight interview), read it as planning context. BRIEF.md
   is a valid standalone planning artifact for small or early-stage projects
   that skipped architect.
5. **Grove idea notes.** If Phase 1 found a Grove idea (pre-repo or otherwise)
   and steps 1-4 found no handoff, read the idea via `grove_get`. If the
   idea's notes contain substantive context (architecture, build plan,
   decisions, scores), use them as the handoff-equivalent. Present in Phase 5
   as "picked up from Grove idea ([date])."

Handoffs are surface-agnostic: `meta.surface` may be `claude-web`,
`claude-code`, or `routine`. Treat a Claude-Code-origin handoff exactly like a
chat-origin one — the schema is identical. (On the Claude Code surface this same
load happens automatically via a SessionStart hook; in chat it's this skill.)

If none resolves, skip to Phase 4 — the project may be new or pre-handoff.
Note this briefly and proceed.

## Phase 3 — Stale handoff check

A handoff from days ago can be overridden by a more recent chat. Always check.

1. Read `meta.generated` from the handoff YAML.
2. Check for newer sessions:
   - **Chat:** call `recent_chats(after=<generated_timestamp>, n=5)`.
   - **Code:** check `git log --since=<timestamp>` for newer commits in the
     repo, or check ops/handoffs/ for newer session handoffs.
3. If anything newer mentions the same project, flag before proceeding.
4. If nothing newer, proceed.

## Phase 4 — Load PLAN.md (or BRIEF.md) and CLAUDE.md

If the resolved repo has `PLAN.md`, read it via git-ops. This satisfies the
"read PLAN.md before working on a repo" requirement so downstream skills (build,
systematic-test, systematic-debug) don't refetch.

If no PLAN.md exists but `BRIEF.md` does, read BRIEF.md instead — it serves as
the lightweight planning artifact for projects that skipped architect.

If PLAN.md is large (>3K tokens), note its presence and key section headings but
don't dump full contents. Downstream skills delegate extraction for the specific
step they need.

Also read `CLAUDE.md` if present — it carries project-specific conventions.

## Phase 4b — Maturity checkpoint

After loading CLAUDE.md and PLAN.md (or noting their absence), run a quick
heuristic to detect when a project has outgrown its planning level.

**Flag when ALL of the following are true:**
- The repo has no `SPEC.md` at the root
- The repo has ≥20 commits (check via git-ops `api("GET", "/repos/{r}/commits?per_page=1")` and read the `Link` header for total pages, or just check if page 1 returns 20+ results)
- The repo has a database schema, a `docs/` directory, or ≥5 source files

When flagged, include a one-line note in the Phase 5 orientation:

```
⚠️ This repo has [N commits] and no SPEC.md — consider a retroactive
spec pass (architect interview mode) to establish a quality contract
before public launch.
```

This is informational, not blocking. Baylee decides whether and when to run
the spec pass. The flag exists because express-mode plans are ephemeral by
design (see architect skill), and projects that grow past prototype scope
need the quality contract (acceptance criteria, success metrics, out-of-scope
list) that only interview mode produces.

## Phase 5 — Orient (read-back gate)

Present a brief orientation — and treat it as a **read-back**: explicitly name
the handoff you loaded and its `next:` items before any work begins. This is the
entry gate (the I-PASS "synthesis" step from the session-continuity spec): the
receiving session confirms it caught the baton before acting on it. Not a wall
of text — a quick status that gets Baylee into the work.

```
**[Project Name]** — picked up from [handoff type] ([date])

**Where we left off:**
[1-3 lines from handoff `done:` — most recent only]

**Decisions to review:**
[From `decisions_made:` — see below. Omit if empty.]

**Next up:**
[Items from handoff `next:`, numbered]

**Blockers:** [from `blocking_on:`, or "None"]
```

#### Surfacing `decisions_made:`

If the handoff contains `decisions_made:` entries, surface them in the
orientation between "where we left off" and "next up." Priority ordering:

1. **Low-confidence + irreversible** — flag prominently: "⚠️ Needs review:"
2. **Low-confidence + reversible** — note for awareness: "FYI, can be changed:"
3. **Medium-confidence** — list briefly
4. **High-confidence** — omit from orientation unless Baylee asks

For flagged decisions (categories 1-2), include the `alternatives` field so
Baylee can redirect without researching from scratch. Wait for Baylee to
acknowledge or override before proceeding with work that depends on these
decisions.

If no handoff was found:

```
**[Project Name]** — no handoff found

Ready to work. What's the focus?
```

### Then wait

Do NOT auto-start building, pushing, or executing. The orientation is a
checkpoint — Baylee confirms or redirects before work begins.

**One exception:** if the handoff `next:` section contains a single clear,
unambiguous task AND Baylee said "work on" (not "check on", "status of"),
proceed directly after presenting the orientation. The handoff itself is the
confirmation.

## Anti-patterns

- **Skipping the stale check.** A 3-day-old handoff may be overridden by
  yesterday's work. Always run Phase 3.
- **Using conversation_search as a handoff substitute.** If no handoff is
  found, present "no handoff found" and ask — don't run multiple search calls
  to reconstruct context from chat fragments. That's slower, noisier, and
  produces lossy context.
- **Running this skill in Code when the SessionStart hook already injected
  handoffs.** In Code, the hook handles Phase 2 automatically. This skill
  adds Phase 4-5 (PLAN.md loading + orientation) on top.
- **Dumping the entire PLAN.md.** Load it into context; don't narrate it.
  Downstream skills extract the step they need.
- **Re-deriving the plan.** If PLAN.md exists, the approach is settled. Don't
  second-guess during orientation.
- **Asking which repo when it's obvious.** "Work on Listing Lens" maps to one
  repo. Don't ask.
- **Auto-starting work.** Orientation first, confirmation second, work third —
  except the singular-unambiguous-task carve-out.

## Integration

- **← chat-archive:** Reads the handoff that chat-archive pushed at last
  session's end.
- **↔ Claude Code:** On the Claude Code surface the entry gate is a SessionStart
  hook (`scripts/session_handoff.py inject`) that injects the same handoffs as
  `additionalContext` before the first turn. Handoffs flow either direction;
  `meta.surface` records origin. See `ops/docs/session-continuity-SPEC.md` §11.
- **→ build / systematic-test / systematic-debug:** Hands off the loaded PLAN.md
  context so they don't refetch.
- **→ chat-status:** Mid-session checkpoints once work begins.
- **→ chat-archive:** Closing this session's work at the end.
