# Contributing to WatchTower AI

Thank you for your interest. WatchTower AI was built for the
[UC Berkeley AI Hackathon 2026](https://ai-hackathon-2026.devpost.com/) and is
maintained as an open-source project. **Bug fixes**, **documentation
improvements**, and **small, focused enhancements** are welcome.

Before you contribute:

1. Read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
2. Read [SECURITY.md](SECURITY.md) — **never** file public issues with exploit
   details or real API keys.
3. Skim the [README](README.md) for architecture, quick start, and environment
   variables.

---

## Who this guide is for

| Audience | Also read |
| --- | --- |
| Human contributors | This file + [README](README.md) |
| AI coding agents (Cursor, Claude Code, etc.) | [frontend/AGENTS.md](frontend/AGENTS.md) — Next.js 16 conventions |

Maintainers use **pull requests to `main`**; direct pushes to `main` are
discouraged even when permissions allow.

---

## Prerequisites

| Component | Requirement |
| --- | --- |
| **Frontend** | Node.js **20+**, npm 9+ (`package-lock.json` in `frontend/`) |
| **Backend** | Python **3.11+**, `venv` recommended |
| **Optional** | Provider API keys (Anthropic, OpenAI, Gemini) for live probing |
| **Optional** | Playwright Chromium (`playwright install chromium`) for Gemini official-status browser adapter |

---

## Clone and install

```bash
git clone https://github.com/kaiiiichen/WatchTower-AI.git
cd WatchTower-AI
```

### Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium   # only if using Gemini status browser
cp .env.example .env
# Edit .env — add keys you have; missing keys -> provider reported as "unknown"
.venv/bin/uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
echo 'BACKEND_URL=http://localhost:8000' > .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Without `BACKEND_URL`, the
dashboard serves **mock data** for UI-only work.

**Never commit** `.env`, `.env.local`, API keys, or `backend/data/watchtower.db`.

---

## Mandatory checks (before a PR)

Run the same checks you would expect in CI:

**Frontend** (`frontend/`):

```bash
npm run lint
npm run build
```

**Backend** (`backend/`):

```bash
PYTHONPATH=. .venv/bin/python tests/test_discovery.py
# Full suite (requires pytest: pip install pytest)
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q
```

**Both services connected** (manual smoke test):

```bash
curl http://localhost:8000/health | jq .
curl http://localhost:3000/api/health | jq .
```

---

## Branch and pull request workflow

1. Branch from up-to-date `main`:

   ```bash
   git checkout main && git pull --ff-only
   git checkout -b <type>/<short-description>
   ```

   Prefix examples: `fix/`, `feat/`, `chore/`, `docs/`, `refactor/`.

2. Commit with clear messages (conventional style is appreciated: `type: summary`).

3. Push and open a PR against **`main`**. GitHub will suggest the
   [pull request template](.github/pull_request_template.md).

4. Describe **what** changed and **why**. Link issues with `Fixes #123` when
   applicable.

5. Update **[README.md](README.md)** and/or **`backend/.env.example`** /
   **`frontend/.env.local` documentation** if you change user-visible behavior,
   API routes, or required/optional environment variables.

---

## Project conventions

### Monorepo layout

- **`backend/`** — FastAPI probe engine, SQLite history, VU dataset backtest,
  community signals, Sentry integration.
- **`frontend/`** — Next.js 16 dashboard; `/api/*` routes proxy the backend.
- **Shared contract** — `frontend/src/lib/types.ts` mirrors `backend/app/models.py`
  JSON shapes. Keep them aligned when changing API responses.

### Stack

- **Frontend:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4.
- **Backend:** FastAPI, asyncio, httpx, stdlib `sqlite3`.
- **Tests:** Backend unit tests in `backend/tests/`; frontend semantic-color lint
  via `npm run lint:colors`.

### Style

- Match existing naming, component patterns, and Tailwind usage in each package.
- Prefer **small, reviewable diffs** over large refactors unless discussed in an
  issue first.
- **Dark mode:** new UI should work in light and dark (see `theme-provider.tsx`
  and `semantic-colors.ts`).

### Secrets and config

- Add **variable names** (and short comments) to `backend/.env.example` when
  introducing new backend configuration — never real secrets.
- Document frontend env vars in [frontend/README.md](frontend/README.md) and
  the root README when they change.

### Probe semantics

When touching `backend/app/probes.py` or diagnostics:

- Distinguish **service faults** (`down`, `degraded`) from **account/config
  faults** (`rate_limited`, `misconfigured`).
- Missing API keys must remain **`unknown`**, never crash the probe loop.
- Do not claim measured lead-time over official status pages without historical
  probe data — see README "Detection gap" section.

---

## Issues

Open a GitHub Issue for bugs and feature requests. For **security issues**, follow
[SECURITY.md](SECURITY.md) instead of posting exploit details in public issues.

---

## Questions

For small questions, open a GitHub Issue. This is a hackathon-born side project;
response time may vary.
