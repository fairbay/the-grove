---
metadata:
  version: "2026-07-12-01"
  description: >-
    Strategic task triage — "bloom", "what should I work on", "plan the work".
    Cross-project mission-weighted grouping into work packages. Not capture
    (→ add-to-do) or onboarding (→ session-start).
---

# bloom — mission-weighted task triage and work planning

Gather all open work across projects, independently derive priority from
mission alignment and structural analysis, group into executable work
packages, and produce a plan that reflects what WILL be done — not what the
system's priority field says.

**Core principle:** System-assigned priority is a proxy variable — noisy,
biased toward recency and squeaky-wheel effects. Bloom treats it as one
signal among many, never as ground truth. Priority is derived from the
analysis, not inherited from the metadata.

## Trigger shapes

Fires for:
- "bloom", "run bloom", "/bloom"
- "what should I work on", "what's next across projects"
- "plan the work", "triage everything", "prioritize the backlog"
- "what's the highest-impact work right now"

Does NOT fire for:
- "add a task", "remind me to" → add-to-do (capture, not analysis)
- "work on [project]", "continue [project]" → session-start (onboarding)
- "status report", "scorecard" → project-health (metrics, not planning)
- "what did I do last session" → session-start or chat-status (retrospective)
- Mid-session "what's next on THIS project" → session-start Phase 4c queue

## Phase 1 — Gather (go wide)

Pull all open work items. Cast the net broadly — filtering happens in Phase 2.

**Sources (query all, merge, deduplicate):**

1. **Grove tasks** — `grove_list_tasks(status="open", limit=50)` across all
   projects. These are the canonical work items.
2. **Grove adjudications** — `grove_list_adjudications(status="open")`.
   Pending judgments are blockers, not tasks — note them but don't rank them.
3. **HANDOFF.yaml `next:`** — from each active repo. May contain items not
   yet in Grove.
4. **Grove project `next_actions`** — from each active project row. May
   diverge from handoffs if a session updated one but not the other.
5. **PLAN.md active phase** — remaining steps in any project's current plan
   phase.

**Cross-reference:** Items appearing in multiple sources get merged (same
work, different records). Note which sources agree — convergence is a
signal of real priority.

**Capture metadata per item:** title, project, source(s), system priority (if
any), creation date, last touched, any dependency references, blocking
status, Grove task ID.

## Phase 2 — Filter (reduce noise)

Remove items that should not be ranked. Do not delete them — tag and park.

**Filter criteria:**

- **Already done.** Cross-check against recent git history, merged PRs, and
  Grove completed tasks. Stale handoff items are the most common source.
- **Superseded.** A newer decision, schema change, or merged PR has made the
  item irrelevant. Check `grove_list_decisions` for decisions that overtake
  the task's premise.
- **Time-gated.** Items with external triggers that haven't fired (quarterly
  scans with future dates, monitoring tasks waiting on external events).
  Park with the trigger date.
- **Blocked on Baylee.** Open adjudications, items requiring physical-world
  action. Park with blocker reference.
- **Duplicate.** Same work described differently across sources. Keep the
  most specific version.

**Output:** Active items (proceed to Phase 3) + parked items (with reason).

## Phase 3 — Analyze (mission-weight)

Score each active item on four dimensions. Do not use a single composite
score — present the dimensions so the shape of each item's value is visible.

### Dimension 1: Mission impact

How directly does completing this item advance the project's stated mission?
Read the project's MISSION.md (or CLAUDE.md mission summary) and score
against it.

**Impact tiers (ordered):**

1. **Active harm removal** — members/users currently receiving wrong
   information, broken functionality, data serving errors. Fix stops ongoing
   damage.
2. **Core capability** — directly builds or improves the product's primary
   value proposition. For MBN: accuracy/completeness of reward data.
3. **Enabler** — unblocks or accelerates core capability work. Tooling,
   infrastructure, methodology improvements.
4. **Additive** — extends coverage, polish, or reach beyond current core.
   Nice to have but not blocking the mission.
5. **Deferred** — valuable but time-gated, speculative, or dependent on
   unmet prerequisites.

### Dimension 2: Dependency structure

Map what blocks what. Items that unblock multiple downstream tasks rank
higher than leaf tasks. Items blocked by unfinished prerequisites rank lower
(they can't start yet anyway).

### Dimension 3: Effort/impact ratio

Estimate effort in session-hours (rough: small <1h, medium 1-4h, large 4h+).
A 30-minute fix that removes active harm outranks a 4-hour enabler. But
don't let this dimension dominate — a large core-capability item still
outranks a small additive one.

### Dimension 4: Risk of inaction

What happens if this item waits another 2 weeks? Another month?

- **Compounding** — gets worse over time (data drift, accumulating errors,
  blocking more work as backlog grows)
- **Static** — same cost whether done now or later
- **Decaying** — becomes less relevant over time (may self-resolve)

## Phase 4 — Group (find natural clusters)

Group items into work packages based on patterns that emerge from the
analysis. Do not force items into predetermined categories.

**Clustering signals (check for each):**

- **Shared methodology** — items that use the same tools, pipeline, or
  approach and benefit from a single session's warm context
- **Shared data scope** — items touching the same state, plan, table, or
  schema region
- **Verification chain** — items whose outputs verify each other or share a
  validation step
- **Sequential dependency** — items where A must complete before B
- **Complementary scope** — items that are individually small but collectively
  address one theme (e.g., "repo health" quick fixes)

**Group sizing:** Target 1-4 hour work packages. A group too large to finish
in one session should be split. A group too small to justify context setup
should be merged with a neighbor.

**Cross-project groups are valid.** If an ops task and an MBN task share
methodology or unlock each other, group them together.

## Phase 5 — Plan (output)

Present the work plan. This is the deliverable.

**Format:**

```
## Bloom — [date]

### Active items: [N] | Parked: [M] | Projects: [list]

### Group 1: [label] — [impact tier] — ~[effort estimate]
[Why this group, why this position in the sequence]

○ Item A [project] [Grove: task_id]
○ Item B [project] [Grove: task_id]

### Group 2: [label] — [impact tier] — ~[effort estimate]
...

### Parked
- [item] — [reason: time-gated/blocked/superseded] [trigger date if any]

### Assumptions
[Any judgment calls made during analysis — flagged for override]
```

**Ordering:** Groups ordered by the highest-impact item in each group, with
dependency constraints overriding pure impact ranking (a group that unblocks
another goes first even if its own impact is lower).

## Autonomy calibration

**Tier 2 — produce plan, state assumptions, proceed unless redirected.**

Bloom produces the plan and presents it. It does not ask "which group do you
want to work on?" — the ordering IS the recommendation. The user can
redirect, reorder, or override, but the default is: start with Group 1.

If bloom is invoked at session start alongside session-start, the bloom
output replaces session-start's Phase 4c work queue. Session-start still
runs Phases 1-4b (project resolution, handoff, staleness, Grove memory);
bloom provides the prioritized queue.

## Background mode

Bloom can run as a background agent (Phases 1-4 delegated, Phase 5
surfaced when ready). When invoked with "bloom in background" or by a
routine, spawn an agent for the gather-filter-analyze-group pipeline and
surface the plan summary when complete.

**Routine integration:** A bloom routine (`bloom-r`) can run on schedule,
pushing the resulting plan to Grove project notes or a handoff. The
executing session picks up the pre-computed plan via session-start instead
of re-deriving it.

## Integration

- **← session-start:** Bloom can consume session-start's loaded context
  (handoff, Grove state, PLAN.md) to avoid re-fetching.
- **← grove:** Primary data source for tasks, decisions, project state.
- **→ session-start Phase 4c:** Bloom's output can replace the synthesized
  work queue when both skills run in the same session.
- **→ build / systematic-debug / etc.:** The first group in bloom's plan
  feeds directly into the executing skill.
- **→ chat-archive:** Bloom's assumptions and grouping rationale are
  decision-grade — log to Grove via `grove_log_decision` if they represent
  a prioritization call.

## Anti-patterns

- **Inheriting system priority as ground truth.** The whole point of bloom
  is independent analysis. P1 is a data point, not a verdict.
- **Asking the user to pick from a menu.** Bloom recommends; the user
  redirects. Don't present an unordered list and ask "which one?"
- **Treating all same-priority items as equal.** 10 P1 tasks are not
  equally important. That's what the four-dimension analysis resolves.
- **Forcing groupings.** If items don't cluster naturally, they're
  standalone. A group of one is fine.
- **Ignoring quick wins.** A 20-minute enabler that unblocks 3 other items
  should surface early, not get buried because it's "small."
- **Planning without a time horizon.** Always state the planning window
  (this session, this week, this sprint). Unbounded plans are wish lists.
- **Re-running full gather when a recent bloom exists.** If a bloom plan
  was produced <24h ago, update it incrementally — don't re-query everything.
