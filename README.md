# WatchTower AI

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Next.js](https://img.shields.io/badge/Next.js-16-black)](frontend/package.json)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)](backend/requirements.txt)

Next.js · React · TypeScript · Tailwind · FastAPI · Python · SQLite · Docker · Sentry

**English** · **中文**

| | |
| --- | --- |
| **Source** | https://github.com/kaiiiichen/WatchTower-AI |
| **Hackathon** | [UC Berkeley AI Hackathon 2026](https://ai-hackathon-2026.devpost.com/) |
| **Local demo** | Frontend `http://localhost:3000` · Backend `http://localhost:8000` |
| **Docker demo** | `docker compose up --build` → [http://localhost:3000](http://localhost:3000) |

---

## English

→ [中文](#中文)

### Contents

1. [The idea](#the-idea)
2. [UC Berkeley AI Hackathon 2026](#uc-berkeley-ai-hackathon-2026)
3. [What WatchTower AI does](#what-watchtower-ai-does)
4. [Getting started — pick your path](#getting-started--pick-your-path)
5. [Prerequisites](#prerequisites)
6. [Quick start (Docker)](#quick-start-docker)
7. [Quick start (local dev)](#quick-start-local-dev)
8. [Verify it works](#verify-it-works)
9. [Configuration](#configuration)
10. [Troubleshooting](#troubleshooting)
11. [API reference](#api-reference)
12. [Architecture](#architecture)
13. [Detection gap & academic backing](#detection-gap--academic-backing)
14. [Product philosophy](#product-philosophy)
15. [Project structure](#project-structure)
16. [Testing](#testing)
17. [Deployment notes](#deployment-notes)
18. [Documentation map](#documentation-map)
19. [License](#license)

### The idea

**WatchTower AI** is **flight radar for AI services** — detect Claude / GPT / Gemini outages before the official status page, and answer the question that keeps you up at 2 AM: *is it the service, or is it me?*

Official status pages are slow, incomplete, and never tell you whether **your** environment is fine. WatchTower AI closes that gap with continuous independent probing, QA checks beyond "HTTP 200", local environment diagnosis, and honest data about how far official pages lag behind real user impact.

It is a **local developer tool**: you run it on your machine, your API keys stay yours, and probe history lives in a local SQLite file — nothing is uploaded to a shared cloud service.

### UC Berkeley AI Hackathon 2026

Built at **[UC Berkeley AI Hackathon 2026](https://ai-hackathon-2026.devpost.com/)** (June 20–21, 2026) by **Kai Chen** ([@kaiiiichen](https://github.com/kaiiiichen)) as a **solo project**. All implementation occurred during the hackathon window.

#### Elevator pitch (for Devpost)

> WatchTower AI is a local flight radar for Claude, GPT, and Gemini — it probes providers every 30 seconds with real QA checks, diagnoses whether an outage is on your side or theirs, and backs its "detection gap" claims with peer-reviewed outage research. When something breaks at 2 AM, you get an honest answer in seconds instead of refreshing a status page that may still say "operational."

#### Devpost submission checklist

| Requirement | Where |
| --- | --- |
| 2–3 sentence summary | Use the elevator pitch above |
| Project image | Screenshot of the dashboard (`localhost:3000` or deployed URL) |
| GitHub repository link | https://github.com/kaiiiichen/WatchTower-AI |
| Team name & table number | Enter on [Devpost](https://ai-hackathon-2026.devpost.com/) |
| Demo | Live dashboard + `GET /health` JSON; 5-minute table presentation |
| Built during hackathon | Yes — ideation allowed beforehand; all code written June 20–21, 2026 |

**Judging alignment** (Application · Functionality · Creativity · Technical complexity):

- **Application** — Every LLM developer hits midnight outages; independent probing + local diagnostics is immediately usable.
- **Functionality** — Full probe loop, four-way verdict, alerts, HN + Downdetector corroboration, official status pages, VU dataset backtest, optional Sentry — all implemented, not mocked.
- **Creativity** — QA probe ("2+2=4"), precursor `degrading` trend, multi-source corroboration as additive signals, honest boundaries on what we can claim.
- **Technical complexity** — Dynamic model discovery, asyncio concurrent probes, SQLite history, Playwright adapters (Browserbase CDP + optional local Chromium), three-layer Sentry integration, research backtest from bundled CSV.

**Sponsor track note:** Sentry integration (events + fingerprinting + performance traces with API-key redaction) qualifies for the [Best Use of Sentry API](https://ai-hackathon-2026.devpost.com/) prize criteria.

### What WatchTower AI does

WatchTower AI is organized in layers. Each layer is implemented and live.

#### 1. Probe layer — real-time monitoring

| Capability | Description |
| --- | --- |
| **Independent probe network** | Concurrently probes Anthropic, OpenAI, and Google every 30 seconds (`asyncio.gather`). |
| **Dynamic model discovery** | At startup, queries each provider's list-models API and picks **flagship** and **mid** tiers by rule — no hard-coded model IDs that 404 when retired. |
| **Multi-tier coverage** | Each provider gets two dashboard cards (e.g. `claude-opus-*` + `claude-sonnet-*`). |
| **QA quality probe** | Asks `"What is 2+2? Answer with just the number."` and verifies the reply contains `"4"`. |
| **Token generation rate** | Estimates output tokens per second from each probe response. |
| **Health scoring** | Rule-based score 0–100 → `operational` (≥85), `degraded` (≥50), or `down`. |
| **Precursor warning (`degrading`)** | Detects steadily climbing latency *before* status crosses into degraded/down. |
| **Failure semantics** | Distinguishes service faults (`down`, `degraded`) from account faults (`rate_limited`, `misconfigured`). |
| **Graceful degradation** | Missing API key → `unknown`; probe loop never crashes. |

#### 2. Attribution layer — whose problem is it?

| Capability | Description |
| --- | --- |
| **Four-way verdict** | Local diagnostics: **your-side**, **account-side**, **service-side**, or **all-clear**. |
| **Local environment checks** | Per provider: DNS, TCP `:443`, minimal authenticated request. |
| **Smart alerts** | Rule-based alerts compare tiers, recommend failover, never conflate 429 with "service down". |
| **Community corroboration** | Hacker News complaint-rate spikes + optional Downdetector (Browserbase CDP) — additive only. |
| **Official status pages** | Statuspage JSON (Claude, OpenAI) + Gemini AI Studio adapter; cites provider wording when available. |

#### 3. Research layer — why this matters

| Capability | Description |
| --- | --- |
| **VU Amsterdam dataset backtest** | Real numbers from bundled CSV (`backend/data/vu_dataset/`). |
| **Coverage gap** | **29.7%** of incidents (161/542) never marked "investigating" in real time. |
| **Official response latency** | Median **73 min** investigating → resolved (N=381). |
| **Honest boundaries** | Does **not** claim measured head-start without historical probe data. |

#### 4. Observability — Sentry integration

| Layer | What it does |
| --- | --- |
| **Events** | Sentry events for each degraded/down provider. |
| **Fingerprinting** | Groups repeated probe cycles into one issue. |
| **Performance traces** | One transaction per probe cycle, one span per provider. |
| **Redaction** | Scrubs API keys from URLs before anything leaves the process. |

#### 5. Persistence & engineering

| Capability | Description |
| --- | --- |
| **SQLite history** | `backend/data/watchtower.db`; 7-day retention (ephemeral in Docker unless you mount a volume). |
| **Frontend proxy** | Next.js `/api/*` routes proxy FastAPI; dashboard shows a clear offline state when backend is unreachable. |

---

### Getting started — pick your path

WatchTower AI is a **monorepo** with two services: a FastAPI probe engine (`backend/`) and a Next.js dashboard (`frontend/`). There are two ways to run them — pick based on what you're trying to do:

| Path | Best for | You need on your machine | Hot reload |
| --- | --- | --- | --- |
| **[Docker Compose](#quick-start-docker)** | First run, demos, self-hosting, "just show me it works" | **Docker Desktop** (or Docker Engine + Compose v2) + Git | No |
| **[Local dev](#quick-start-local-dev)** | Contributing, debugging probes, iterating on UI | **Node.js 20+**, **Python 3.12+**, Git | Yes |

> **Why two paths?** Docker bundles Node and Python inside containers so you don't install them — but you **must** have Docker installed first. Local dev gives you `--reload` on the backend and `next dev` HMR on the frontend, which is what you want when changing code.

**API keys are optional for both paths.** Without keys, each provider shows `unknown` on the dashboard — the app still starts, probes still run where possible, and you can explore the UI. Add keys when you want live health data.

---

### Prerequisites

Read this **before** running any commands. Each path has different requirements.

#### Path A — Docker Compose

| Requirement | Minimum version | Why |
| --- | --- | --- |
| **Git** | any recent | Clone the repo |
| **Docker Engine** | 20.10+ | Builds and runs both containers |
| **Docker Compose v2** | bundled with Docker Desktop | Orchestrates `backend` + `frontend` (`docker compose`, not legacy `docker-compose`) |

**Verify Docker is installed and running** (do this first — many "it doesn't work" reports are just missing Docker):

```bash
docker --version          # e.g. Docker version 27.x
docker compose version    # e.g. Docker Compose version v2.x
docker info               # should NOT say "Cannot connect to the Docker daemon"
```

If `docker info` fails, install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (macOS/Windows) or [Docker Engine](https://docs.docker.com/engine/install/) (Linux), then start the daemon.

**Also check:** port **3000** must be free (frontend publishes it). Port 8000 stays internal to the compose network.

```bash
# macOS / Linux — should print nothing if free
lsof -i :3000
```

#### Path B — Local development

| Requirement | Minimum version | Why |
| --- | --- | --- |
| **Git** | any recent | Clone the repo |
| **Node.js** | **20+** | Frontend (`frontend/package.json`) |
| **npm** | 9+ (ships with Node 20) | Install frontend deps |
| **Python** | **3.12+** | Backend (matches `backend/Dockerfile`) |
| **pip + venv** | stdlib | Backend dependencies |

**Verify local toolchain:**

```bash
node --version    # v20.x or v22.x
npm --version     # 9.x or 10.x
python3 --version # 3.12.x or 3.13.x
```

**Optional (local dev only):**

| Tool | When you need it |
| --- | --- |
| **`playwright install chromium`** | Gemini official status via local headless browser (`GEMINI_STATUS_BROWSER=1`, the default in `backend/.env.example`) |
| **Provider API keys** | Live probe data instead of `unknown` |
| **Browserbase API key** | Downdetector corroboration (`DOWNDETECTOR_ENABLED=1`) |
| **`jq`** | Pretty-print JSON in the verify commands below |

**Also check:** ports **3000** (frontend) and **8000** (backend) must both be free when running locally.

---

### Quick start (Docker)

**Requires:** [Docker prerequisites](#path-a--docker-compose) verified above.

#### Step 1 — Clone and configure

```bash
git clone https://github.com/kaiiiichen/WatchTower-AI.git
cd WatchTower-AI
cp .env.example .env
```

Edit `.env` at the **repo root** — add any API keys you have (see [Configuration](#configuration)). Empty keys are fine for a first look.

#### Step 2 — Build and run

```bash
docker compose up --build
```

First build downloads base images and installs dependencies — expect a few minutes. Subsequent starts are faster.

#### Step 3 — Open the dashboard

[http://localhost:3000](http://localhost:3000)

The frontend container talks to the backend at `http://backend:8000` inside the compose network (set automatically — you don't configure this for Docker).

#### What the containers include

| Service | Image | Port | Role |
| --- | --- | --- | --- |
| `backend` | `python:3.12-slim` | 8000 (internal) | FastAPI probe engine |
| `frontend` | `node:20-alpine` | **3000** (published) | Next.js dashboard |

#### Docker-specific behavior (read before wondering "why is X broken?")

We made deliberate trade-offs in the Docker images. Knowing them upfront saves debugging time:

| Feature | In Docker | Workaround |
| --- | --- | --- |
| **Gemini official status (local Chromium)** | Does **not** work out of the box — slim image has no browser binaries | Set `GEMINI_STATUS_BROWSER=0` in `.env`, or use [local dev](#quick-start-local-dev) with `playwright install chromium` |
| **Downdetector** | Works via **Browserbase remote CDP** (no local browser needed) | Set `DOWNDETECTOR_ENABLED=1` + `BROWSERBASE_API_KEY` in `.env` |
| **Probe history (SQLite)** | Lives **inside** the backend container — lost on `docker compose down` unless you add a volume | Mount `./backend/data:/app/data` (see [Deployment notes](#deployment-notes)) |
| **Hot reload** | Not available | Use [local dev](#quick-start-local-dev) for code changes |

Stop containers: `Ctrl+C`, then optionally `docker compose down`.

---

### Quick start (local dev)

**Requires:** [Local dev prerequisites](#path-b--local-development) verified above.

Local dev runs **two processes in two terminals**. Start the backend first — the frontend proxies to it.

#### Terminal 1 — Backend (probe engine)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium   # optional — skip if GEMINI_STATUS_BROWSER=0
cp .env.example .env
# Edit backend/.env — add ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Wait until you see `probe cycle complete` in the logs — the first cycle may take 10–20 seconds while models are discovered.

#### Terminal 2 — Frontend (dashboard)

```bash
cd frontend
npm install
echo 'BACKEND_URL=http://localhost:8000' > .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

> **`BACKEND_URL` is required.** Without it, `/api/*` routes return **503** with `"Backend offline — set BACKEND_URL"`. The dashboard will not show live probe data.

Package-specific details: [backend/README.md](backend/README.md) · [frontend/README.md](frontend/README.md)

---

### Verify it works

Run these after either path. Expected: JSON with a `providers` array.

**Through the frontend proxy** (works for both Docker and local dev):

```bash
curl -s http://localhost:3000/api/health | jq .
```

**Direct to backend** (local dev only — port 8000 is not published in Docker):

```bash
curl -s http://localhost:8000/health | jq .
```

| What you see | Meaning |
| --- | --- |
| `providers` with `"status": "operational"` | API keys work, probes succeeded |
| `providers` with `"status": "unknown"` | Missing API key for that provider — expected if you skipped keys |
| HTTP **503** from `/api/health` | Frontend can't reach backend — check `BACKEND_URL`, backend logs, or that backend container is running |
| Empty page / connection refused on `:3000` | Frontend not running, or port 3000 taken by another app |

Other endpoints (same proxy pattern):

```bash
curl -s http://localhost:3000/api/diagnose | jq .
curl -s http://localhost:3000/api/backtest | jq .
```

---

### Configuration

WatchTower AI uses **different env files depending on how you run it**. This trips people up — here's why:

| How you run | Env file location | Template |
| --- | --- | --- |
| **Docker Compose** | `.env` at **repo root** | [`.env.example`](.env.example) |
| **Local backend** | `backend/.env` | [`backend/.env.example`](backend/.env.example) |
| **Local frontend** | `frontend/.env.local` | create manually (one variable) |

Docker Compose reads the root `.env` via `env_file` in [`docker-compose.yml`](docker-compose.yml) and injects `BACKEND_URL` / `CORS_ORIGINS` for you. Local dev needs you to set those yourself.

#### Root `.env` (Docker) — key variables

| Variable | Default | Description |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `GEMINI_API_KEY` | — | Google AI key |
| `DOWNDETECTOR_ENABLED` | `0` | Set `1` to enable Downdetector corroboration |
| `BROWSERBASE_API_KEY` | — | Required when Downdetector enabled |
| `DOWNDETECTOR_SUMMARY_MODEL` | `claude-3-5-haiku-latest` | Model for Downdetector comment summaries |
| `GEMINI_STATUS_BROWSER` | `1` | Set `0` in Docker unless you customize the image with Chromium |
| `SENTRY_DSN` | — | Sentry DSN (unset = disabled) |

#### `backend/.env` (local dev) — additional knobs

See [`backend/.env.example`](backend/.env.example) for the full list. Highlights:

| Variable | Default | Description |
| --- | --- | --- |
| `PROBE_INTERVAL` | `30` | Seconds between probe cycles |
| `PROBE_TIMEOUT` | `20` | Per-request timeout (seconds) |
| `GEMINI_STATUS_BROWSER` | `1` | Local headless Chromium for Gemini official status |
| `ENABLE_DOCS` | off | Set `1` for `/docs` and OpenAPI at `http://localhost:8000/docs` |
| `DEMO_FORCE_DOWN` | off | Demo flag — force one provider to `degraded` |

Model env vars (`ANTHROPIC_MODEL`, etc.) are **fallbacks only** when dynamic discovery fails.

#### `frontend/.env.local` (local dev)

| Variable | Description |
| --- | --- |
| `BACKEND_URL` | FastAPI base URL, e.g. `http://localhost:8000` |

---

### Troubleshooting

Common issues we anticipated when writing this README — if you're stuck, check here first.

#### Docker

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `docker: command not found` | Docker not installed | Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine, then re-open your terminal |
| `Cannot connect to the Docker daemon` | Docker installed but not running | Start Docker Desktop / `sudo systemctl start docker` |
| `docker-compose: command not found` | Using legacy v1 binary | Use `docker compose` (space, v2) — bundled with Docker Desktop |
| Port 3000 already allocated | Another app using 3000 | Stop the other app, or change the host port in `docker-compose.yml` (`"3001:3000"`) |
| Build fails on Apple Silicon | Rare base-image issues | Ensure Docker Desktop is updated; build uses standard `linux/amd64`-compatible images |
| Providers all `unknown` after adding keys | `.env` not at repo root, or container not restarted | Keys go in **root** `.env`; run `docker compose up --build` again after editing |
| Gemini official status empty | No Chromium in Docker image | Set `GEMINI_STATUS_BROWSER=0` in root `.env` and restart |
| History lost after restart | SQLite inside ephemeral container | Add a volume mount on `backend/data/` (see [Deployment notes](#deployment-notes)) |

#### Local dev

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Dashboard shows "Backend offline" | Missing or wrong `BACKEND_URL` | Create `frontend/.env.local` with `BACKEND_URL=http://localhost:8000`; restart `npm run dev` |
| `503` from `/api/health` | Backend not running or crashed | Check Terminal 1 — look for errors in uvicorn logs |
| `ModuleNotFoundError` | venv not activated / wrong Python | Use `.venv/bin/uvicorn` explicitly (as shown above) |
| All providers `unknown` | Keys in wrong file | Keys go in **`backend/.env`**, not the repo root `.env` |
| Playwright / Chromium errors | Browser not installed | Run `.venv/bin/playwright install chromium`, or set `GEMINI_STATUS_BROWSER=0` |
| Port 8000 in use | Another service on 8000 | `lsof -i :8000` and stop the conflicting process, or use `--port 8001` and update `BACKEND_URL` |

#### General

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Provider `rate_limited` | Your API quota / rate limit hit | Not a service outage — check provider billing/limits |
| Provider `misconfigured` | Invalid or expired API key | Rotate the key in your `.env` |
| `/backtest` returns 503 | VU dataset CSV missing | Ensure `backend/data/vu_dataset/` is present (bundled in repo) |
| CORS errors in browser | Wrong `CORS_ORIGINS` | Local dev: defaults allow `localhost:3000`; Docker sets this in compose |

---

### API reference

| Route | Description |
| --- | --- |
| `GET /health` | Live probe snapshot: providers, alerts, community signals |
| `GET /diagnose` | Local DNS/TCP/key checks + four-way verdict |
| `GET /backtest` | VU dataset detection-gap analysis (`503` if CSV missing) |

Frontend proxies: `GET /api/health`, `/api/diagnose`, `/api/backtest`.

**Provider status values:** `operational` · `degrading` · `degraded` · `down` · `unknown` · `rate_limited` · `misconfigured`

**Verdict kinds:** `your-side` · `account-side` · `service-side` · `all-clear` · `indeterminate`

Types shared in `frontend/src/lib/types.ts` and `backend/app/models.py`.

---

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser  →  localhost:3000                                     │
│    Next.js dashboard (theme, provider cards, alerts, backtest)  │
│    Polls /api/health every 30s                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ BACKEND_URL
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI probe engine (:8000)                                   │
│  Probe loop (30s) · Community hub (HN + Downdetector)           │
│  Official status (Statuspage + Gemini adapter) · SQLite history │
│  GET /health · GET /diagnose · GET /backtest · Sentry (optional)│
└─────────────────────────────────────────────────────────────────┘

Docker Compose runs both services; only port 3000 is published.
```

| Layer | Technology |
| --- | --- |
| Frontend | Next.js 16 (standalone) + React 19 + Tailwind CSS 4 |
| Backend | FastAPI + asyncio + httpx + Playwright (CDP) |
| Packaging | Docker Compose (`backend/Dockerfile`, `frontend/Dockerfile`) |
| Persistence | SQLite (stdlib `sqlite3`) |
| Observability | Sentry SDK (optional) |
| Research data | VU Amsterdam status-page dataset (bundled CSV) |

#### Detection gap & academic backing

**Paper:** *An Empirical Characterization of Outages and Incidents in Public Services for LLMs* — Xiaoyu Chu et al., VU Amsterdam, **ICPE '25**.

**Dataset:** [Zenodo 14018219](https://zenodo.org/records/14018219) · [GitHub atlarge-research/llm-service-analysis](https://github.com/atlarge-research/llm-service-analysis)

| Metric | Value |
| --- | --- |
| Incidents never marked "investigating" in real time | **29.7%** (161/542) |
| Median investigating → resolved | **73 min** (N=381) |
| Anthropic median investigating → resolved | **55.5 min** |

**What we claim:** Official status pages leave a blind window; high-frequency probing with QA checks can surface anomalies inside that window.

**What we do not claim:** Measured head-start over the status page on historical incidents.

#### Product philosophy

- **You run it** — keys and probe history stay on your machine.
- **Corroboration, not dependency** — HN, Downdetector, and official status upgrade alerts but never block core detection.
- **Honest numbers** — backtest metrics computed from CSV; estimates flagged.
- **Shippable** — Docker Compose for one-command deploy; local dev path for contributors.

---

### Project structure

```
WatchTower-AI/
├── README.md                 # You are here — start here
├── docker-compose.yml        # Orchestrates backend + frontend (Docker path)
├── .env.example              # Docker env template → copy to .env at repo root
├── LICENSE
├── CONTRIBUTING.md           # Contributor workflow + PR checks
├── CODE_OF_CONDUCT.md
├── SECURITY.md               # Responsible disclosure (don't paste keys in issues)
├── .github/
│   └── pull_request_template.md
│
├── backend/                  # FastAPI probe engine
│   ├── Dockerfile
│   ├── .env.example          # Local dev env template → copy to backend/.env
│   ├── requirements.txt
│   ├── README.md             # Probe semantics, model discovery, tests
│   ├── app/
│   │   ├── main.py           # FastAPI app, background loops, HTTP routes
│   │   ├── probes.py         # Per-provider adapters, scoring, probe_all
│   │   ├── diagnostics.py    # Local DNS/TCP/key checks + verdict
│   │   ├── models.py         # Pydantic models (mirrors frontend types)
│   │   ├── config.py         # Env-based configuration
│   │   ├── store.py          # SQLite probe history
│   │   ├── backtest.py       # VU dataset analysis
│   │   ├── community_hub.py  # HN + Downdetector orchestration
│   │   ├── community.py      # Hacker News Algolia signals
│   │   ├── community_downdetector.py
│   │   ├── official_status.py
│   │   ├── gemini_status_browser.py  # Optional headless Chromium adapter
│   │   ├── monitoring.py     # Sentry integration
│   │   └── redaction.py      # API key scrubbing
│   ├── data/
│   │   ├── vu_dataset/       # Bundled research CSV (committed)
│   │   └── watchtower.db     # Runtime SQLite (gitignored, created on first run)
│   └── tests/                # pytest + offline discovery tests
│
└── frontend/                 # Next.js 16 dashboard
    ├── Dockerfile
    ├── package.json
    ├── README.md             # Proxy routes, components, scripts
    ├── AGENTS.md             # Next.js 16 notes for AI coding agents
    ├── next.config.ts
    └── src/
        ├── app/
        │   ├── page.tsx      # Dashboard entry
        │   ├── layout.tsx
        │   └── api/          # Proxy routes → backend
        │       ├── health/route.ts
        │       ├── diagnose/route.ts
        │       └── backtest/route.ts
        ├── components/       # ProviderCard, AlertBanner, DetectionGap, …
        └── lib/
            ├── types.ts      # Shared JSON contract with backend
            └── backend.ts    # BACKEND_URL resolution + offline responses
```

**Shared contract:** `frontend/src/lib/types.ts` ↔ `backend/app/models.py` — keep these aligned when changing API responses.

---

### Testing

**Backend** (`backend/`):

```bash
cd backend
PYTHONPATH=. .venv/bin/python tests/test_discovery.py
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q   # requires: pip install pytest
```

**Frontend** (`frontend/`):

```bash
cd frontend
npm run lint      # ESLint + semantic color checks
npm run build     # Production build smoke test
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full pre-PR checklist.

---

### Deployment notes

| Path | When to use | Notes |
| --- | --- | --- |
| **Docker Compose** | Quick deploy, demos, self-hosting | `docker compose up --build` — see [Quick start (Docker)](#quick-start-docker) |
| **Vercel + PaaS** | Split frontend/backend | Set `BACKEND_URL` on Vercel; run backend on Railway, Fly.io, etc. |
| **Local dev** | Contributing | Hot reload — see [Quick start (local dev)](#quick-start-local-dev) |

| Concern | Guidance |
| --- | --- |
| Secrets | Env vars only — never commit `.env` / `.env.local` |
| SQLite persistence | Add to `docker-compose.yml` under `backend`: `volumes: ["./backend/data:/app/data"]` — adjust `ProbeHistoryStore` path if needed |
| Outbound network | Backend needs HTTPS to provider APIs (+ Browserbase if Downdetector enabled) |
| Gemini browser in prod | Prefer `GEMINI_STATUS_BROWSER=0` in containerized deploys unless you build a custom image with Chromium |

---

### Documentation map

| File | Contents |
| --- | --- |
| **README.md** | This file — idea, paths, prerequisites, troubleshooting |
| [backend/README.md](backend/README.md) | Probe engine, model discovery, tests |
| [frontend/README.md](frontend/README.md) | Dashboard setup, proxy routes, components |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute, PR checks |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards |
| [SECURITY.md](SECURITY.md) | Responsible disclosure |
| [frontend/AGENTS.md](frontend/AGENTS.md) | AI agent / Next.js 16 notes |
| [backend/.env.example](backend/.env.example) | Backend env var names (local dev) |
| [.env.example](.env.example) | Docker Compose env var names |

---

### License

**GNU General Public License v3.0** — see [LICENSE](LICENSE). Report vulnerabilities via [SECURITY.md](SECURITY.md).

API keys and local `watchtower.db` are yours — do not commit them.

↑ English · [中文 →](#中文)

---

## 中文

→ [English](#english)

### 目录

1. [理念](#理念)
2. [UC Berkeley AI Hackathon 2026](#uc-berkeley-ai-hackathon-2026-1)
3. [功能概览](#功能概览)
4. [快速开始 — 选择路径](#快速开始--选择路径)
5. [环境要求](#环境要求)
6. [快速开始（Docker）](#快速开始docker)
7. [快速开始（本地开发）](#快速开始本地开发)
8. [验证是否正常运行](#验证是否正常运行)
9. [配置](#配置)
10. [常见问题](#常见问题)
11. [部署说明](#部署说明)
12. [项目结构](#项目结构)
13. [文档索引](#文档索引)

### 理念

**WatchTower AI** 是 AI 服务的**航班雷达** —— 在官方状态页更新之前发现 Claude / GPT / Gemini 的故障，并回答那个让你凌晨两点睡不着的问题：*是服务商挂了，还是我自己的问题？*

官方状态页慢、不全，也不会告诉你**你的环境**是否正常。WatchTower AI 用持续独立探测、超越「HTTP 200」的 QA 检查、本地环境诊断，以及关于官方页面滞后于真实影响的诚实数据来填补这一空白。

这是一款**本地开发者工具**：在你自己的机器上运行，API 密钥归你所有，探测历史保存在本地 SQLite 文件中 —— 不会上传到共享云服务。

### UC Berkeley AI Hackathon 2026

本项目在 **[UC Berkeley AI Hackathon 2026](https://ai-hackathon-2026.devpost.com/)**（2026 年 6 月 20–21 日）期间由 **Kai Chen**（[@kaiiiichen](https://github.com/kaiiiichen)）以**个人项目**完成。

#### 电梯演讲（Devpost 用）

> WatchTower AI 是 Claude、GPT、Gemini 的本地航班雷达 —— 每 30 秒用真实 QA 检查探测各提供商，诊断故障是在你这边还是他们那边，并用同行评审的故障研究数据支撑「检测空白」论点。凌晨两点出问题时，你可以在几秒内得到诚实答案，而不必刷新仍显示「一切正常」的状态页。

### 功能概览

| 层级 | 能力 |
| --- | --- |
| **探测层** | 30 秒并发探测、动态模型发现、QA 探针、健康评分、前兆 `degrading` 预警 |
| **归因层** | 四方裁决（你的环境 / 账户 / 服务 / 一切正常）、本地 DNS/TCP/密钥检查、HN + Downdetector 社区佐证、官方状态页 |
| **研究层** | VU Amsterdam 数据集回测 —— 29.7% 事件从未实时标记为 investigating |
| **可观测性** | Sentry 三层集成（事件、指纹分组、性能追踪）+ API 密钥脱敏 |
| **持久化** | SQLite 探测历史、Next.js API 代理（后端离线时明确提示） |
| **部署** | Docker Compose 一键打包前后端 |

---

### 快速开始 — 选择路径

本项目是 **monorepo**，包含 FastAPI 后端（`backend/`）和 Next.js 前端（`frontend/`）。两种运行方式：

| 路径 | 适合场景 | 本机需要 | 热重载 |
| --- | --- | --- | --- |
| **[Docker Compose](#快速开始docker)** | 首次体验、演示、自托管 | **Docker Desktop**（或 Docker Engine + Compose v2）+ Git | 否 |
| **[本地开发](#快速开始本地开发)** | 贡献代码、调试探针、改 UI | **Node.js 20+**、**Python 3.12+**、Git | 是 |

> **为什么两条路径？** Docker 把 Node 和 Python 打包进容器，你不需要单独安装 —— 但**必须先安装 Docker**。本地开发提供后端 `--reload` 和前端 HMR，适合改代码。

**API 密钥对两条路径都是可选的。** 没有密钥时，各提供商显示 `unknown`，应用仍可启动，你可以先浏览 UI。

---

### 环境要求

**运行任何命令之前**先读这一节。两条路径的要求不同。

#### 路径 A — Docker Compose

| 依赖 | 最低版本 | 用途 |
| --- | --- | --- |
| **Git** | 任意较新版本 | 克隆仓库 |
| **Docker Engine** | 20.10+ | 构建并运行容器 |
| **Docker Compose v2** | 随 Docker Desktop 附带 | 编排前后端（命令是 `docker compose`，不是旧版 `docker-compose`） |

**先验证 Docker 已安装且正在运行**（很多「跑不起来」其实是没装 Docker）：

```bash
docker --version
docker compose version
docker info    # 不应出现 "Cannot connect to the Docker daemon"
```

若 `docker info` 失败，请安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 并启动。

端口 **3000** 必须空闲（前端对外暴露）。8000 仅在 compose 内网使用。

#### 路径 B — 本地开发

| 依赖 | 最低版本 | 用途 |
| --- | --- | --- |
| **Git** | 任意较新版本 | 克隆仓库 |
| **Node.js** | **20+** | 前端 |
| **npm** | 9+ | 安装前端依赖 |
| **Python** | **3.12+** | 后端 |

```bash
node --version    # v20.x 或 v22.x
python3 --version # 3.12.x 或 3.13.x
```

**可选：** `playwright install chromium`（Gemini 官方状态页本地浏览器）、提供商 API 密钥、`jq`（格式化 JSON）。

端口 **3000** 和 **8000** 均需空闲。

---

### 快速开始（Docker）

**前提：** 上方 [Docker 环境要求](#路径-a--docker-compose) 已验证通过。

```bash
git clone https://github.com/kaiiiichen/WatchTower-AI.git
cd WatchTower-AI
cp .env.example .env
# 编辑 .env，填入你有的 API 密钥（也可以先留空）
docker compose up --build
```

打开 [http://localhost:3000](http://localhost:3000)。

#### Docker 特有说明（避免踩坑）

| 功能 | Docker 中 | 处理方式 |
| --- | --- | --- |
| Gemini 官方状态（本地 Chromium） | 默认**不可用**（镜像无浏览器） | 在 `.env` 中设 `GEMINI_STATUS_BROWSER=0`，或用本地开发 + `playwright install chromium` |
| Downdetector | 通过 **Browserbase 远程 CDP**（无需本地浏览器） | `DOWNDETECTOR_ENABLED=1` + `BROWSERBASE_API_KEY` |
| SQLite 历史 | 存在容器内，`docker compose down` 后丢失 | 挂载 `./backend/data` 卷（见[部署说明](#部署说明)） |

停止：`Ctrl+C`，可选 `docker compose down`。

---

### 快速开始（本地开发）

**前提：** 上方 [本地开发环境要求](#路径-b--本地开发) 已验证通过。

需要**两个终端**，先启动后端。

**终端 1 — 后端：**

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium   # 可选
cp .env.example .env
# 编辑 backend/.env，填入密钥
.venv/bin/uvicorn app.main:app --reload --port 8000
```

**终端 2 — 前端：**

```bash
cd frontend
npm install
echo 'BACKEND_URL=http://localhost:8000' > .env.local
npm run dev
```

打开 [http://localhost:3000](http://localhost:3000)。

> 未设置 `BACKEND_URL` 时，`/api/*` 返回 **503**「Backend offline」。仪表盘不会显示实时探测数据。

---

### 验证是否正常运行

```bash
curl -s http://localhost:3000/api/health | jq .
```

| 现象 | 含义 |
| --- | --- |
| `providers` 中 `"status": "operational"` | 密钥有效，探测成功 |
| `"status": "unknown"` | 该提供商缺少 API 密钥 —— 预期行为 |
| HTTP **503** | 前端连不上后端 —— 检查 `BACKEND_URL` 或后端日志 |
| `:3000` 连接被拒绝 | 前端未启动，或 3000 端口被占用 |

本地开发还可直接访问后端：

```bash
curl -s http://localhost:8000/health | jq .
```

---

### 配置

| 运行方式 | 环境文件位置 | 模板 |
| --- | --- | --- |
| **Docker Compose** | 仓库根目录 `.env` | [`.env.example`](.env.example) |
| **本地后端** | `backend/.env` | [`backend/.env.example`](backend/.env.example) |
| **本地前端** | `frontend/.env.local` | 手动创建（一个变量） |

Docker 通过 [`docker-compose.yml`](docker-compose.yml) 自动注入 `BACKEND_URL` 和 `CORS_ORIGINS`。本地开发需自行设置。

根目录 `.env` 主要变量：`ANTHROPIC_API_KEY`、`OPENAI_API_KEY`、`GEMINI_API_KEY`、`DOWNDETECTOR_ENABLED`、`BROWSERBASE_API_KEY`、`GEMINI_STATUS_BROWSER`（Docker 建议设 `0`）、`SENTRY_DSN`。

本地后端更多选项见 [`backend/.env.example`](backend/.env.example)（`PROBE_INTERVAL`、`ENABLE_DOCS` 等）。

---

### 常见问题

#### Docker

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `docker: command not found` | 未安装 Docker | 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/) |
| `Cannot connect to the Docker daemon` | Docker 未启动 | 启动 Docker Desktop |
| 端口 3000 被占用 | 其他程序占用 | 停止冲突程序，或改 `docker-compose.yml` 端口映射 |
| 加了密钥仍全部 `unknown` | `.env` 位置错误或容器未重启 | 密钥放在**仓库根目录** `.env`；重新 `docker compose up --build` |

#### 本地开发

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 仪表盘显示 Backend offline | 缺少 `BACKEND_URL` | 创建 `frontend/.env.local` |
| 全部 `unknown` | 密钥放错文件 | 密钥放在 **`backend/.env`**，不是根目录 `.env` |
| Playwright 报错 | 未安装 Chromium | `playwright install chromium` 或设 `GEMINI_STATUS_BROWSER=0` |

---

### 部署说明

| 方式 | 适用场景 |
| --- | --- |
| **Docker Compose** | 快速部署、演示、自托管 |
| **Vercel + PaaS** | 前后端分离部署 |
| **本地开发** | 贡献代码、热重载 |

密钥仅通过环境变量注入，切勿提交 `.env`。生产 Docker 建议挂载 `backend/data/` 卷以保留 SQLite 历史。

---

### 项目结构

```
WatchTower-AI/
├── README.md              # 从这里开始
├── docker-compose.yml     # Docker 编排
├── .env.example           # Docker 环境模板
├── backend/               # FastAPI 探针引擎
│   ├── app/               # main.py, probes.py, diagnostics.py, …
│   ├── data/              # vu_dataset/（已提交）, watchtower.db（运行时生成）
│   └── tests/
└── frontend/              # Next.js 16 仪表盘
    └── src/
        ├── app/api/       # 代理路由 → 后端
        ├── components/
        └── lib/types.ts   # 与 backend/app/models.py 对齐
```

详见英文版 [Project structure](#project-structure) 完整目录树。

---

### 文档索引

| 文件 | 内容 |
| --- | --- |
| **README.md** | 本文件 —— 路径选择、环境要求、排错 |
| [backend/README.md](backend/README.md) | 后端详情 |
| [frontend/README.md](frontend/README.md) | 前端详情 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 |
| [SECURITY.md](SECURITY.md) | 安全披露 |
| [.env.example](.env.example) | Docker 环境变量 |
| [backend/.env.example](backend/.env.example) | 本地后端环境变量 |

---

### 许可证

**GNU General Public License v3.0** —— 见 [LICENSE](LICENSE)。

→ [English](#english) · ↑ 中文

---

WatchTower AI — *is it the service, or is it me?*
