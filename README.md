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
4. [Technical reference](#technical-reference)
   - [Requirements](#requirements)
   - [Quick start (Docker)](#quick-start-docker)
   - [Quick start (local dev)](#quick-start-local-dev)
   - [Configuration](#configuration)
   - [API reference](#api-reference)
   - [Architecture](#architecture)
   - [Detection gap & academic backing](#detection-gap--academic-backing)
   - [Product philosophy](#product-philosophy)
   - [Project structure](#project-structure)
   - [Testing](#testing)
   - [Deployment notes](#deployment-notes)
   - [Documentation map](#documentation-map)
   - [License](#license)

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

### Technical reference

#### Requirements

**Docker (recommended for deployment)**

| Tool | Version / notes |
| --- | --- |
| **Docker** | Docker Engine + Docker Compose v2 |
| **API keys** | Optional — missing keys show provider as `unknown` |

**Local development**

| Tool | Version / notes |
| --- | --- |
| **Node.js** | **20+** (frontend) |
| **Python** | **3.12+** (backend; Docker image uses 3.12-slim) |
| **API keys** | Optional — missing keys show provider as `unknown` |

#### Quick start (Docker)

The fastest way to run WatchTower AI — no Node or Python install on the host.

```bash
git clone https://github.com/kaiiiichen/WatchTower-AI.git
cd WatchTower-AI
cp .env.example .env
# Edit .env — fill in the API keys you have (see Configuration below)
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000). The frontend container proxies to the backend at `http://backend:8000` inside the compose network.

Verify:

```bash
curl http://localhost:3000/api/health | jq .
```

**What the images include**

| Service | Image | Notes |
| --- | --- | --- |
| `backend` | `python:3.12-slim` | FastAPI on port 8000 (internal only) |
| `frontend` | `node:20-alpine` | Next.js standalone on port **3000** (published) |

- Playwright is installed as a Python package but **local browsers are not bundled** — Downdetector connects to remote Browserbase sessions over CDP.
- Gemini official status uses local Chromium when `GEMINI_STATUS_BROWSER=1` (the default) — that path **does not work in the stock Docker image** (no `playwright install`). Set `GEMINI_STATUS_BROWSER=0` in `.env` to skip it, or use local dev with Chromium installed.
- Probe history SQLite lives inside the backend container unless you add a volume on `backend/data/`.

Stop: `docker compose down`

#### Quick start (local dev)

For hacking on the codebase with hot reload:

**Backend** (probe engine):

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium   # optional — Gemini official status (local headless)
cp .env.example .env
# Edit .env — ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY
.venv/bin/uvicorn app.main:app --reload --port 8000
```

**Frontend** (dashboard):

```bash
cd frontend
npm install
echo 'BACKEND_URL=http://localhost:8000' > .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Verify:

```bash
curl http://localhost:8000/health | jq .
curl http://localhost:3000/api/health | jq .
```

`BACKEND_URL` is **required** for live data — without it, API routes return `503` with an offline message.

See [backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md) for package-specific details.

#### Configuration

**Docker** — copy [`.env.example`](.env.example) to `.env` at the **repo root** (used by `docker compose`):

| Variable | Default | Description |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `GEMINI_API_KEY` | — | Google AI key |
| `DOWNDETECTOR_ENABLED` | `0` | Set `1` to enable Downdetector corroboration |
| `BROWSERBASE_API_KEY` | — | Browserbase API key (required when Downdetector enabled) |
| `DOWNDETECTOR_SUMMARY_MODEL` | `claude-3-5-haiku-latest` | Model for Downdetector comment summaries |
| `SENTRY_DSN` | — | Sentry DSN (unset = disabled) |

`BACKEND_URL` and `CORS_ORIGINS` are set automatically in [`docker-compose.yml`](docker-compose.yml).

**Local dev — backend** (`backend/.env`) — copy from [backend/.env.example](backend/.env.example):

| Variable | Default | Description |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `GEMINI_API_KEY` | — | Google AI key (alias: `GOOGLE_API_KEY`) |
| `PROBE_INTERVAL` | `30` | Seconds between probe cycles |
| `PROBE_TIMEOUT` | `20` | Per-request timeout (seconds) |
| `DOWNDETECTOR_ENABLED` | off | Downdetector via Browserbase CDP |
| `BROWSERBASE_API_KEY` | — | Browserbase API key |
| `DOWNDETECTOR_SUMMARY_MODEL` | `claude-3-5-haiku-latest` | Summary model for Downdetector |
| `SENTRY_DSN` | — | Sentry DSN (unset = disabled) |
| `GEMINI_STATUS_BROWSER` | `1` | Local headless Chromium for Gemini official status |
| `ENABLE_DOCS` | off | Set `1` for `/docs` and OpenAPI |

Model env vars (`ANTHROPIC_MODEL`, etc.) are **fallbacks only** when dynamic discovery fails.

**Local dev — frontend** (`frontend/.env.local`):

| Variable | Description |
| --- | --- |
| `BACKEND_URL` | FastAPI base URL, e.g. `http://localhost:8000` |

#### API reference

| Route | Description |
| --- | --- |
| `GET /health` | Live probe snapshot: providers, alerts, community signals |
| `GET /diagnose` | Local DNS/TCP/key checks + four-way verdict |
| `GET /backtest` | VU dataset detection-gap analysis (`503` if CSV missing) |

Frontend proxies: `GET /api/health`, `/api/diagnose`, `/api/backtest`.

**Provider status values:** `operational` · `degrading` · `degraded` · `down` · `unknown` · `rate_limited` · `misconfigured`

**Verdict kinds:** `your-side` · `account-side` · `service-side` · `all-clear` · `indeterminate`

Types shared in `frontend/src/lib/types.ts` and `backend/app/models.py`.

#### Architecture

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

#### Project structure

```
WatchTower-AI/
├── README.md
├── docker-compose.yml
├── .env.example              # Docker runtime env (copy to .env)
├── LICENSE · CONTRIBUTING.md · CODE_OF_CONDUCT.md · SECURITY.md
├── backend/
│   ├── Dockerfile
│   ├── .env.example          # Local dev env
│   ├── app/                  # main.py, probes.py, community_hub.py, …
│   ├── data/                 # vu_dataset/ (bundled), watchtower.db (local, gitignored)
│   └── tests/
└── frontend/
    ├── Dockerfile
    └── src/                  # app/, components/, lib/
```

#### Testing

**Backend** (`backend/`):

```bash
PYTHONPATH=. .venv/bin/python tests/test_discovery.py
PYTHONPATH=. .venv/bin/python -m pytest tests/ -q   # requires: pip install pytest
```

**Frontend** (`frontend/`):

```bash
npm run lint
npm run build
```

#### Deployment notes

| Path | When to use | Notes |
| --- | --- | --- |
| **Docker Compose** | Quick deploy, demos, self-hosting | `docker compose up --build` — see [Quick start (Docker)](#quick-start-docker) |
| **Vercel + PaaS** | Split frontend/backend | Set `BACKEND_URL` on Vercel; run backend on Railway, Fly.io, etc. |
| **Local dev** | Contributing | Hot reload — see [Quick start (local dev)](#quick-start-local-dev) |

| Concern | Guidance |
| --- | --- |
| Secrets | Env vars only — never commit `.env` |
| SQLite persistence | Mount `backend/data/` as a volume in production Docker |
| Outbound network | Backend needs HTTPS to provider APIs (+ Browserbase if Downdetector enabled) |

#### Documentation map

| File | Contents |
| --- | --- |
| **README.md** | This file — idea, hackathon, technical reference |
| [backend/README.md](backend/README.md) | Probe engine, model discovery, tests |
| [frontend/README.md](frontend/README.md) | Dashboard setup, proxy routes, components |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards |
| [SECURITY.md](SECURITY.md) | Responsible disclosure |
| [frontend/AGENTS.md](frontend/AGENTS.md) | AI agent / Next.js 16 notes |
| [backend/.env.example](backend/.env.example) | Backend env var names (local dev) |
| [.env.example](.env.example) | Docker Compose env var names |

#### License

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
4. [技术参考](#技术参考-1)
   - [环境要求](#环境要求)
   - [快速开始（Docker）](#快速开始docker)
   - [快速开始（本地开发）](#快速开始本地开发)
   - [配置](#配置)
   - [部署说明](#部署说明)

### 理念

**WatchTower AI** 是 AI 服务的**航班雷达** —— 在官方状态页更新之前发现 Claude / GPT / Gemini 的故障，并回答那个让你凌晨两点睡不着的问题：*是服务商挂了，还是我自己的问题？*

官方状态页慢、不全，也不会告诉你**你的环境**是否正常。WatchTower AI 用持续独立探测、超越「HTTP 200」的 QA 检查、本地环境诊断，以及关于官方页面滞后于真实影响的诚实数据来填补这一空白。

这是一款**本地开发者工具**：在你自己的机器上运行，API 密钥归你所有，探测历史保存在本地 SQLite 文件中 —— 不会上传到共享云服务。

### UC Berkeley AI Hackathon 2026

本项目在 **[UC Berkeley AI Hackathon 2026](https://ai-hackathon-2026.devpost.com/)**（2026 年 6 月 20–21 日）期间由 **Kai Chen**（[@kaiiiichen](https://github.com/kaiiiichen)）以**个人项目**完成。所有实现均在黑客松窗口内完成。

#### 电梯演讲（Devpost 用）

> WatchTower AI 是 Claude、GPT、Gemini 的本地航班雷达 —— 每 30 秒用真实 QA 检查探测各提供商，诊断故障是在你这边还是他们那边，并用同行评审的故障研究数据支撑「检测空白」论点。凌晨两点出问题时，你可以在几秒内得到诚实答案，而不必刷新仍显示「一切正常」的状态页。

#### Devpost 提交清单

| 要求 | 位置 |
| --- | --- |
| 2–3 句摘要 | 使用上方电梯演讲 |
| 项目截图 | 仪表盘截图 |
| GitHub 仓库链接 | https://github.com/kaiiiichen/WatchTower-AI |
| 队名与桌号 | 在 [Devpost](https://ai-hackathon-2026.devpost.com/) 填写 |
| 演示 | 实时仪表盘 + `GET /health` JSON |

### 功能概览

| 层级 | 能力 |
| --- | --- |
| **探测层** | 30 秒并发探测、动态模型发现、QA 探针、健康评分、前兆 `degrading` 预警 |
| **归因层** | 四方裁决（你的环境 / 账户 / 服务 / 一切正常）、本地 DNS/TCP/密钥检查、HN + Downdetector 社区佐证、官方状态页 |
| **研究层** | VU Amsterdam 数据集回测 —— 29.7% 事件从未实时标记为 investigating |
| **可观测性** | Sentry 三层集成（事件、指纹分组、性能追踪）+ API 密钥脱敏 |
| **持久化** | SQLite 探测历史、Next.js API 代理（后端离线时明确提示） |
| **部署** | Docker Compose 一键打包前后端 |

### 技术参考

#### 环境要求

**Docker（推荐，用于部署）**

| 工具 | 说明 |
| --- | --- |
| Docker | Docker Engine + Docker Compose v2 |
| API 密钥 | 可选 —— 缺失则对应提供商显示 `unknown` |

**本地开发**

| 工具 | 版本 |
| --- | --- |
| Node.js | 20+ |
| Python | 3.12+ |
| API 密钥 | 可选 |

#### 快速开始（Docker）

无需在宿主机安装 Node 或 Python：

```bash
git clone https://github.com/kaiiiichen/WatchTower-AI.git
cd WatchTower-AI
cp .env.example .env
# 编辑 .env，填入 API 密钥
docker compose up --build
```

打开 [http://localhost:3000](http://localhost:3000)。前端容器通过 compose 内网访问 `http://backend:8000`。

```bash
curl http://localhost:3000/api/health | jq .
```

停止：`docker compose down`

**说明：** 镜像内不 bundled 本地浏览器；Downdetector 通过 Browserbase 远程 CDP 连接。SQLite 历史默认存在容器内，生产环境建议挂载 `backend/data/` 卷。

#### 快速开始（本地开发）

```bash
# 后端
cd backend && python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium   # 可选 —— Gemini 官方状态页
cp .env.example .env   # 填入密钥
.venv/bin/uvicorn app.main:app --reload --port 8000

# 前端
cd frontend && npm install
echo 'BACKEND_URL=http://localhost:8000' > .env.local
npm run dev
```

打开 [http://localhost:3000](http://localhost:3000)。未设置 `BACKEND_URL` 时 API 返回 `503` 离线提示。

#### 配置

**Docker** —— 复制根目录 [`.env.example`](.env.example) 为 `.env`：

| 变量 | 说明 |
| --- | --- |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | 提供商 API 密钥 |
| `DOWNDETECTOR_ENABLED` | `1` 启用 Downdetector 佐证 |
| `BROWSERBASE_API_KEY` | Browserbase 密钥（启用 Downdetector 时需要） |
| `DOWNDETECTOR_SUMMARY_MODEL` | Downdetector 评论摘要模型 |
| `SENTRY_DSN` | Sentry DSN（可选） |

`BACKEND_URL` 与 `CORS_ORIGINS` 已在 [`docker-compose.yml`](docker-compose.yml) 中自动配置。

**本地开发** —— 后端见 [backend/.env.example](backend/.env.example)，前端设置 `BACKEND_URL=http://localhost:8000`。

#### 部署说明

| 方式 | 适用场景 |
| --- | --- |
| **Docker Compose** | 快速部署、演示、自托管 |
| **Vercel + PaaS** | 前后端分离部署 |
| **本地开发** | 贡献代码、热重载 |

密钥仅通过环境变量注入，切勿提交 `.env`。

#### 文档索引

| 文件 | 内容 |
| --- | --- |
| **README.md** | 本文件 —— 理念、Docker 部署、技术参考 |
| [.env.example](.env.example) | Docker Compose 环境变量 |
| [docker-compose.yml](docker-compose.yml) | 前后端容器编排 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | 行为准则 |
| [SECURITY.md](SECURITY.md) | 安全披露 |
| [backend/README.md](backend/README.md) | 后端详情 |
| [frontend/README.md](frontend/README.md) | 前端详情 |

#### 许可证

**GNU General Public License v3.0** —— 见 [LICENSE](LICENSE)。漏洞报告见 [SECURITY.md](SECURITY.md)。

→ [English](#english) · ↑ 中文

---

WatchTower AI — *is it the service, or is it me?*
