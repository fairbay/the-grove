---
name: project-health
description: >
  MBN health check — "status report", "scorecard", "health check",
  "how's the navigator doing". Audits DB + Grove + Vercel with real
  metrics. Not mid-session (→ chat-status) or close (→ chat-archive).
metadata:
  version: "2026-10-20-02"
---

# project-health — is the live MBN site trustworthy, current, and shipping?

**Version gate (chat only):** In claude.ai, compare this skill's
`metadata.version` against `fairbay/ops` via git-ops. If behind,
warn once and continue. If fetch fails, skip silently. In Claude Code /
Routines, skip — skills are synced from source.

Act like an auditor who reports what moved, not what is big. medicaidrewards.com
has served the V4 app since 2026-09-26, so every finding is about what members see
today. Listing totals and row counts are never health metrics.

The run reads; it never writes content or builds a fix. Data fixes go through the
migration library in a data session; visible changes need Baylee's OK on
screenshots (MBN CLAUDE.md standing rules). The run's outputs are a report,
Grove tasks and one Grove decision.

**Fixed identifiers:** Supabase `mqbnsjkeucvumdoqdeww`; repo
`fairbay/medicaid-benefits-navigator`; Grove list `medicaid-benefits-navigator`,
`project_ref` `fairbay/medicaid-benefits-navigator`; Vercel project
`prj_dtvpPh1fOMELsmJNJSxuVYGXrcMD`, team `team_hDPlehxYhRW7Hrq8ddre65Qg`.

## Workflow

1. **Goal line.** The first message says `Goal: health check, 0/7 — OFF-PATH
   (Baylee asked), launch readiness D/12` (MBN CLAUDE.md "Two progress numbers":
   a health check moves no ledger item, and Baylee asking for it is the OK).
   Each checkpoint reports `Session: N/7 (X%)`.
2. **Pre-flight.** `get_advisors(security)`. It doubles as the hibernation check:
   compute can sleep while `get_project` says `ACTIVE_HEALTHY`, and `execute_sql`
   then times out. If it is asleep, give Baylee one numbered step, opening
   https://supabase.com/dashboard/project/mqbnsjkeucvumdoqdeww to wake it, and
   run everything that doesn't need the database meanwhile. Never declare the
   database down before this.
3. **Gather.** Run every block in `references/queries.md`. Then:
   - **Repo** (Code: the working tree; chat: attach the repo with read access and
     clone it, per the global rule "Design runs read the real system first"):
     - Read the launch-readiness ledger and the LR-11 row in PLAN.md. Read the
       line `launch readiness: D/12`; never recompute it.
     - Get the LR-11 rate from the `accuracy_checks` table once it exists; until
       then, from `reports/accuracy/` (docs/ACCURACY-AUDIT.md).
     - Run `npm run data:pull`, then `node scripts/wording-debt.mjs` and
       `node scripts/validate-data.mjs --gate` on the live set. The gate is the
       same check publish runs: reward-unit drift, broken links. Exit 0 is the bar.
   - **Live site:** `curl -sL https://www.medicaidrewards.com/data/manifest.json`
     and read its `exported_at`. It must be later than Q7's `last_applied`.
     A READY deployment does not prove the data is current.
   - **GitHub** (`gh api repos/fairbay/medicaid-benefits-navigator/...`):
     - `actions/workflows/smoke.yml/runs?event=schedule&per_page=1` and the same
       for `backup.yml` (the scheduled runs only; smoke also runs on pushes).
     - `actions/workflows/publish.yml/runs?per_page=1`.
     - `commits/main/status` (the `Vercel` context).
     - `pulls?state=open`: ready PRs, and drafts older than 14 days.
     - For a failed run, read `check-runs/<id>/annotations`. A billing annotation
       means the Actions minutes are gone: say so and don't retry.
     - Don't use `--paginate` through the session proxy; page by hand.
   - **Vercel:** `list_deployments` (latest production state) and
     `get_runtime_errors` for production.
   - **Grove:**
     - `grove_list_adjudications(list, status="open")` and the open tasks on
       the list.
     - The baseline: the newest decision whose text starts `Health check ` in
       `grove_list_decisions(project_ref, limit=30, compact=false)`. With none,
       fall back to the `health-check-*` tasks and
       `reports/2026-09-28-project-health.md` in the repo.
   If a source can't be reached, say which and report the rest.
4. **Score** against the tables below and compare every number with the baseline.
   A finding is a class until shown otherwise. When a metric has a gap, count
   every row in the gap and find where it started (Q4's weekly breakdown is the
   pattern), not one example.
5. **Report** (see "Report").
6. **File in Grove** (see "Grove").
7. **Check the work.** Check every figure in the report and the decision against
   the raw output. Re-run the arithmetic; don't recall it.

## Metrics

### Headline

- **Launch readiness D/12**, with the open LR rows and what each waits on.
- **LR-11 accuracy rate** (sampled accuracy audit, Grove 877562ca). Until a
  rate exists, report its step. Once it exists, the rate and its margin lead the
  report: it is the only metric that measures whether what a member reads is right.

### Trust and currency (red / amber / green)

| Metric | Query | Red | Amber | Green |
|---|---|---|---|---|
| Snapshot capture (appearances of live sources) | Q4 | <25% | <50% | ≥50% |
| Appearance coverage (live sources) | Q4 | <40% | <70% | ≥70% |
| Link-label fill | Q4 | <70% | <90% | ≥90% |
| Handbook-anchored plans (n/a states left out) | Q3 | <80% | <95% | ≥95% |
| Reward cards showing the plan-year note (lower is better) | Q5 | >25% | >10% | ≤10% |
| Shown listings with reward units | Q6 | <90% | <98% | ≥98% |
| Security advisors | pre-flight | any ERROR | any WARN | INFO only |

- **Handbook:** name every gap plan from Q3, whatever the colour; the list is the
  work. A state program filed as a plan shows up here.
- **Plan-year note:** this is the share of reward pages that say "From the 20xx
  plan documents; 20yy may differ." (FR-036). It jumps on January 1. Until the
  January rollover sweep (Grove ddb807a0) closes, report it against that sweep
  instead of colouring it. In the per-state list, rank states by cards affected,
  not by percentage: an FFS state with four rewards reads 100%. Baylee's open
  decision f3a98351 on the plan-year line may change what this counts.
- **Q4 scope:** Q4 measures over sources behind shown listings. Runs before
  2026-10-17 measured over all sources; say so when comparing with them.

### Trend only (number and delta, no colour)

- **Source checks:** live sources checked in the last 120 days, and
  `never_checked` (Q5). No scheduled fingerprint run exists yet, so this gets a
  colour only once one does (SOURCE-DISCOVERY "Staleness detection").
- **Wording:** "N of M shown listing texts carry a standing-rule flag", from
  `wording-debt.mjs`. It falls as wording sweeps land; a rise means a batch added
  flagged text.
- **Multi-unit listings** (Q6): the functional-atomization backlog (PLAN Step 28
  C1, Grove 9e68976d). It falls as C1 lands.
- **Open unit reviews** and **POINT units** (Q6). The standing rule is "No points,
  ever", so the POINT count should reach zero (Grove 98158534, 20caffcc).
- **Enrollment null share** (Q8, member-facing rows outside FFS/PCCM states).
- **`ops.row_history` growth** since the baseline (Q9). It has no retention yet.

### Regression guards (expected to hold; any break is a top finding)

From Q1, and per state from Q2:

- Plans without listings = 0. A member-facing plan with none is an empty page;
  name it from Q1's second block.
- Listings without a source = 0.
- Every state's extractions per listing ≥ 1.0.
- Eligibility, values on INCENTIVE/GOODS, and confirmed ≥98% overall, and no
  state below 90%.
- Grounding average ≥0.95.
- Any drop from the baseline.

Report the guards as one line when all hold.

A drop in eligibility or values needs an explanation, and is never filled by
inference: "only what official documents state" and "where the plan has not
published a rule, link, never summarise" make an absent value legitimate. These
two guards read the legacy lists; move them to reward units when phase 4 of the
unit model makes those lists projections.

### Pipeline (pass / fail)

- **Live data current:** the manifest's `exported_at` is later than `last_applied`.
- **Publish holds** (Q7): no row, or one no older than a running apply. An old
  hold blocks every build and publish.
- **Applied, not published** (Q7): zero, or `oldest_unpublished` within the day.
- **Vercel:** latest production deployment READY; the `Vercel` status on main is
  success; no new runtime errors.
- **Workflows:** the last scheduled `smoke.yml` and `backup.yml` runs succeeded
  in the last 26 hours; the last `publish.yml` run succeeded and is later than
  `last_applied`.
- **Data gate:** `validate-data.mjs --gate` exits 0.
- **Database size** (Q9) under 400 MB (the free tier allows 500 MB).
- **Outside-model spend** (Q11): every provider and `all` at or under its
  `weekly_calls` and `monthly_usd`, and none tripped (`tripped_until` in the
  future). Report calls, refusals, errors and dollars as numbers too; a rise
  in refusals or errors is a finding even while the caps hold.
- **Queues:** open adjudications; untriaged feedback (Q7; above zero sends it to
  the weekly triage, Grove c0c2d6e3); ready PRs; drafts older than 14 days.

### Structural smells (Q8, Q10)

- **Regionalized states whose `region_model_status` is not `verified`.** The site
  auto-picks a plan only where it is verified (`MRAdapt.nextStep`). List these
  states by status.
- **A regionalized state with a single member-facing insurer** (a modeling
  mismatch).
- **`ffs_mco_rows` above zero:** a member-facing COMPREHENSIVE_MCO row in an FFS
  state.
- **`dup_enroll_rows` above zero:** an enrollment count copied across rows, not
  sourced.
- **Q10: plan rows in any status other than active, exited or out_of_scope.** The
  site shows them.

### Rules

- **Shown** is the export's filter, status not in (exited, out_of_scope), used in
  every query.
- Plan coverage and handbook count member-facing programs only. Handbook is n/a
  for an FFS or PCCM state with no plan handbook (decision 34950652).
- Confirmed % counts distinct listings.
- Only `plan_document` counts as a handbook.

## Report

Lead with the answer: what is red, what moved since the baseline, and launch
readiness. Order findings by what a member would hit, not by the lowest number.
Each finding gives the metric, what members see because of it, its scope
(counted), and the Grove task that owns it.

**Surface branching:**
- **Chat:** at most two inline visuals, styled for dark mode, since Baylee is
  often on a phone. Never use colour alone for status; pair it with an icon and a
  label.
  - First visual: the headline numbers and every scored metric with its status.
  - Second visual: the per-state watch list from Q2, sortable, holding only
    states with a non-green value, a guard break or a non-verified region model.
  - Prose goes between and after the visuals; actions come last.
- **Code / Routines:** the same content as markdown in the session or run output.
  Don't write a report file to the repo; the Grove decision is the record.

## Grove

- **Search before filing.** For each finding, look for an open task that already
  covers it (`grove_list_tasks` with `q` on its key words, and past runs' tags).
  If one exists:
  - Read it in full with `grove_get` first: `grove_update_task` replaces `notes`
    and `tags` whole.
  - Write back the old notes with a dated `## Update, health check YYYY-MM-DD`
    section on top.
  - Keep the old tags and add this run's tag.
  - Raise the priority if the metric turned red.
  - Never file a duplicate.
- **New tasks** only for red or amber metrics, guard breaks, pipeline failures and
  new structural smells, at most five per run.
  - Each has Why, Before (live numbers), Approach, and Done when.
  - Tag `health-check-YYYY-MM-DD`; list `medicaid-benefits-navigator`.
  - Anything smaller goes in the decision.
- **One decision per run.**
  - The text starts `Health check YYYY-MM-DD:` and holds every metric's value and
    the watch-list state codes; it is the next run's baseline.
  - Under 2,000 characters.
  - Tags `project-health` and `health-check-YYYY-MM-DD`.
- **Two tracks:** a finding that needs Baylee in the real world (an account, a
  lawyer, an outside service) goes as one line to Grove project `mbn-launch-ops`
  and isn't discussed (MBN PLAN.md "Tracks").

## Ops read — decision routing (outside this charter)

A section of its own, after the health report, on every run (the run Baylee
already schedules; no new timer) and whenever he asks for "the ops read". It
is not a member-facing metric: its filings sit outside the five-task cap and
the health decision. Design: `fairbay/ops` docs/decision-routing/DESIGN.md §4–§5.

1. **Gather** (window: the 7 days ending today, UTC), saving each as JSON in the
   working directory:
   - `decisions.json`: `grove_list_decisions(project_ref=…, current_only=false,
     compact=false, limit=100)` for `fairbay/ops`, `ops`,
     `fairbay/medicaid-benefits-navigator` and any repo with a
     `.claude/policy.json`, concatenated (the script keeps the `session-record`
     and `reversal` tags). A list that comes back with 100 rows hit the cap:
     say S4's window may be truncated for that repo.
   - `cards.json`: `grove_list_tasks(tag="wrong_question", compact=false,
     limit=100)` (adjudication listings carry no tags; the task read does).
   - `activity.json`: `{repo, date, kind, ref, message}` rows from
     `gh api "repos/fairbay/<repo>/commits?since=<ISO>&per_page=100"` (commits)
     and `grove_events` in the window (Grove writes, repo from the entity's
     `project_ref`); keep each commit's first message line (the script drops
     sync.py's `sync …` mirror commits).
   - `runs.json`: the newest run of `sync.yml` (ops) and `rules.yml` (each repo
     that has it): `gh api "repos/fairbay/<repo>/actions/workflows/<file>/runs?per_page=1"`.
   - Each repo's `.claude/policy.json` (from a clone or `contents/.claude/policy.json`).
2. **Run** `python3 .claude/skills/chat-archive/scripts/ops_read.py --decisions
   decisions.json --cards cards.json --activity activity.json --runs runs.json
   --policy fairbay/ops=<path> --policy fairbay/medicaid-benefits-navigator=<path>`
   (`--json` for the actions). Thresholds come from each policy; a "not judged"
   line is reported as is, never filled with a default.
3. **File what it lists**, searching each action's `dedup_key` first
   (`grove_list_tasks(q=<dedup_key>)`; never a duplicate) and filing its body
   unchanged, so the `dedup:` line it ends with is in the notes next week: one Grove task per
   S1/S2 breach (list `ops`, tags `decision-routing`, `ops-read-YYYY-MM-DD`;
   after one design round on an edge, the edge goes to Baylee as a ruling);
   one adjudication card per S4/S5 breach with the script's recommendation and
   stakes; each S5 postmortem as one line in the repo's project `next_actions`.
   "Activity with no record" is reported, never read as a quiet week.
4. **Print** the script's section verbatim under the health report, including
   the interactions and the last sync.yml and rules.yml conclusions.

## Integration

- **← session-start:** can open a session for orientation.
- **→ add-to-do / grove:** findings become Grove tasks.
- **→ chat-archive:** at session end, hand off.
- **Skill upkeep:** a metric that stays green across several runs moves to the
  guards. A new product surface or pipeline stage gets a metric here
  (skill-creator-b).
