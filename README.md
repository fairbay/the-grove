# The Grove 🌿

A nature-themed walking portfolio where each idea grows from seed to fruit-bearing tree. First-person perspective — scroll to walk the path.

Live at [bayleemiller.org](https://bayleemiller.org)

## Architecture

- **Garden** (`src/App.jsx`) — Walking perspective view with SVG plants, perspective projection, infinite scroll loop, click-to-modal details
- **Vault Dashboard** (`/vault`) — Table view of all ideas with filters, sort, search
- **Router** (`src/GroveRouter.jsx`) — Routes between garden and vault, fetches `public/vault.json`, maps vault fields to garden props
- **Data** (`public/vault.json`) — Single source of truth for all ideas. Only `portfolio_visible: true` entries appear in the garden.

## Dev

```bash
npm install
npm run dev
```

## Update Portfolio

1. Update `public/vault.json` (add ideas, change statuses, toggle `portfolio_visible`)
2. Push to GitHub — Vercel auto-deploys

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
