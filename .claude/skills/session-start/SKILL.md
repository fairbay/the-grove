---
name: session-start
description: >
  Session onboarding — "work on [project]", "continue [project]", or pasting a
  handoff doc. Loads handoff + PLAN. Not for mid-session (→ chat-status) or
  archiving (→ chat-archive).
metadata:
  version: "2026-05-24-01"
---

**Version gate:** Compare this skill's `metadata.version` against
`fairbay/baylee-skills/.claude/skills/session-start/SKILL.md` via git-ops
before doing anything else. If behind, warn once and continue. If fetch
fails, skip silently.

# session-start — orient a new session from handoff state

Fires on the first message of a session when Baylee names a project. Loads the
handoff, checks freshness, reads PLAN.md, and presents what's next — so the
session starts ready to work, not reconstructing context turn by turn.

**If you are about to start answering Baylee's question before loading the
handoff, stop.** Run Phase 1 first. The instinct to jump into problem-solving
skips the handoff, which forces context reconstruction later in the session
at higher cost.

## Trigger shapes

Fires for:
- "work on grove-web", "work on listing lens"
- "continue [project]", "resume [project]", "pick up where we left off"
- Any first message naming a known Fairbay project with continuation intent

Does NOT fire for:
- Mid-session topic shifts → chat-status
- "archive this", session-end signals → chat-archive
- A fresh idea with no prior work → idea-scout
- Generic greetings without a project reference → respond normally

## Phase 1 — Resolve project → repo

Map the project name to a GitHub repo under the `fairbay` user account.
Resolution order:

1. **Memory.** Known project↔repo mappings from userMemories (e.g. "Listing Lens"
   → `fairbay/listing-lens-api`, "Grove" → `fairbay/grove`).
2. **Grove ideas.** Search Grove ideas via MCP (`grove_list_ideas`) for the name.
   Ideas with `repo` or `github` fields resolve directly.
3. **Repo name match.** Try `fairbay/<kebab-case-project-name>` via git-ops
   `list_files`. If it exists, use it.
4. **Ask once.** If still unresolved, ask Baylee one direct question: "Which repo
   is this in?" — not a menu of guesses.

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
3. **Session handoff:** list `fairbay/operating-manual/handoffs/` via git-ops,
   filter filenames containing the project slug, read the most recent by date
   prefix.

Handoffs are surface-agnostic: `meta.surface` may be `claude-web`,
`claude-code`, or `routine`. Treat a Claude-Code-origin handoff exactly like a
chat-origin one — the schema is identical. (On the Claude Code surface this same
load happens automatically via a SessionStart hook; in chat it's this skill.)

If none resolves, skip to Phase 4 — the project may be new or pre-handoff.
Note this briefly and proceed.

## Phase 3 — Stale handoff check

A handoff from days ago can be overridden by a more recent chat. Always check.

1. Read `meta.generated` from the handoff YAML.
2. Call `recent_chats(after=<generated_timestamp>, n=5)`.
3. If any returned chat titles or snippets mention the same project, flag before
   proceeding: "There's a more recent chat on [project] — want me to pull
   context from there first?"
4. If nothing newer, proceed.

## Phase 4 — Load PLAN.md and CLAUDE.md

If the resolved repo has `PLAN.md`, read it via git-ops. This satisfies the
"read PLAN.md before working on a repo" requirement so downstream skills (build,
systematic-test, systematic-debug) don't refetch.

If PLAN.md is large (>3K tokens), note its presence and key section headings but
don't dump full contents. Downstream skills delegate extraction for the specific
step they need.

Also read `CLAUDE.md` if present — it carries project-specific conventions.

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

**Next up:**
[Items from handoff `next:`, numbered]

**Blockers:** [from `blocking_on:`, or "None"]
```

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
  `meta.surface` records origin. See `operating-manual/docs/session-continuity-SPEC.md` §11.
- **→ build / systematic-test / systematic-debug:** Hands off the loaded PLAN.md
  context so they don't refetch.
- **→ chat-status:** Mid-session checkpoints once work begins.
- **→ chat-archive:** Closing this session's work at the end.
