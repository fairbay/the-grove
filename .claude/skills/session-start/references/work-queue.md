# Work queue: ordering and rendering (Phase 4c)

Moved out of SKILL.md (2026-11-05, ops 85a02946: the body was over the 500-line limit).
Phase 4c gathers and verifies the items; this file orders and renders them.

**Ordering principle — topological batches:**

Sort items into sequential batches. Items within a batch have no dependencies
on each other and can run in parallel. Batches are sequential gates — batch N+1
waits for batch N.

Classification tiers (batch assignment):

1. **Blockers & correctness** — broken tools, bugs, anything producing wrong
   output. Gates all downstream work.
2. **Tooling & infrastructure** — pipeline improvements, flags, automation.
   Group related changes together. These compound: every future run benefits.
3. **Data enrichment & cleanup** — work that uses the tooling. Do after tooling
   is solid. Independent enrichment tasks are parallel within this batch.
4. **External data integration** — independent enrichment from outside sources.
   Can float earlier if truly independent.
5. **Downstream consumers** — prototype updates, UI changes, exports. Depend on
   data being right — do last.

**Rendering format (topological batch list):**

```
Next up (critical-path-ordered):

Batch 1 ‖ [cluster label]
  ○ Item A
  ○ Item B

Batch 2 — [cluster label]
  ○ Item C [needs A]

Batch 3 ‖ [cluster label]
  ○ Item D
  ○ Item E
```

`‖` after batch number = items within are parallel-safe. `—` = single item or
sequential sub-items. Status: `○` pending, `◉` active, `●` done. Batch labels
describe the cluster purpose (e.g., "Pipeline correctness", "Data quality").

Within each batch, group related items. If an item could float to an earlier
batch (no dependencies on prior batches), move it — don't penalize independent
work with artificial sequencing.
