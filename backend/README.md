# WatchTower AI — Backend (FastAPI Probe Engine)

Concurrently probes Claude / GPT / Gemini every `PROBE_INTERVAL` seconds
(`asyncio.gather`), scores their health, and serves a snapshot at `GET /health`
whose JSON matches `frontend/src/lib/types.ts` exactly.

## Dynamic model discovery
At startup each provider's list-models endpoint is queried and two models are
picked by rule — no hard-coded versions that 404 when a model is retired:
- **flagship** — Anthropic: latest `opus` · OpenAI: highest-version `gpt-*`
  (excludes mini/nano/audio/realtime/**pro** — `gpt-*-pro` is responses-only) ·
  Gemini: latest `gemini-*` `pro`
- **mid** — Anthropic: latest `sonnet` · OpenAI: that family's `-mini` ·
  Gemini: latest `flash` excluding `lite`

"Latest" compares version/date suffixes in the model name. Discovery failure (or
missing key) falls back per-tier to the `*_MODEL` / `*_MODEL_MID` env vars.
Each provider is then probed at **both** tiers; the dashboard shows a card per tier.

## What each probe measures
- **Latency / availability** — one minimal QA request, round-trip timed, HTTP status recorded.
- **QA probe** — asks `"What is 2+2? Answer with just the number."`; passes if the reply contains `"4"`.
- **Token rate** — output tokens ÷ latency (rough tokens/sec).
- **Health score** — coarse weighting: start 100, −35 on QA fail, latency penalty above a 1s budget (capped 40).
  `≥85 operational · ≥50 degraded · else down`.

A provider with **no API key** is reported as `unknown` (never crashes the loop).

## Run
```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in the keys you have
.venv/bin/uvicorn app.main:app --reload --port 8000
curl localhost:8000/health
```

## Connect to the frontend
Set `BACKEND_URL=http://localhost:8000` for the Next.js app — its `/api/health`
route proxies this engine (and falls back to mock data if unreachable).

## Layout
- `app/config.py` — env config (keys, models, interval, CORS)
- `app/probes.py` — per-provider adapters, scoring, rolling history, `probe_all`
- `app/models.py` — Pydantic models mirroring the frontend types
- `app/main.py` — FastAPI app, background probe loop, `GET /health`

## Tests
`PYTHONPATH=. .venv/bin/python tests/test_discovery.py` — 8 offline tests
(selection rules, version comparison, live-then-fallback, list parsing).

## Verified
- Discovery + probing verified **live** against all three providers: it selected
  `claude-opus-4-8`/`claude-sonnet-4-6`, `gpt-5`/`gpt-5-mini`,
  `gemini-*-pro`/`gemini-*-flash` — real current models, probed `operational`.
- Provider quirks handled (found via live probes): OpenAI needs
  `max_completion_tokens` (not `max_tokens`) and `gpt-*-pro` is responses-only;
  Gemini 3.x reasoning needs a larger output budget or returns empty content.
- Missing key → `unknown`; non-200 / overloaded (e.g. Gemini `503`) → `down`.

## Not yet (later modules)
Alerts are minimal rule-based stubs — the full "Agent" chain (history-based
recovery ETA, LLM insight, Sentry event) and Supabase persistence come next.
OpenAI/Gemini list-models pagination is single-page (`pageSize=1000`).
