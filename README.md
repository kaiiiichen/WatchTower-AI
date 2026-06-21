# WatchTower AI

**Flight radar for AI services** — detect Claude / GPT / Gemini outages before the official status page, and answer the question that keeps you up at 2 AM: *is it the service, or is it me?*

Built for [Cal AI Hackathon 2026](https://calai.dev) as a solo project. WatchTower AI is a **local developer tool**: you run it on your machine, your API keys stay yours, and probe history lives in a local SQLite file — nothing is uploaded to a shared cloud service.

---

## Table of contents

- [The problem](#the-problem)
- [What WatchTower AI does](#what-watchtower-ai-does)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Detection gap & academic backing](#detection-gap--academic-backing)
- [Product philosophy](#product-philosophy)
- [Project structure](#project-structure)
- [Testing](#testing)
- [Deployment notes](#deployment-notes)
- [References](#references)

---

## The problem

You're shipping with Claude, GPT, or Gemini. Something breaks at midnight. Is Anthropic down? Is your API key wrong? Is campus Wi‑Fi blocking Reddit? Is it just you?

Official status pages are slow, incomplete, and never tell you whether **your** environment is fine. WatchTower AI exists to close that gap: continuous independent probing, quality checks beyond "HTTP 200", local environment diagnosis, and honest data about how far official pages lag behind real user impact.

---

## What WatchTower AI does

WatchTower AI is organized in layers. Each layer is implemented and live — not a slide deck.

### 1. Probe layer — real-time monitoring

| Capability | Description |
|------------|-------------|
| **Independent probe network** | Concurrently probes Anthropic, OpenAI, and Google every 30 seconds (`asyncio.gather`). |
| **Dynamic model discovery** | At startup, queries each provider's list-models API and picks **flagship** and **mid** tiers by rule — no hard-coded model IDs that 404 when a model is retired. |
| **Multi-tier coverage** | Each provider gets two cards on the dashboard (e.g. `claude-opus-*` + `claude-sonnet-*`, `gpt-*` + `gpt-*-mini`, `gemini-*-pro` + `gemini-*-flash`). |
| **QA quality probe** | Asks `"What is 2+2? Answer with just the number."` and verifies the reply contains `"4"`. Catches "online but broken" failures that latency-only checks miss. |
| **Token generation rate** | Estimates output tokens per second from each probe response. |
| **Health scoring** | Rule-based score 0–100: start at 100, −35 on QA fail, latency penalty above a 1 s budget (capped at 40). Maps to `operational` (≥85), `degraded` (≥50), or `down`. |
| **Precursor warning (`degrading`)** | Detects steadily climbing latency *before* status crosses into degraded/down — a forward-looking heads-up, not a false alarm on jitter. |
| **Failure semantics** | Distinguishes genuine service faults (`down`, `degraded`) from account/config faults (`rate_limited` for HTTP 429, `misconfigured` for other 4xx). |
| **Graceful degradation** | Missing API key → provider reported as `unknown`; probe loop never crashes. |

### 2. Attribution layer — whose problem is it?

| Capability | Description |
|------------|-------------|
| **Four-way verdict** | Local diagnostics produce one of: **your-side** (environment), **account-side** (quota/key/config), **service-side** (provider outage), or **all-clear**. |
| **Local environment checks** | Per provider: DNS resolution, TCP connect to `:443`, and a minimal authenticated request to validate the API key. |
| **Environment profile** | Egress IP, resolved IPs, and network RTT — informational context separate from model latency. |
| **Smart alerts** | Rule-based alerts compare tiers (model-specific vs provider-wide outage), recommend failover (prefer same-provider healthy tier), and never conflate 429 with "service down". |
| **Community corroboration** | Reddit complaint-rate spikes upgrade a probe anomaly to a **confirmed widespread event** — additive only; absent Reddit data changes nothing. |

### 3. Research layer — why this matters

| Capability | Description |
|------------|-------------|
| **VU Amsterdam dataset backtest** | Computes real numbers from bundled CSV data (`backend/data/vu_dataset/`). |
| **Coverage gap** | **29.7%** of incidents (161/542) were never marked "investigating" in real time — resolved-only posts with no live acknowledgment. |
| **Official response latency** | Median **73 min** investigating → resolved (N=381); Anthropic median **55.5 min**. |
| **Case study delay** | Example incident: official acknowledgment **~23 min** after estimated user impact window. |
| **Honest boundaries** | Does **not** claim "we beat the status page by X minutes" without historical probe data. Argues the *window* high-frequency probing can fill. |

### 4. Observability — Sentry integration

| Layer | What it does |
|-------|----------------|
| **Layer 1 — Events** | Sends Sentry events for each degraded/down provider. |
| **Layer 2 — Fingerprinting** | Groups repeated probe cycles of the same model + anomaly into one issue (no alert storm). |
| **Layer 3 — Performance traces** | One transaction per probe cycle, one span per provider probe. |
| **Redaction** | Scrubs API keys from URLs (especially Gemini's `?key=` query param) before anything leaves the process. |

### 5. Persistence & engineering

| Capability | Description |
|------------|-------------|
| **SQLite history** | Probe results stored in `backend/data/watchtower.db`; survives backend restarts (7-day retention). |
| **Frontend proxy** | Next.js `/api/*` routes proxy the FastAPI backend; fall back to mock data when `BACKEND_URL` is unset or unreachable. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser  →  Next.js (localhost:3000)                         │
│    Dashboard · Provider cards · Alerts · Diagnostics · Backtest │
│    Polls /api/health every 30s                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ BACKEND_URL (optional)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Probe Engine (localhost:8000)                          │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Probe loop   │  │ Community    │  │ SQLite history store │  │
│  │ (30s)        │  │ loop (60s)   │  │ (watchtower.db)      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘  │
│         │                 │                                     │
│         ▼                 ▼                                     │
│  Claude / GPT / Gemini   Reddit JSON (corroboration)            │
│  (QA probe + scoring)                                           │
│                                                                 │
│  GET /health · GET /diagnose · GET /backtest                    │
│  Sentry (optional): events + fingerprints + traces              │
└─────────────────────────────────────────────────────────────────┘
```

**Stack**

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 16 (App Router) + React 19 + Tailwind CSS 4 |
| Backend | FastAPI + asyncio + httpx |
| Persistence | SQLite (stdlib `sqlite3`) |
| Observability | Sentry SDK (optional) |
| Research data | VU Amsterdam status-page dataset (bundled CSV) |

---

## Quick start

### Prerequisites

- **Node.js** 20+ (frontend)
- **Python** 3.11+ (backend)
- API keys for the providers you want to probe (optional — missing keys show as `unknown`)

### 1. Backend (probe engine)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env — add ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY as available
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Verify:

```bash
curl http://localhost:8000/health | jq .
curl http://localhost:8000/diagnose | jq .
curl http://localhost:8000/backtest | jq .
```

See [backend/README.md](./backend/README.md) for probe scoring, model discovery rules, and test commands.

### 2. Frontend (dashboard)

```bash
cd frontend
npm install
# Connect to the live backend:
echo 'BACKEND_URL=http://localhost:8000' > .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

Without `BACKEND_URL`, the dashboard serves **mock data** so the UI works standalone for demos.

### 3. Run both (typical dev)

Terminal A — backend on `:8000`. Terminal B — frontend on `:3000` with `BACKEND_URL=http://localhost:8000`.

The dashboard header shows **Last updated** from live probes when connected. Response header `x-watchtower-fallback: mock` indicates the frontend fell back to mock data.

---

## Configuration

### Backend (`backend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `GEMINI_API_KEY` | — | Google AI key (alias: `GOOGLE_API_KEY`) |
| `PROBE_INTERVAL` | `30` | Seconds between probe cycles |
| `PROBE_TIMEOUT` | `20` | Per-request probe timeout (seconds) |
| `HISTORY_LEN` | `20` | Latency sparkline points kept in memory |
| `TREND_WINDOW` | `5` | Probes inspected for precursor `degrading` trend |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Allowed frontend origins |
| `SENTRY_DSN` | — | Sentry project DSN (unset = disabled) |
| `SENTRY_ENVIRONMENT` | `watchtower` | Sentry environment tag |
| `REDDIT_USER_AGENT` | `python:watchtower-ai:v1.0 ...` | Required by Reddit's public JSON API |
| `COMMUNITY_INTERVAL` | `60` | Seconds between Reddit polls |
| `ENABLE_DOCS` | off | Set `1` to expose `/docs` and OpenAPI |

Model names (`ANTHROPIC_MODEL`, etc.) are **fallbacks only** — used when dynamic discovery fails.

### Frontend (`frontend/.env.local`)

| Variable | Description |
|----------|-------------|
| `BACKEND_URL` | Base URL of the FastAPI engine, e.g. `http://localhost:8000` |

---

## API reference

All backend routes return JSON. Types are shared with the frontend in `frontend/src/lib/types.ts`.

### `GET /health`

Live probe snapshot.

```json
{
  "providers": [ /* ProviderHealth[] — one entry per probed tier */ ],
  "alerts": [ /* Alert[] — rule-based, per anomaly */ ],
  "updatedAt": "2026-06-20T12:00:00+00:00",
  "community": [ /* CommunitySignal[] — Reddit corroboration */ ]
}
```

**Provider status values:** `operational` · `degrading` · `degraded` · `down` · `unknown` · `rate_limited` · `misconfigured`

### `GET /diagnose`

Local environment diagnosis cross-referenced with the current probe layer.

```json
{
  "checks": [ /* dns / tcp / key per provider */ ],
  "localHealthy": true,
  "verdictKind": "all-clear",
  "verdict": "Your environment looks fine and all probed providers are operational.",
  "checkedAt": "...",
  "profile": { "egressIp": "...", "hosts": [ /* DNS + TCP RTT */ ] }
}
```

**Verdict kinds:** `your-side` · `account-side` · `service-side` · `all-clear` · `indeterminate`

### `GET /backtest`

Detection lead-time analysis over the VU Amsterdam dataset. Returns `503` if CSV data is not bundled.

Key fields: `coverage` (including `all.pct` ≈ 29.7%), `latency` (stage statistics), `caseTimelines`, `resolvedHistogram`.

### Frontend proxy routes

| Route | Proxies to |
|-------|------------|
| `GET /api/health` | `{BACKEND_URL}/health` |
| `GET /api/diagnose` | `{BACKEND_URL}/diagnose` |
| `GET /api/backtest` | `{BACKEND_URL}/backtest` |

---

## Detection gap & academic backing

WatchTower AI's "Detection Gap" section on the dashboard is computed from real data — not marketing copy.

**Reference paper:** *An Empirical Characterization of Outages and Incidents in Public Services for LLMs* — Xiaoyu Chu et al., VU Amsterdam, **ICPE '25** (May 2025, Toronto).

**Dataset:** [Zenodo record 14018219](https://zenodo.org/records/14018219) · [GitHub atlarge-research/llm-service-analysis](https://github.com/atlarge-research/llm-service-analysis)

**Headline numbers (computed from bundled CSV):**

| Metric | Value |
|--------|-------|
| Incidents never marked "investigating" in real time | **29.7%** (161/542) |
| Median investigating → resolved | **73 min** (N=381) |
| Anthropic median investigating → resolved | **55.5 min** |
| Example case: impact → official acknowledgment | **~23 min** |

**What we claim:** Official status pages leave a blind window; high-frequency probing with QA checks can surface anomalies inside that window.

**What we do not claim:** Measured head-start over the status page on historical incidents (no probe data exists for those past events).

Three honest takeaways from the research (usable in demos):

1. Official status pages often under-report — users need independent fault awareness.
2. Provider outages should be part of normal developer workflow, not rare exceptions.
3. Community/user reports are an under-explored signal in peer-reviewed outage research — WatchTower AI explores this via Reddit corroboration.

---

## Product philosophy

WatchTower AI deliberately **did not** become a hosted "public signal service" or crowdsourced outage button. Design choices reflect a local-tool mindset:

- **You run it** — keys and probe history stay on your machine.
- **Corroboration, not dependency** — Reddit signals upgrade alerts but never block core detection.
- **Honest numbers** — backtest metrics are computed from CSV; estimated quantities (impact-window start parsed from description text) are flagged.
- **Right cuts** — features like BrowserBase scraping, StatusGator integration, ML classifiers, and periodicity prediction were dropped to keep one complete story line instead of many half-built modules.

---

## Project structure

```
WatchTower-AI/
├── README.md                 ← you are here
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI app, probe + community loops, routes
│   │   ├── probes.py         Model discovery, probing, scoring, alerts
│   │   ├── diagnostics.py    Local DNS/TCP/key checks + verdict
│   │   ├── community.py      Reddit community-signal layer
│   │   ├── backtest.py       VU dataset analysis
│   │   ├── store.py          SQLite probe history
│   │   ├── monitoring.py     Sentry integration (3 layers)
│   │   ├── config.py         Environment configuration
│   │   └── models.py         Pydantic models (mirror frontend types)
│   ├── data/
│   │   ├── watchtower.db     Local probe history (gitignored in prod use)
│   │   └── vu_dataset/       Bundled research CSV
│   └── tests/                pytest-style unit tests
└── frontend/
    ├── src/
    │   ├── app/              Next.js App Router pages + API proxy routes
    │   ├── components/       Dashboard UI (cards, alerts, charts, diagnostics)
    │   └── lib/types.ts      Shared TypeScript types
    └── public/
```

---

## Testing

From `backend/`:

```bash
# Model discovery & selection (offline)
PYTHONPATH=. .venv/bin/python tests/test_discovery.py

# Full test suite (if pytest available)
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q
```

Tests cover discovery rules, diagnostics verdicts, community signal parsing, backtest computations, SQLite store, Sentry event shape, and API handlers — all runnable without live API keys where possible.

---

## Deployment notes

| Component | Suggested target | Notes |
|-----------|------------------|-------|
| Frontend | Vercel | Set `BACKEND_URL` to your probe engine URL |
| Backend | Railway, Fly.io, or any Python host | Needs outbound HTTPS to provider APIs; persist `data/` volume for SQLite |
| Secrets | Environment variables only | Never commit `.env` |

For local development, both services on localhost is the intended workflow.

---

## References

- **Paper:** Chu, X. et al. *An Empirical Characterization of Outages and Incidents in Public Services for LLMs.* ICPE 2025.
- **Dataset:** VU Amsterdam LLM service analysis — Zenodo + GitHub links above.
- **Hackathon:** Cal AI Hackathon 2026 — solo build with AI-assisted development.

---

## License

See repository license file if present. API keys and local `watchtower.db` are yours — do not commit them.
