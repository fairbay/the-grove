# The Grove

Nature-themed walking portfolio where each idea grows from seed to fruit-bearing tree. First-person perspective with infinite scroll loop.

**Live at:** [bayleemiller.org](https://bayleemiller.org)

## Architecture

- **Vite + React + Tailwind** — SPA with two views.
- **Garden** (`src/App.jsx`) — Walking perspective with SVG plants, perspective projection, click-to-modal details.
- **Vault Dashboard** (`/vault`) — Table view of all ideas with filters, sort, search.
- **Router** (`src/GroveRouter.jsx`) — Routes between garden and vault, fetches data, maps vault fields to garden props.
- **Data** (`public/vault.json`) — Single source of truth. Only `portfolio_visible: true` entries appear in the garden.

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

1. Update `public/vault.json` (add ideas, change statuses, toggle `portfolio_visible`)
2. Push to GitHub → Vercel auto-deploys

Future: vault.json will be replaced by a live Grove API read (Phase C2) so the portfolio updates automatically when ideas change status in Grove.

## Deployment

Push to GitHub → Vercel auto-deploys at `bayleemiller.org`.
