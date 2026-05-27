---
name: chat-status
description: >
  Mid-session checkpoint — "where are we", "status update", "what's next",
  summaries, topic shifts. Use proactively. Not session start (→ session-start)
  or close (→ chat-archive).
metadata:
  version: "2026-05-27-02"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/baylee-skills` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# chat-status — lightweight mid-session checkpoint

Quick structured status. Fires when Baylee asks for progress, when Claude is
about to summarize, when topics shift, or when a build phase completes with
more work queued.

**If you are about to write a prose summary of what we've done this session,
stop. Use the format below instead.** The instinct to recap inline grows after
each shipped piece of work — that is exactly when the structured format
matters, because Baylee scans status, not prose.

**This skill is mid-session only. If the session is closing → chat-archive.**

## When to fire

1. **Always-emit on topic shift.** If the next turn would shift to a
   different project, feature, or workstream, emit a checkpoint *before*
   engaging the new topic. When the shift crosses projects, append a Gate 2
   line: "This is a good point for a new chat — say 'work on [project]' to
   pick up." This is automatic, not requested.
2. **On request.** "Where are we", "status", "what have we done", "recap",
   "what's next".
3. **On milestone.** A build phase completes and more phases remain.
   Checkpoint before continuing. Brief, not blocking.
4. **On self-summary.** When Claude is about to summarize accomplishments
   (even unprompted), use this format instead of prose.

## Output format

Inline markdown in the chat response. No artifacts, no files, no tool calls.
Three sections in order. Omit empty sections except **Your Next Step**, which
is always present.

```
---

**Done**
- Built and pushed chat-status skill to fairbay/baylee-skills
- Prototyped React artifact v1–v3

**Parked**
- VoiceGrade idea → Grove idea `14f44ffa`
- ANTHROPIC_API_KEY setup → Grove task

**Your Next Step**
1. Verify deploy at [vault.bayleemiller.org/pulse](https://vault.bayleemiller.org/pulse)
2. Start a new chat and say "work on grove-web"

---
```

## Format rules

### Done

Terse outcomes, lead with verbs. Only items that actually shipped, deployed,
pushed, created, or resolved — not plans or discussions. Outcomes, not
play-by-play.

### Parked

Tasks, ideas, or decisions captured but deferred. Include where each landed
(Grove task ID, Grove idea ID, memory edit number). Omit the section if
nothing was parked — capturing emptiness wastes a section header.

### Your Next Step

**Always present. Always last. Never omit.** A status without an actionable
next step is just a summary.

- Sequential steps: numbered (1, 2, 3).
- Parallel options: bulleted.
- Sub-steps: outline conventions (1 → a → i).
- External links: standard markdown links (clickable inline) — direct
  deep-link, not "go to Vercel".
- Confirm Claude can't do it directly before listing it.
- Attachment references: inline "see attached `filename.ext`".
- Continuing in this chat: one sentence, no link.
- Nothing needed: "Nothing — this workstream is complete."
- Requires a new chat: "Start a new chat and say 'work on [project].'" No
  kickoff blurb — the handoff doc provides context.

For longer multi-destination action items (env vars in Vercel + DNS in
Cloudflare), defer to chat-archive's full Step 6 formatting (group by
destination, state what's already done, etc.).

## Pre-emit scan

Before writing the status, scan the conversation for uncaptured items. **No
external tool calls** — no Grove, no git-ops, no web_fetch. Reflect task and
idea state from conversation context only. Reference IDs that already exist
from earlier in this session; do not create new Grove entries here. The
checkpoint reflects this session's work, nothing more.

## What checkpoint does NOT do

- External tool calls (no Grove, no git-ops, no web_fetch)
- Push anything to GitHub
- Apply memory edits
- Generate handoff documents
- Run verification passes
- Perform meta-analysis of session friction

These are all archive-tier activities. Checkpoints are zero-tool-call
markdown. If the work warrants verification or encoding → chat-archive.

## Anti-patterns

- **Wall of prose.** Status is structured. Use the three sections.
- **Restating the conversation.** Done items are outcomes, not play-by-play.
- **Missing "Your Next Step."** The whole point is actionable closure.
- **Punching out to Grove.** Don't burn tool budget on a mid-session ping.
- **Generating an artifact.** Status is inline markdown. No React, no HTML,
  no visualizer.
- **Leaking into archive territory.** No memory edits, no handoff push, no
  verification reads. Those belong to chat-archive.

## Integration

- **← session-start:** Picks up after orientation; runs at any milestone
  during the session.
- **→ chat-archive:** When the session is actually closing, hand off — don't
  try to do archive work here.
