@.claude/global.md

# the-grove

Nature-themed walking portfolio where each idea grows from seed to fruit-bearing tree. First-person perspective with infinite scroll loop.

**Live at:** [bayleemiller.org](https://bayleemiller.org)

## Architecture

- **Vite + React + Tailwind** — SPA with two views.
- **Garden** (`src/App.jsx`) — Walking perspective with SVG plants, perspective projection, click-to-modal details.
- **Vault Dashboard** (`/vault`) — Table view of all ideas with filters, sort, search.
- **Router** (`src/GroveRouter.jsx`) — Routes between garden and vault, fetches data, maps vault fields to garden props.
- **Data** (`public/vault.json`) — Only `portfolio_visible: true` entries appear in the garden. ⚠️ **Stale / v3 pending (2026-06-12):** the deployed code actually fetches a legacy Google Apps Script endpoint (Sheets-era), and `public/vault.json` is vestigial (last updated March). Both are two migrations behind Grove. Decision `fc99d106` replaces this data path wholesale in grove-site v3 with the anonymous Grove public-read API (`fairbay/grove` `docs/PLATFORM-SPEC.md` §8.2). No interim fix — the live site renders frozen data until v3 lands.

## Plant growth stages

| Status | Plant | Scale |
|--------|-------|-------|
| raw | Seed | 0.2x |
| scouted | Sprout | 0.35x |
| building | Sapling | 0.55x |
| in-dev | Young Tree | 0.75x |
| deployed | Flowering | 0.9x |
| shipped | Bearing Fruit | 1.0x |
| parked | Dormant | 0.6x |
| killed | Composted | 0.15x |

Pink flowers = impact score. Red fruit = business score. Counts relative to the highest-scoring project.

## Updating the portfolio

⚠️ **Editing `public/vault.json` no longer affects the live site** — the deployed build fetches a legacy Apps Script endpoint, and v3 will replace the data path entirely. Until grove-site v3 ships, treat content updates as blocked-by-v3.

**v3 (planned, decision `fc99d106`):** the portfolio becomes data-driven from Grove's anonymous public-read API (`GET /api/public/portfolio`, spec'd in `fairbay/grove` `docs/PLATFORM-SPEC.md` §8.2) over category paths (`/apps`, `/papers`, …). Publishing an item = flip `portfolio_visible` in Grove. Architecture pass pending (idea `f5598938`).

## Deployment

Deployed at `bayleemiller.org` via Vercel.
