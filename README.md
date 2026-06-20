# Watchtower AI

Flight radar for AI services — detect Claude / GPT / Gemini outages before the official status page, and tell users "is it your problem?"

## Structure
- `frontend/` — Next.js (App Router) + Tailwind → Vercel
- `backend/`  — FastAPI + asyncio → Railway (probe engine, anomaly detector, alert/agent chain, Sentry)

## Walking skeleton (current)
Frontend Dashboard polls `/api/health` every 30s. That route currently serves mock data (`src/lib/mock-data.ts`).
Swap to the real backend by pointing the route handler at `BACKEND_URL` — see `frontend/src/app/api/health/route.ts`.

## Run frontend
```bash
cd frontend && npm install && npm run dev
```
