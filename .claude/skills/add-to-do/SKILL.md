---
name: add-to-do
description: >
  Task capture and triage — "add to do", "remind me to", "show my to-dos",
  "done with X", "drop X". Also project feature ideas. Not standalone ideas
  (→ idea-scout) or scoring (→ idea-vault).
metadata:
  version: "2026-05-27-02"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/baylee-skills` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# add-to-do — task-shaped capture and CRUD

A thin router. Claude classifies the task, calls Grove MCP, confirms in one
line, and returns to the current work. **No asking "which list?"** unless two
or more branches are genuinely plausible.

Everything lives in Grove. There is no secondary capture system.

## Collision with grove

Both skills call the same MCP tools. The split is by task-shape:

- **Task user voice → here.** "add a to-do", "remind me to call X", "done with
  the dishwasher", "show my to-dos for listing-lens", "drop the gym signup".
- **Anything else → grove.** Idea capture, full-system browse, events, status
  verdict queries — see grove's collision table.

For full MCP tool reference and field schemas, see grove's SKILL.md. This skill
covers the task-side routing logic and CRUD flow only.

## Routing decision tree

Run this against every to-do. Pick the first match. The reasoning each branch
encodes is: where would Baylee look for this later? Match that list.

1. **Is this actually a new idea Baylee wants evaluated?** Not this skill —
   hand to **grove** (idea capture) or **idea-scout** (if fresh chat).
2. **Is this a feature idea for an existing project?** User names a project
   (Listing Lens, Grove, Trenchcoat, etc.) and describes a feature or
   enhancement → `list = <project-slug>`, tag `feature-idea`. Feature ideas
   are tasks, not standalone ideas — they don't need scouting because the
   project is already validated. Capture the feature description in `notes`.
3. **Tied to a specific project or repo?** `list = <project-slug>`,
   `project_ref = fairbay/<repo>`. Example: `listing-lens` + `fairbay/listing-lens`.
4. **Dev work, no specific project?** `list: dev`.
5. **Personal errand, call, appointment?** `list: personal`.
6. **Kids, school, household, partner?** `list: family`.
7. **General work or ambiguous?** `list: inbox`.

Infer from: current repo in conversation, whether Baylee is mid-task, what kind
of thing it is. Asking "where should this go?" is a derailment — only do it
when two branches are genuinely plausible *and* the wrong choice would lose
the task.

## Operations

### Add a to-do (Tier 2 — reversible)

1. Classify per the routing tree.
2. Call `grove_create_task` with `title`, `list`, `project_ref` (if applicable),
   plus `priority`, `tags`, `due_at`, `notes` as the input warrants.
3. Confirm in one line: `Added to Grove (<list>): <title>`.
4. **Return to the current task.** A to-do is a sidebar, not a topic change.

**Before creating, check for duplicates.** Run `grove_list_tasks` with a search
query matching the title. If the exact item already exists open, skip and say
so: `Already in Grove (<list>): <title>`. Duplicate tasks pollute the list and
make completion ambiguous.

**Note quality gate.** Before calling `grove_create_task`, verify the notes
pass this test: could someone execute this task with zero chat context?

- Required: why the task exists, what "done" looks like.
- Include when available: key decisions already made, links to repos/artifacts/
  Grove ideas, technical details that would take time to reconstruct.
- Red flags — expand before creating: "as discussed", "see above", "the
  approach we landed on" without spelling it out, or bare titles with no notes
  (unless truly self-explanatory like "Buy milk").

This gate applies to tasks created by any skill during any workflow — not just
user-voiced to-dos. chat-archive and grove follow the same standard.

**Batched input:** If two to-dos came in one message, create both, confirm both
on separate lines. If five+ came in, batch confirmations to one line per `list`.

### List to-dos

| User says | Call |
|---|---|
| "show my to-dos" / "what's on my list" | `grove_list_tasks` with `status: open` |
| "what's open for listing-lens" | `grove_list_tasks` with `list: listing-lens` |
| "anything tagged research" | `grove_list_tasks` with `tag: research` |
| "what's due this week" | `grove_list_tasks` with `due_at` range filter |

Surface counts first if the list is long (>10). Group by `list` for
cross-cutting views.

### Close a to-do

1. Find the task: search by title via `grove_list_tasks`, or use a known ID
   from the current session.
2. `grove_complete_task` with the task ID.
3. Confirm: `Done: <title>`.

### Drop a to-do

For items that won't happen:
1. `grove_drop_task` with the task ID.
2. Confirm: `Dropped: <title>`.

Drop ≠ delete — the audit log retains it. Use drop when the to-do is
abandoned; use complete when it actually got done.

### Auto-close proactively

**If you are about to wrap a task that matches an open Grove item without
closing it, stop.** Offer: `Looks like we just handled <title> — close it
out?` Baylee says yes, you call `grove_complete_task`.

This fires on recognizable task shapes during build, debug, or errand sessions.
The cost of asking once is low; the cost of stale tasks is high.

## Chat-archive integration

When archiving (see `chat-archive`):

1. Scan the conversation for implicit TODOs that were mentioned but never
   captured. Route each per the decision tree → Grove.
2. Surface open tasks for touched projects in the archive summary.
3. Prompt to close any tasks that appear to have been handled this session.

## Known gotchas

- **No TODOs in memory edits.** Memory is for behavioral overrides and
  reference data, not task data. Task state lives in Grove.
- **"Added to Grove" requires the MCP call to have succeeded.** Don't claim
  capture until the tool returned an ID.
- **Project tasks need both `list` and `project_ref`.** The `list` is the slug
  shown in the UI; `project_ref` is what git-ops and chat-archive cross-reference.

## Integration

- **← chat-archive:** Pulls implicit TODOs into Grove during session wrap.
- **← any build/debug session:** Auto-close offered when matched tasks land.
- **→ grove:** Shares MCP tools and field reference. Ideas, browse, and events
  live there.
