---
name: grove
description: >
  Grove ops — "save this idea", "what's in grove", "log this decision",
  "what did we decide", "project status", recent activity. Not for to-dos
  (→ add-to-do) or scoring (→ idea-scout, idea-vault).
metadata:
  version: "2026-06-10-01"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# grove — Grove backend reference and idea-side capture

Grove is Baylee's memory store (Supabase + Vercel API at
`vault.bayleemiller.org`). Everything that needs to be remembered lives here:
dev tasks, errands, family items, raw ideas, scout verdicts, durable
decisions, and project state for code AND non-code projects. No secondary
capture system exists. Code lives in git; memory lives in Grove.

This skill owns: idea capture, decision logging/recall, project-state
browse, full-system browse, event/history queries, and the MCP/field
reference used by every Grove-touching skill. Task user-voice ("add to do",
"remind me to") routes through **add-to-do**, which calls the same MCP tools
but with task-specific routing logic.

## Collision zone with add-to-do

| User says | This skill | add-to-do |
|---|---|---|
| "save this idea" / "grove this idea" | yes (idea capture) | no |
| "grove this" (pointing at a task) | hand to add-to-do | yes |
| "what's in grove" / "show my grove" | yes (cross-cutting) | no |
| "recent activity" / "what happened recently" | yes (events) | no |
| "show my ideas" / "what got greenlit" | yes | no |
| "add a to-do" / "remind me to X" | no | yes |
| "show my to-dos for X" | no | yes |
| "done with X" / "drop X" | no | yes |

Rule of thumb: **ideas, events, and cross-cutting browse → grove. Task-shaped
user voice → add-to-do.** Both call the same MCP tools.

## MCP tools

Grove MCP is at `vault.bayleemiller.org/api/mcp` as a custom Claude connector.
When active, 13 tools are available natively — no code execution needed.

| Tool | Use when |
|---|---|
| `grove_create_task` | Any to-do, reminder, action item, errand |
| `grove_create_idea` | New concept, project idea, "what if" |
| `grove_list_tasks` | "Show my tasks", "what's open for X" |
| `grove_list_ideas` | "Show my ideas", "raw ideas", "what got greenlit" |
| `grove_log_decision` | Rung-3 call made, "log this decision"; `supersedes` to correct |
| `grove_list_decisions` | "What did we decide about X", session-start Rung-1 read |
| `grove_create_project` | New project (code or non-code; omit `repo` for non-code) |
| `grove_list_projects` | "Project status", briefing reads, slug lookup |
| `grove_get` | Fetch a single item by ID (task, idea, project, decision) |
| `grove_update` | Change fields on a task, idea, or project (NOT decisions) |
| `grove_complete_task` | "Done with X", mark complete |
| `grove_drop_task` | "Drop X", "never mind about X" |
| `grove_events` | "What happened recently", audit history, Session Chronicle |

MCP is the only interface. The Python script (`scripts/grove.py`) is the fallback
for Routines that lack MCP access — same operations, same auth flow.

## Idea capture

When the user has a new concept, project idea, or "what if" worth keeping:

1. **Create as `status: raw`** via `grove_create_idea`. Title is required;
   notes carry the framing. Tags optional.
2. **Decide whether to chain to scoring.** Three cases:
   - Fresh chat, no active task → auto-invoke `idea-scout`.
   - Mid-task, idea would derail → save as raw, return to task.
   - Explicit "save this" / "park this" → save raw, no scout.
3. Confirm in one line: `Saved idea: <title>`.

**Note quality gate (ideas and tasks).** Before calling `grove_create_idea` or
`grove_create_task`, verify the notes pass this test: could someone act on this
item with zero chat context?

- Required: why it exists, what "done" (or "scouted" / "shipped") looks like.
- Include when available: key decisions already made, links to repos/artifacts,
  technical details that would take time to reconstruct.
- Red flags — expand before creating: "as discussed", "see above", bare titles
  with no notes (unless truly self-explanatory).

Same standard applies in add-to-do and chat-archive.

Status progression (set by other skills, documented here for reference):
`raw → scouted → in_dev → shipped` (or `shelved` / `gifted` / `killed`).

## Decisions and project state

### "Log this decision" / Rung-3 calls

`grove_log_decision` with: `decision` (the call), `project_ref`
(`fairbay/<repo>`, a project slug, or `cross-project`), `alternatives`,
`confidence`, `reversible`, `context`, `rung` (usually 3). Decisions are
**append-only** — to correct one, log a new decision with `supersedes` set to
the old ID. Never try `grove_update` on a decision.

### "What did we decide about X"

`grove_list_decisions(project_ref=..., current_only=true)`. Default excludes
superseded decisions; pass `current_only=false` for full history. This is
the Rung-1 read at session start (see session-start skill).

### "Project status" / project rows

`grove_list_projects` (slug for exact lookup, `q` for search). Project rows
carry `phase`, `blockers`, `next_actions`, `last_session`, `docs` status, and
`notes` (the planning-doc body for non-code projects). Create with
`grove_create_project` — omit `repo` for non-code projects; update with
`grove_update(entity_type="project", ...)`. chat-archive refreshes the row at
session end; session-start's briefing reads it.

## Browse and events

### "What's in grove" / "show my grove"

Cross-cutting browse covers both tasks and ideas. Default: open tasks across
all lists + raw/scouted ideas. Surface counts first, drill into items on
request.

### "Recent activity" / "what happened recently"

Call `grove_events`. Default window: last 7 days. Group by entity type, show
the most recent first. Useful for chat-status checkpoints and weekly review.

### "Show my ideas" / verdict filtering

`grove_list_ideas` with status or verdict filter. Common asks:
- "what got greenlit" → `verdict: greenlight`
- "raw ideas" → `status: raw`
- "what shipped" → `status: shipped`

## Field reference

### Task fields
- `title` — required, 1–500 chars
- `list` — see add-to-do for routing logic
- `status` — `open` / `done` / `dropped` (default: `open`)
- `priority` — 0 (none) … 3 (urgent)
- `due_at` — ISO 8601, e.g. `"2026-05-01T14:00:00-04:00"`
- `tags` — list of strings
- `project_ref` — `fairbay/<repo>` when tied to a repo
- `notes` — free text
- `source` — auto-set by MCP

### Idea fields
- `title` — required
- `status` — `raw` / `scouted` / `in_dev` / `shipped` / `shelved` / `gifted` / `killed`
- `verdict` — `greenlight` / `overreach` / `public_good` / `mirage` /
  `workhorse` / `fools_gold` / `lark` / `pass` (set by idea-scout)
- `scores` — jsonb dict: `{"impact_pct": N, "business_pct": N, "sustainability_pct": N}`
- `tags`, `notes`, `metadata` — optional

### Decision fields
- `decision` — required, 1–2000 chars (the call that was made)
- `project_ref` — `fairbay/<repo>`, a project slug, or `cross-project`
- `alternatives` — what was considered and rejected
- `confidence` — `high` / `medium` / `low` (default `medium`)
- `reversible` — `yes` / `no` / `partial` (default `yes`)
- `context` — one sentence on why it mattered
- `rung` — Decision Ladder rung 1–4 (usually 3)
- `superseded_by` — set via `supersedes` on a newer decision; append-only

### Project fields
- `name` — required; `slug` — required, unique kebab-case
- `repo` — `fairbay/<repo>` for code projects; **null = non-code project**
- `phase` — `planning` / `building` / `testing` / `shipping` / `maintaining` / `parked`
- `docs` — jsonb `{mission, spec, plan, brief}` booleans
- `blockers`, `next_actions` — text arrays
- `last_session` — date; `notes` — planning-doc body for non-code projects

## MCP failure handling

If any Grove MCP call fails (timeout, connection error, server error):

1. **Report the error explicitly.** Include the tool name and error message.
2. **Retry once** with a fresh call.
3. **If still failing,** surface the data that would have been written in the
   response body so it's not lost. For ideas: title, notes, tags. For tasks:
   title, list, notes, priority.
4. **Never skip silently.** "Added to Grove" requires the MCP call to have
   succeeded and returned an ID.

## Update and delete

`grove_update` patches any field on tasks, ideas, and projects. Use
sparingly — most mutations are status transitions (raw → scouted, open →
done) handled by purpose-specific tools (`grove_complete_task`,
`grove_drop_task`, scout writing a verdict). Decisions cannot be updated —
append-only; supersede instead.

There is no delete. Drop a task with `grove_drop_task`; shelve an idea by
setting `status: shelved`. The audit log retains everything.

## Web UI

`vault.bayleemiller.org` — Tasks, Ideas, Settings tabs. Surface this link when
Baylee asks "where can I see all this" or needs to interact outside chat.

## Deprecated capture paths

These are no longer used anywhere. If found in old plans or memory edits,
migrate to Grove:

- iOS Reminders (all lists)
- `<project>/TODO.md`
- `idea-vault/ideas.json` (migrated to Supabase 2026-05-05)
- `idea-vault/breadcrumbs.md`

## Integration

- **← idea-scout:** Writes verdicts and scores onto ideas via `grove_update`.
- **← add-to-do:** Task-shaped capture flows through the same MCP tools.
- **← chat-archive:** Pulls open tasks for touched projects during session
  wrap; writes the project row + Rung-3 decisions (Step 9b).
- **→ session-start:** Project rows + decisions are the briefing's data source.
- **→ idea-vault:** Reads idea state from Grove for browsing and comparison.
- **→ idea-scout:** Newly raw ideas chain to scoring in a fresh chat.
