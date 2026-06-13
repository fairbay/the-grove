# The Grove 🌿

A nature-themed walking portfolio where each idea grows from seed to fruit-bearing tree. First-person perspective — scroll to walk the path.

Live at [bayleemiller.org](https://bayleemiller.org)

## Architecture

- **Garden** (`src/App.jsx`) — Walking perspective view with SVG plants, perspective projection, infinite scroll loop, click-to-modal details
- **Vault Dashboard** (`/vault`) — Table view of all ideas with filters, sort, search
- **Router** (`src/GroveRouter.jsx`) — Routes between garden and vault, maps vault fields to garden props
- **Data** — ⚠️ **stale, v3 pending (2026-06-12):** deployed code fetches a legacy Google Apps Script endpoint; `public/vault.json` is vestigial (March). grove-site v3 replaces this with Grove's anonymous public-read API (decision `fc99d106`; spec in `fairbay/grove` `docs/PLATFORM-SPEC.md` §8.2). Live site renders frozen data until v3 lands.

## Dev

```bash
npm install
npm run dev
```

## Update Portfolio

⚠️ **Blocked by v3 (2026-06-12):** editing `public/vault.json` no longer affects the live site (deployed build reads a legacy Apps Script endpoint; v3 replaces the data path with Grove's public-read API). Until grove-site v3 ships, content updates are on hold. See CLAUDE.md for the v3 plan.

## Plant Growth Stages

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

Pink flowers = impact score. Red fruit = business score. Counts are relative to the highest-scoring project.

v2.0.0
