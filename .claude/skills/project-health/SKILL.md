---
name: project-health
description: >
  MBN health check — "status report", "scorecard", "health check",
  "how's the navigator doing". Audits DB + Grove + Vercel with real
  metrics. Not mid-session (→ chat-status) or close (→ chat-archive).
metadata:
  version: "2026-06-30-02"
---

# project-health — MBN data completeness & quality scorecard

**Version gate (chat only):** Compare `metadata.version` against
`fairbay/ops` via git-ops. If behind, warn once and continue.

Pulls live numbers from Supabase (`mqbnsjkeucvumdoqdeww`), Grove, and
Vercel to produce an actionable scorecard. Replaces vanity counts
(listing totals, row counts) with metrics tied to whether the product
strategy actually works.

## Metrics

### Data completeness — "Can we show users everything they need?"

| Metric | SQL | Thresholds |
|--------|-----|-----------|
| **Plan coverage** — % of active PIAs with ≥1 listing | `COUNT(DISTINCT pia.id) FILTER (WHERE rl_ct > 0) / COUNT(DISTINCT pia.id)` per state | Red <60%, amber <90%, green ≥90% |
| **Eligibility fill** — % of listings with populated eligibility JSONB | `FILTER (WHERE eligibility IS NOT NULL AND eligibility::text NOT IN ('null','{}','[]'))` | Red <70%, amber <90%, green ≥90% |
| **Values fill** — % of INCENTIVE/GOODS listings with dollar amounts | Join rewards on reward_class IN ('INCENTIVE','GOODS'), filter values populated | Red <30%, amber <60%, green ≥60% |
| **Source-backed** — % of listings with ≥1 extraction that has a source_id | `EXISTS (SELECT 1 FROM extractions WHERE reward_listing_id = rl.id AND source_id IS NOT NULL)` | Red <60%, amber <85%, green ≥85% |

### Data quality — "Can users trust what we're showing?"

| Metric | SQL | Thresholds |
|--------|-----|-----------|
| **Confirmed %** — listings with evidence_type = 'confirmed' (not inferred_mandatory) | Per state from reward_listings.evidence_type | Red <60%, amber <90%, green ≥90% |
| **Grounding score** — avg grounding_score on scored extractions | `AVG(grounding_score) FILTER (WHERE grounding_score IS NOT NULL)` per state | Red <0.6, amber <0.8, green ≥0.8 |
| **Extraction density** — avg extractions per listing | `COUNT(e.id) / COUNT(DISTINCT rl.id)` per state | <1.0 = thin provenance |

### Why these metrics and not others

- **Plan coverage** matters because a zero-listing plan = empty page for
  that plan's members. This is the highest-severity gap.
- **Eligibility fill** matters because the action-first UX ("how do I get
  this?") needs to tell users who qualifies. Without it, listings are
  informational noise.
- **Values fill** matters because the freebie-first content strategy
  (NC-008) makes dollar amounts the headline hook. "You're missing out on
  $X" goes dead without values. Only measured on INCENTIVE/GOODS — SERVICE
  and PROGRAM rewards don't have monetary values.
- **Source-backed** matters because unverifiable listings undermine trust.
  The product shows "source" links — if a listing has no source, the link
  is empty.
- **Confirmed %** separates plan-document-sourced data from regulatory
  inference. CA at 7.4% confirmed means almost all its data is inferred,
  not extracted.
- **Grounding score** measures extraction fidelity. 1.0 = verbatim match
  to source document. Low scores indicate the extraction drifted from what
  the source actually says.
- Listing counts, row counts, and table sizes are explicitly NOT health
  metrics. "757 listings" tells you nothing about whether those listings
  are complete, sourced, or useful.

## Queries

### Completeness query (run as one)

```sql
SELECT
  pia.state_id,
  COUNT(DISTINCT pia.id) as total_plans,
  COUNT(DISTINCT pia.id) FILTER (WHERE rl_ct.ct > 0) as plans_with_listings,
  COUNT(DISTINCT pia.id) FILTER (WHERE rl_ct.ct = 0 OR rl_ct.ct IS NULL) as zero_listing_plans,
  ROUND(100.0 * COUNT(DISTINCT pia.id) FILTER (WHERE rl_ct.ct > 0)
    / NULLIF(COUNT(DISTINCT pia.id), 0), 1) as plan_coverage_pct
FROM program_insurer_areas pia
LEFT JOIN LATERAL (
  SELECT COUNT(*) as ct FROM reward_listings WHERE program_insurer_area_id = pia.id
) rl_ct ON true
WHERE pia.status = 'active'
GROUP BY pia.state_id ORDER BY pia.state_id;
```

```sql
SELECT
  pia.state_id,
  COUNT(rl.id) as total_listings,
  ROUND(100.0 * COUNT(rl.id) FILTER (
    WHERE rl.eligibility IS NOT NULL
    AND rl.eligibility::text NOT IN ('null','{}','[]')
  ) / NULLIF(COUNT(rl.id), 0), 1) as eligibility_pct,
  COUNT(rl.id) FILTER (
    WHERE r.reward_class IN ('INCENTIVE','GOODS')
  ) as incentive_goods_ct,
  ROUND(100.0 * COUNT(rl.id) FILTER (
    WHERE r.reward_class IN ('INCENTIVE','GOODS')
    AND rl.values IS NOT NULL
    AND rl.values::text NOT IN ('null','{}','[]')
  ) / NULLIF(COUNT(rl.id) FILTER (
    WHERE r.reward_class IN ('INCENTIVE','GOODS')
  ), 0), 1) as values_pct,
  ROUND(100.0 * COUNT(DISTINCT rl.id) FILTER (WHERE EXISTS (
    SELECT 1 FROM extractions e
    WHERE e.reward_listing_id = rl.id AND e.source_id IS NOT NULL
  )) / NULLIF(COUNT(rl.id), 0), 1) as source_backed_pct
FROM reward_listings rl
JOIN program_insurer_areas pia
  ON pia.id = rl.program_insurer_area_id AND pia.status = 'active'
LEFT JOIN rewards r ON r.id = rl.reward_id
GROUP BY pia.state_id ORDER BY pia.state_id;
```

### Quality query

```sql
SELECT
  pia.state_id,
  ROUND(100.0 * COUNT(rl.id) FILTER (
    WHERE rl.evidence_type = 'confirmed'
  ) / NULLIF(COUNT(rl.id), 0), 1) as confirmed_pct,
  ROUND(COUNT(e.id)::numeric
    / NULLIF(COUNT(DISTINCT rl.id), 0), 1) as extractions_per_listing,
  ROUND(AVG(e.grounding_score) FILTER (
    WHERE e.grounding_score IS NOT NULL
  ), 2) as avg_grounding_score
FROM reward_listings rl
JOIN program_insurer_areas pia
  ON pia.id = rl.program_insurer_area_id AND pia.status = 'active'
LEFT JOIN extractions e ON e.reward_listing_id = rl.id
GROUP BY pia.state_id ORDER BY pia.state_id;
```

### Supporting queries

```sql
-- Table sizes (sanity check, not a health metric)
SELECT relname, n_live_tup FROM pg_stat_user_tables
WHERE schemaname = 'public' ORDER BY n_live_tup DESC;

-- Migration count
SELECT COUNT(*) as total, MAX(name) as latest
FROM supabase_migrations.schema_migrations;

-- Reward category distribution
SELECT rc.name, COUNT(DISTINCT r.id) as rewards,
  COUNT(DISTINCT rl.id) as listings
FROM reward_categories rc
LEFT JOIN rewards r ON r.reward_category_id = rc.id
LEFT JOIN reward_listings rl ON rl.reward_id = r.id
GROUP BY rc.name ORDER BY COUNT(DISTINCT rl.id) DESC;

-- Source type breakdown
SELECT source_type, COUNT(*) FROM sources GROUP BY source_type ORDER BY COUNT(*) DESC;

-- PIA status breakdown
SELECT status, COUNT(*) FROM program_insurer_areas GROUP BY status;

-- Enrollment coverage
SELECT
  COUNT(*) FILTER (WHERE enrollment_count > 0) as populated,
  COUNT(*) FILTER (WHERE enrollment_count = 0 OR enrollment_count IS NULL) as zero
FROM program_insurer_areas WHERE status = 'active';
```

## Report structure

Use visualizer for all sections. Interleave prose between visuals.

1. **Key metrics dashboard** — metric cards: listings, catalog size, active
   plans, extractions, sources, migrations, states covered. Quick sanity
   check, not the health measure.

2. **Completeness scorecard** — interactive table, one row per state, columns
   for each completeness + quality metric. Sortable by any column. Filterable:
   "all states", "gaps only" (any metric below amber threshold), "strongest"
   (all metrics green). Bar charts in each cell with color thresholds.

3. **Critical findings** — prose analysis of what the scorecard reveals.
   Ordered by user impact, not by which number is lowest. Each finding:
   the metric, why it matters for the product strategy, specific scope.

4. **Prioritized action list** — stack-ranked. Each item specific enough to
   become a Grove task. Create the tasks in Grove with the
   `health-check-YYYY-MM-DD` tag.

## Grove integration

- Query `grove_list_tasks` for open MBN tasks.
- Query `grove_list_decisions` for recent architectural decisions.
- Check Vercel `list_deployments` for deploy health.
- After analysis, create Grove tasks for each action item with:
  - Before/after metrics
  - Done definition
  - Approach section
  - `health-check-YYYY-MM-DD` tag
- Log a decision capturing the metrics framework findings.

## Comparison to previous health checks

If previous health-check tasks exist (search by tag), compare current
metrics to the targets set in those tasks. Show what improved and what
didn't.

## Integration

- **← session-start:** Can run at session start for orientation.
- **→ add-to-do / grove:** Findings produce Grove tasks.
- **→ chat-archive:** If running at end of session, hand off.
