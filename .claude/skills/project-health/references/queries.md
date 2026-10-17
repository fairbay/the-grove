# project-health queries

All read-only. Run with Supabase `execute_sql` on project `mqbnsjkeucvumdoqdeww` (the connector is
for reads only; MBN docs/rules/DATA-WORK.md). Run each fenced block as its own call: `execute_sql`
returns only the last statement of a block. Keep semicolons out of string literals: the connector's
guard reads one as the end of a statement and the call comes back `cancelled`.

**Shown** means a plan row whose `program_insurer_areas.status` is not `exited` or `out_of_scope`:
the export's own filter (`scripts/generate-state-exports.mjs`), so these counts are what the site
serves. Q10 flags rows in any status other than active, exited and out_of_scope.

Contents: Q1 guards · Q2 per state · Q3 handbook · Q4 provenance · Q5 freshness · Q6 reward units ·
Q7 pipeline · Q8 structure · Q9 sizes · Q10 plan-row statuses

## Q1 — Regression guards

Exception counts, not only percentages: at a few thousand listings a one-decimal percentage reads
100.0 with listings still failing. Confirmed % counts distinct listings.

```sql
WITH ap AS (
  SELECT pia.id, pia.state_id, p.is_member_facing
  FROM program_insurer_areas pia JOIN programs p ON p.id = pia.program_id
  WHERE pia.status NOT IN ('exited','out_of_scope')
), rl AS (
  SELECT rl.id, rl.eligibility, rl."values", rl.evidence_type, r.reward_class, ap.state_id
  FROM reward_listings rl JOIN ap ON ap.id = rl.program_insurer_area_id
  LEFT JOIN rewards r ON r.id = rl.reward_id
), dens AS (
  SELECT rl.state_id, COUNT(e.id)::numeric / NULLIF(COUNT(DISTINCT rl.id), 0) AS d
  FROM rl LEFT JOIN extractions e ON e.reward_listing_id = rl.id GROUP BY rl.state_id
)
SELECT
  (SELECT COUNT(*) FROM ap WHERE is_member_facing
     AND NOT EXISTS (SELECT 1 FROM reward_listings x WHERE x.program_insurer_area_id = ap.id))       AS plans_without_listings,
  COUNT(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM extractions e
     WHERE e.reward_listing_id = rl.id AND e.source_id IS NOT NULL))                                  AS listings_without_source,
  ROUND(100.0 * COUNT(*) FILTER (WHERE eligibility IS NOT NULL AND eligibility::text NOT IN ('null','{}','[]')) / COUNT(*), 2) AS eligibility_pct,
  ROUND(100.0 * COUNT(*) FILTER (WHERE reward_class IN ('INCENTIVE','GOODS') AND "values" IS NOT NULL AND "values"::text NOT IN ('null','{}','[]'))
    / NULLIF(COUNT(*) FILTER (WHERE reward_class IN ('INCENTIVE','GOODS')), 0), 2)                    AS values_pct,
  ROUND(100.0 * COUNT(*) FILTER (WHERE evidence_type = 'confirmed') / COUNT(*), 2)                     AS confirmed_pct,
  (SELECT ROUND(AVG(e.grounding_score), 3) FROM extractions e JOIN rl x ON x.id = e.reward_listing_id
     WHERE e.grounding_score IS NOT NULL)                                                              AS grounding_avg,
  (SELECT ROUND(MIN(d), 2) FROM dens)                                                                    AS min_state_density,
  (SELECT string_agg(state_id, ',') FROM dens WHERE d < 1)                                               AS thin_states,
  COUNT(*)                                                                                               AS shown_listings
FROM rl;
```

Named exceptions, when a count above is not zero:

```sql
SELECT pia.state_id, i.brand AS insurer, p.name AS program, pia.area_label, pia.id
FROM program_insurer_areas pia
JOIN programs p ON p.id = pia.program_id AND p.is_member_facing
JOIN insurers i ON i.id = pia.insurer_id
WHERE pia.status NOT IN ('exited','out_of_scope')
  AND NOT EXISTS (SELECT 1 FROM reward_listings x WHERE x.program_insurer_area_id = pia.id)
ORDER BY 1;
```

## Q2 — Per state (the watch list's source)

Handbook is NULL (n/a) for an FFS or PCCM state with no plan handbook: its member-facing rows are the
state program, sourced from state documents (decision 34950652). `plan_year_note_pct` is the share
of reward cards (one reward on one plan) whose newest source document is from an earlier year than
now; the reward page shows "From the 20xx plan documents; 20yy may differ." for them (FR-036; the
app's `staleFor` in `app/design/flows.dc.html` takes the newest document year across a card's
listings and ignores sources with no `document_date`).

```sql
WITH mf AS (
  SELECT pia.id, pia.state_id FROM program_insurer_areas pia
  JOIN programs p ON p.id = pia.program_id AND p.is_member_facing
  WHERE pia.status NOT IN ('exited','out_of_scope')
), hb AS (
  SELECT mf.state_id, COUNT(*) plans,
    COUNT(*) FILTER (WHERE EXISTS (SELECT 1 FROM reward_listings x JOIN extractions e ON e.reward_listing_id = x.id
      JOIN sources s ON s.id = e.source_id WHERE x.program_insurer_area_id = mf.id AND s.source_type = 'plan_document')) with_hb
  FROM mf GROUP BY mf.state_id
), rl AS (
  SELECT rl.id, rl.eligibility, rl."values", rl.evidence_type, rl.reward_id, rl.program_insurer_area_id, r.reward_class, pia.state_id
  FROM reward_listings rl
  JOIN program_insurer_areas pia ON pia.id = rl.program_insurer_area_id AND pia.status NOT IN ('exited','out_of_scope')
  LEFT JOIN rewards r ON r.id = rl.reward_id
), card AS (
  SELECT rl.state_id, rl.program_insurer_area_id, rl.reward_id, MAX(EXTRACT(year FROM s.document_date)) y
  FROM rl LEFT JOIN extractions e ON e.reward_listing_id = rl.id LEFT JOIN sources s ON s.id = e.source_id
  GROUP BY 1, 2, 3
), cy AS (
  SELECT state_id, ROUND(100.0 * COUNT(*) FILTER (WHERE y < EXTRACT(year FROM now())) / COUNT(*), 1) plan_year_note_pct
  FROM card GROUP BY state_id
), st AS (
  SELECT state_id, COUNT(*) listings,
    ROUND(100.0 * COUNT(*) FILTER (WHERE eligibility IS NOT NULL AND eligibility::text NOT IN ('null','{}','[]')) / COUNT(*), 1) elig,
    ROUND(100.0 * COUNT(*) FILTER (WHERE reward_class IN ('INCENTIVE','GOODS') AND "values" IS NOT NULL AND "values"::text NOT IN ('null','{}','[]'))
      / NULLIF(COUNT(*) FILTER (WHERE reward_class IN ('INCENTIVE','GOODS')), 0), 1) vals,
    COUNT(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM extractions e WHERE e.reward_listing_id = rl.id AND e.source_id IS NOT NULL)) unsourced,
    ROUND(100.0 * COUNT(*) FILTER (WHERE evidence_type = 'confirmed') / COUNT(*), 1) confirmed
  FROM rl GROUP BY state_id
)
SELECT s.id state, s.managed_care_type mct, s.is_regionalized reg, s.region_model_status region,
  hb.plans mf_plans, st.listings,
  CASE WHEN s.managed_care_type IN ('FFS','PCCM') AND hb.with_hb = 0 THEN NULL
       ELSE ROUND(100.0 * hb.with_hb / NULLIF(hb.plans, 0), 1) END handbook,
  st.elig, st.vals, st.unsourced, st.confirmed, cy.plan_year_note_pct
FROM states s LEFT JOIN hb ON hb.state_id = s.id LEFT JOIN st ON st.state_id = s.id LEFT JOIN cy ON cy.state_id = s.id
ORDER BY cy.plan_year_note_pct DESC NULLS LAST;
```

## Q3 — Handbook

The total, n/a rows left out of both sides:

```sql
WITH mf AS (
  SELECT pia.id, pia.state_id, s.managed_care_type,
    EXISTS (SELECT 1 FROM reward_listings x JOIN extractions e ON e.reward_listing_id = x.id
      JOIN sources so ON so.id = e.source_id
      WHERE x.program_insurer_area_id = pia.id AND so.source_type = 'plan_document') AS has_hb
  FROM program_insurer_areas pia
  JOIN programs p ON p.id = pia.program_id AND p.is_member_facing
  JOIN states s ON s.id = pia.state_id
  WHERE pia.status NOT IN ('exited','out_of_scope')
), na AS (
  SELECT state_id FROM mf WHERE managed_care_type IN ('FFS','PCCM') GROUP BY state_id HAVING NOT bool_or(has_hb)
)
SELECT COUNT(*) FILTER (WHERE has_hb) AS with_handbook, COUNT(*) AS plans,
  ROUND(100.0 * COUNT(*) FILTER (WHERE has_hb) / NULLIF(COUNT(*), 0), 1) AS handbook_pct,
  (SELECT string_agg(state_id, ',') FROM na) AS na_states
FROM mf WHERE state_id NOT IN (SELECT state_id FROM na);
```

The gap plans by name (n/a states left out):

```sql
SELECT pia.state_id, i.brand AS insurer, p.name AS program, pia.area_label, pia.id
FROM program_insurer_areas pia
JOIN programs p ON p.id = pia.program_id AND p.is_member_facing
JOIN insurers i ON i.id = pia.insurer_id
JOIN states s ON s.id = pia.state_id
WHERE pia.status NOT IN ('exited','out_of_scope')
  AND NOT EXISTS (SELECT 1 FROM extractions e JOIN sources so ON so.id = e.source_id
    JOIN reward_listings x ON x.id = e.reward_listing_id
    WHERE x.program_insurer_area_id = pia.id AND so.source_type = 'plan_document')
  AND NOT (s.managed_care_type IN ('FFS','PCCM') AND NOT EXISTS (
    SELECT 1 FROM program_insurer_areas p2 JOIN reward_listings x2 ON x2.program_insurer_area_id = p2.id
    JOIN extractions e2 ON e2.reward_listing_id = x2.id JOIN sources s2 ON s2.id = e2.source_id
    WHERE p2.state_id = s.id AND s2.source_type = 'plan_document'))
ORDER BY 1;
```

## Q4 — Provenance (source_appearances of sources behind shown listings)

Measured over the sources members can reach. Runs before 2026-10-17 measured over every row in
`sources`; say so when comparing with them.

```sql
WITH live_src AS (
  SELECT DISTINCT e.source_id AS id FROM extractions e
  JOIN reward_listings rl ON rl.id = e.reward_listing_id
  JOIN program_insurer_areas pia ON pia.id = rl.program_insurer_area_id AND pia.status NOT IN ('exited','out_of_scope')
  WHERE e.source_id IS NOT NULL
), sa AS (
  SELECT a.* FROM source_appearances a JOIN live_src l ON l.id = a.source_id
)
SELECT (SELECT COUNT(*) FROM live_src) AS live_sources,
  ROUND(100.0 * (SELECT COUNT(DISTINCT source_id) FROM sa) / NULLIF((SELECT COUNT(*) FROM live_src), 0), 1) AS appearance_coverage_pct,
  (SELECT COUNT(*) FROM sa) AS appearances,
  ROUND(100.0 * (SELECT COUNT(*) FROM sa WHERE snapshot_url IS NOT NULL) / NULLIF((SELECT COUNT(*) FROM sa), 0), 1) AS snapshot_pct,
  ROUND(100.0 * (SELECT COUNT(*) FROM sa WHERE link_label IS NOT NULL) / NULLIF((SELECT COUNT(*) FROM sa), 0), 1) AS link_label_pct;
```

Where a gap comes from, all appearance rows by week created:

```sql
SELECT date_trunc('week', created_at)::date AS wk, COUNT(*) AS appearances,
  COUNT(*) FILTER (WHERE snapshot_url IS NOT NULL) AS with_snapshot,
  COUNT(*) FILTER (WHERE snapshot_pending) AS pending
FROM source_appearances GROUP BY 1 ORDER BY 1;
```

## Q5 — Freshness

```sql
WITH rl AS (
  SELECT rl.id, rl.program_insurer_area_id, rl.reward_id FROM reward_listings rl
  JOIN program_insurer_areas pia ON pia.id = rl.program_insurer_area_id AND pia.status NOT IN ('exited','out_of_scope')
), card AS (
  SELECT rl.program_insurer_area_id, rl.reward_id, MAX(EXTRACT(year FROM s.document_date)) y
  FROM rl LEFT JOIN extractions e ON e.reward_listing_id = rl.id LEFT JOIN sources s ON s.id = e.source_id
  GROUP BY 1, 2
), live_src AS (
  SELECT DISTINCT e.source_id FROM extractions e JOIN rl ON rl.id = e.reward_listing_id WHERE e.source_id IS NOT NULL
)
SELECT
  (SELECT COUNT(*) FROM card) AS cards,
  (SELECT COUNT(*) FILTER (WHERE y < EXTRACT(year FROM now())) FROM card) AS plan_year_note_cards,
  (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE y < EXTRACT(year FROM now())) / COUNT(*), 1) FROM card) AS plan_year_note_pct,
  (SELECT COUNT(*) FROM live_src) AS live_sources,
  (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE s.last_checked >= now() - interval '120 days') / COUNT(*), 1)
     FROM live_src JOIN sources s ON s.id = live_src.source_id) AS checked_120d_pct,
  (SELECT COUNT(*) FILTER (WHERE s.last_checked IS NULL) FROM live_src JOIN sources s ON s.id = live_src.source_id) AS never_checked,
  (SELECT MIN(s.last_checked)::date FROM live_src JOIN sources s ON s.id = live_src.source_id) AS oldest_check;
```

## Q6 — Reward units

```sql
WITH rl AS (
  SELECT rl.id FROM reward_listings rl JOIN program_insurer_areas p ON p.id = rl.program_insurer_area_id
  WHERE p.status NOT IN ('exited','out_of_scope')
)
SELECT
  (SELECT COUNT(*) FROM rl) AS shown_listings,
  (SELECT COUNT(*) FROM rl WHERE EXISTS (SELECT 1 FROM reward_units u WHERE u.reward_listing_id = rl.id)) AS with_units,
  (SELECT COUNT(*) FROM rl WHERE (SELECT COUNT(*) FROM reward_units u
     WHERE u.reward_listing_id = rl.id AND u.duplicate_of_unit_id IS NULL) > 1) AS multi_unit_listings,
  (SELECT COUNT(*) FROM reward_units u JOIN rl ON rl.id = u.reward_listing_id WHERE u.amount_unit = 'POINT') AS point_units,
  (SELECT COUNT(*) FROM reward_unit_reviews WHERE resolved_at IS NULL) AS open_unit_reviews;
```

## Q7 — Pipeline

```sql
SELECT
  (SELECT COUNT(*) FROM public.publish_holds) AS holds,
  (SELECT MIN(since) FROM public.publish_holds) AS oldest_hold,
  (SELECT string_agg(batch_id || ' (' || COALESCE(reason, '') || ')', ', ') FROM public.publish_holds) AS hold_detail,
  (SELECT COUNT(*) FROM ops.change_batches WHERE status = 'applied' AND published_at IS NULL) AS applied_unpublished,
  (SELECT MIN(applied_at) FROM ops.change_batches WHERE status = 'applied' AND published_at IS NULL) AS oldest_unpublished,
  (SELECT MAX(applied_at) FROM ops.change_batches) AS last_applied,
  (SELECT MAX(published_at) FROM ops.change_batches) AS last_published,
  (SELECT COUNT(*) FROM feedback WHERE status = 'new'
     AND COALESCE(issue_type, '') <> 'smoke_test' AND COALESCE(page_path, '') <> '/__smoke') AS feedback_untriaged;
```

## Q8 — Structure

`enroll_null` counts member-facing rows outside FFS/PCCM states only: CMS publishes no plan
enrollment for those states.

```sql
WITH a AS (
  SELECT pia.*, p.program_type, p.is_member_facing FROM program_insurer_areas pia JOIN programs p ON p.id = pia.program_id
  WHERE pia.status NOT IN ('exited','out_of_scope')
), dup AS (
  SELECT state_id, enrollment_count, COUNT(*) n FROM a WHERE enrollment_count > 0 GROUP BY 1, 2 HAVING COUNT(*) > 1
)
SELECT s.id AS state, s.managed_care_type, s.is_regionalized, s.region_model_status,
  COUNT(a.id) FILTER (WHERE a.is_member_facing) AS mf_rows,
  COUNT(DISTINCT a.insurer_id) FILTER (WHERE a.is_member_facing) AS mf_insurers,
  string_agg(DISTINCT a.program_type, ',') AS program_types,
  COUNT(a.id) FILTER (WHERE a.is_member_facing AND s.managed_care_type = 'FFS' AND a.program_type = 'COMPREHENSIVE_MCO') AS ffs_mco_rows,
  CASE WHEN s.managed_care_type IN ('FFS','PCCM') THEN NULL
       ELSE COUNT(a.id) FILTER (WHERE a.is_member_facing AND COALESCE(a.enrollment_count, 0) = 0) END AS enroll_null,
  (SELECT COALESCE(SUM(n), 0) FROM dup WHERE dup.state_id = s.id) AS dup_enroll_rows
FROM states s LEFT JOIN a ON a.state_id = s.id
GROUP BY s.id, s.managed_care_type, s.is_regionalized, s.region_model_status
ORDER BY s.id;
```

## Q9 — Sizes

```sql
SELECT pg_database_size(current_database()) / 1048576 AS db_mb,
       pg_total_relation_size('ops.row_history') / 1048576.0 AS row_history_mb,
       (SELECT COUNT(*) FROM supabase_migrations.schema_migrations) AS migrations;
```

## Q10 — Plan-row statuses

Any status other than active, exited and out_of_scope is shown on the site (the export filters only
the last two) and needs a look.

```sql
SELECT status, COUNT(*) FROM program_insurer_areas GROUP BY status ORDER BY 2 DESC;
```
