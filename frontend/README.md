# WatchTower AI — Frontend

Next.js 16 dashboard for WatchTower AI. Polls the probe engine every 30 seconds and renders provider health, alerts, local diagnostics, community signals, and the VU dataset backtest ("Detection Gap").

## Prerequisites

- Node.js 20+
- Running backend (optional) — see [backend/README.md](../backend/README.md)

## Setup

```bash
npm install
cp .env.local.example .env.local   # or create manually
npm run dev
```

Create `frontend/.env.local`:

```bash
BACKEND_URL=http://localhost:8000
```

Open [http://localhost:3000](http://localhost:3000).

Without `BACKEND_URL`, `/api/health` serves mock data from `src/lib/mock-data.ts` so the UI works standalone.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Development server (default port 3000) |
| `npm run build` | Production build |
| `npm run start` | Serve production build |
| `npm run lint` | ESLint |

## API proxy routes

These server routes forward to the FastAPI backend when `BACKEND_URL` is set:

| Route | Backend |
|-------|---------|
| `GET /api/health` | `GET /health` |
| `GET /api/diagnose` | `GET /diagnose` |
| `GET /api/backtest` | `GET /backtest` |

On backend failure, health/backtest routes fall back to mock data and set `x-watchtower-fallback` response headers.

## Key files

| Path | Purpose |
|------|---------|
| `src/app/page.tsx` | Main dashboard |
| `src/lib/types.ts` | Shared types (mirrors backend JSON) |
| `src/components/ProviderCard.tsx` | Per-tier health card + latency sparkline |
| `src/components/AlertBanner.tsx` | Attribution, failover, community confirmation |
| `src/components/LocalDiagnostics.tsx` | Environment checks + verdict |
| `src/components/CommunitySignals.tsx` | Reddit corroboration heat |
| `src/components/DetectionGap.tsx` | VU dataset backtest charts |

## Stack

- Next.js 16 (App Router)
- React 19
- Tailwind CSS 4
- TypeScript

See the [root README](../README.md) for architecture, configuration, and deployment.
