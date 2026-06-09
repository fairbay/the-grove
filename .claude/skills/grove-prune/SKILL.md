---
name: grove-prune
description: >
  Prune stale Grove tasks/ideas — "prune grove", "clean up tasks", "what's
  stale". Interactive assessment + batch action. Not for capture (→ grove,
  add-to-do) or browse (→ idea-vault).
metadata:
  version: "2026-06-09-01"
---

# grove-prune — assess and clean up stale Grove items

Sweep all open tasks and raw/scouted ideas. Classify each as done,
stale, superseded, blocked, or ready. Present a grouped assessment.
Execute batch actions after confirmation.

## When this fires

- "prune grove", "clean up tasks", "what's stale", "grove hygiene"
- Proactively suggest after 3+ months without a prune (check
  `grove_events` for last prune event).

## Interactive mode (chat / Code)

### Phase 1: Pull everything open

```
grove_list_tasks(status: "open")
grove_list_ideas(status: "raw")
grove_list_ideas(status: "scouted")
```

### Phase 2: Classify each item

For each item, classify into one of:

| Classification | Criteria | Action |
|---|---|---|
| **Done** | Work was completed (check repos, deploys, conversation context) | `grove_complete_task` |
| **Stale** | >90 days old, no activity, no blocking dependency | `grove_drop_task` or shelve idea |
| **Superseded** | Another task/idea covers this | Drop with note pointing to successor |
| **Blocked** | Waiting on external dependency, Baylee action, or prerequisite | Keep open, add `blocked:` tag |
| **Ready** | Actionable now, not stale | Keep open, optionally reprioritize |

**Classification heuristics:**
- Task >90 days with p0 priority → likely stale (urgent things that sat 3 months aren't urgent)
- Idea with `status: raw` >60 days → suggest scouting or shelving
- Task with `project_ref` pointing to an archived repo → superseded
- Task whose description matches a completed PR or deploy → done

### Phase 3: Present assessment

Group by classification. For each item show: title, age, list/status, and
your reasoning.

```
## Done (3 items)
1. **Fix Vercel deploy** (dev, 45 days) — PR #32 merged, deploy verified
2. ...

## Stale (5 items)
1. **Research OAuth providers** (dev, 120 days, p0) — no activity since March
2. ...

## Superseded (1 item)
1. **Sync skills to baylee-skills** (dev) — repo archived, ops is source now

## Blocked (2 items)
1. **App Store submission** (listing-lens) — needs Apple Developer enrollment

## Ready (4 items — no action needed)
1. **Build landing page** (grove-web, 30 days)
2. ...
```

### Phase 4: Confirm and execute

Present the batch action plan:

> **Proposed actions:**
> - Complete 3 tasks (done)
> - Drop 5 tasks (stale) + shelve 2 ideas (stale)
> - Drop 1 task (superseded)
> - Keep 2 blocked, 4 ready
>
> Proceed? (Or name specific items to keep/change.)

After confirmation, execute all actions via Grove MCP. Report results
as a summary table.

### Phase 5: Record the prune

Create a Grove event note (via `grove_create_task` with `list: meta`,
`status: done`): "Grove prune: completed N, dropped N, shelved N, kept N".
This is the timestamp for "when was the last prune."

## Routine mode (grove-prune-r)

For async execution via fire-routine. Conservative — only acts on
unambiguous cases.

**Auto-complete:** Tasks whose `project_ref` repo has a merged PR or
deploy that matches the task title/description. Verify via git-ops
before completing.

**Auto-drop:** Tasks >90 days old with p0 priority and no tags suggesting
active work (`blocked`, `waiting`, `deferred`).

**Surface for review:** Everything else that's >60 days old. Create a
single Grove task with `list: meta`, `tags: ["prune-review"]`, notes
containing the list of items needing human decision.

**Never auto-drop:** Ideas (only shelve), tasks with `blocked` or
`deferred` tags, tasks with p2-p3 priority (intentionally low-priority
items age normally).

## Integration

- **← grove:** shares MCP tools for task/idea operations.
- **← chat-archive:** session wrap may suggest a prune if stale items were
  encountered during the session.
- **→ add-to-do:** items reclassified during prune may generate new tasks.
