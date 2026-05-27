---
name: idea-vault
description: >
  Browse stored ideas — "show my ideas", "vault", "compare ideas", "what should
  I build next". Not for scouting (→ idea-scout), capture (→ grove), or
  calibration (→ review-panel).
metadata:
  version: "2026-05-27-02"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/baylee-skills` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# idea-vault — query and curate the stored idea catalog

Act like a librarian who knows the collection cold — surface the right entries
fast, compare them honestly, and answer "what should I build next?" with a
named recommendation, not a list dump.

Ideas live in **Grove (Supabase)**, accessed via MCP tools. The
`fairbay/idea-vault` repo is archived (read-only) — it was the source of truth
before the 2026-05-05 migration. All reads and writes go through Grove MCP;
no git-ops, no `ideas.json`.

## Routing — when this fires vs. its siblings

- **Browse / list / compare / rank** → vault. "Show my ideas", "what should I
  build next", "compare X and Y."
- **Save without scoring** → `grove` (capture-only path).
- **Score a new idea** → `idea-scout` (does its own Grove write in Phase 8).
- **Calibrate scores across the catalog** → `review-panel` (scores mode).

## Data access

Use Grove MCP tools for all operations:

| Operation | Tool | Notes |
|---|---|---|
| List/search | `grove_list_ideas` | Filters: `status`, `verdict`, `tag`, `q` (full-text) |
| Get one | `grove_get` | By UUID |
| Create | `grove_create_idea` | Minimum: title |
| Update | `grove_update` | Partial update by UUID |

## Schema

### Supabase idea fields

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | auto-generated |
| `title` | string | display name |
| `status` | enum | `raw`, `scouted`, `in_dev`, `shipped`, `shelved`, `gifted`, `killed` |
| `verdict` | enum \| null | `greenlight`, `overreach`, `public_good`, `mirage`, `workhorse`, `fools_gold`, `lark`, `pass` |
| `scores` | jsonb | `{"impact_pct": N, "business_pct": N, "sustainability_pct": N}` |
| `tags` | text[] | free-form |
| `notes` | text | one-liner + notes combined |
| `metadata` | jsonb | `key_insight`, `platform`, `deploy_url`, `portfolio_visible`, `hero_description`, `legacy_id` |
| `source` | enum | `claude-web`, `migration`, etc. |
| `created_at` | timestamptz | auto-set |
| `updated_at` | timestamptz | auto-updated |

### Legacy fields (migrated ideas only)

Ideas migrated from `ideas.json` (v3 schema) have these in `metadata`:

- `metadata.legacy_id` — old `idea_<8hex>` identifier
- `metadata.date_added` / `metadata.date_updated` — original dates
- `metadata.original_verdict` — pre-migration verdict string (e.g. "Unicorn"
  → `greenlight`)
- `metadata.key_insight` — one-line core insight
- `metadata.platform` — `web`, `iOS (native)`, `undecided`, etc.
- `metadata.deploy_url` — live URL if deployed
- `metadata.portfolio_visible` — show on The Grove
- `metadata.hero_description` — longer pitch for portfolio

### Zero-cost analysis fields (v1.0+)

Ideas evaluated against the zero-cost framework carry `metadata.zero_cost`:

| Field | Type | Notes |
|---|---|---|
| `version` | string | Framework version (e.g. "1.0") |
| `date` | string | Date of analysis (YYYY-MM-DD) |
| `tier` | int | 1=free as-is, 2=reduced free, 3=BYOK/capped |
| `arch` | string | Recommended zero-cost architecture pattern |
| `cost_drivers` | string | What prevents $0 hosting |
| `free_version` | string | What the zero-cost version includes |
| `popularity` | string | high, medium, low, niche |
| `effort` | string | Rough effort to reach free version |

**Tags:** `zc:t1`, `zc:t2`, `zc:t3` (tier), `zc:byok` (BYOK pattern),
`zc:popular` (high popularity potential). Filterable via `grove_list_ideas`
tag parameter.

## Commands

### `list` — summary table

`grove_list_ideas` with appropriate filters. Sorted most-recently-updated
first. Support filtering: status, tags, verdict, full-text search.

### `show <title>` — detailed view

Search with `grove_list_ideas` (q = title), then `grove_get` by UUID for full
details. Match by title (case-insensitive, fuzzy).

### `add` — save new idea

Use only when query intent is already established (e.g., user said `vault add`
or is mid-flow inside this skill). Standalone capture without a vault query
routes to `grove` instead — same Supabase write, simpler intent. Mechanism:
`grove_create_idea` with title, status (`raw` unless scored), tags, notes. If
a scout report exists in conversation, auto-populate all fields.

### `update <title>` — modify

Search → get UUID → `grove_update` with changed fields.

### `compare <title> <title> [...]` — side-by-side

2-4 ideas, scores, verdicts, key insights. If `metadata.zero_cost` exists,
include tier + architecture + popularity. Highlight the strongest candidate
by name; don't just dump the table.

### `search <keyword>` — find

`grove_list_ideas` with `q` parameter. Ranked matches.

### `prioritize` — rank backlog

All `scouted` / `raw` ideas ranked by weighted combination of the three lenses
+ recency. **Zero-cost tier is a tiebreaker** — between two similarly-scored
ideas, the one deployable for $0 has less friction. Surface top 3-5 with
reasoning. End with a named recommendation, not a list.

### `review` — pipeline overview

Kanban-style: count per status, longest-sitting, highest-scoring, tag patterns.

### `patterns` — analyze kills

Surface patterns across `killed` / `pass` ideas. Runs automatically at 5+
killed ideas in a session.

### `calibrate` — score accuracy

Available at 10+ scouted ideas. Compare predictions vs. outcomes. Hand off to
**review-panel** (scores mode) for the full adversarial pass — don't try to
calibrate inside this skill.

### `remove <title>` — kill

`grove_update` with `status: "killed"`. **Requires a kill reason** written into
`notes`. Don't delete — history is valuable.

## Rendering (browse mode)

When the user wants to see the vault visually:

**Chat:** produce a **React artifact**:

- Filterable/sortable table — cards on mobile, table on desktop
- Status badges: green=shipped, blue=in_dev, yellow=scouted, gray=raw,
  red=killed, teal=shelved, purple=gifted
- Score bars for all three lenses
- Click-to-expand for notes, insights, kill reasons
- Tag chips for filtering

Use React state for data — load from `grove_list_ideas` and pass as props.
Do NOT use `localStorage` / `sessionStorage` (artifact sandbox doesn't support
them; use `window.claude.storage` if persistence is needed).

**Code / Routines:** present as a formatted table in terminal output or prose.
No artifact rendering available.

## Style

- **Tables over prose.** Fast in, fast out.
- **Deliver conclusions.** "Your strongest unbuilt idea is X" beats dumping
  the table.
- **Name the idea in every response** — "For PushCraft, …" keeps focus clear.

## Integration

- **← idea-scout:** auto-adds via `grove_create_idea` (Phase 9). This skill
  doesn't score new ideas — scout does.
- **← brainstorm-engine:** bulk-adds raw tier-1/tier-2 ideas via `add` when the
  user wants to retain a brainstorm batch for later scouting.
- **← grove:** capture-only writes flow in as `status: raw`. Vault later
  promotes them via `update` after scouting.
- **← architect / build / ship-it:** status transitions (`scouted` → `in_dev`
  → `shipped`) and deploy URLs land in metadata.
- **→ review-panel (scores mode):** `calibrate` command hands off the
  adversarial score review.
- **→ The Grove portfolio:** public endpoint reads `portfolio_visible: true`
  ideas from Supabase.

## What this skill does NOT do

- Score new ideas (→ `idea-scout` does scoring inline).
- Redesign scoring methodology (→ `review-panel` scores mode).
- Capture without query intent (→ `grove`).
- Push code or specs (→ `git-ops`).
