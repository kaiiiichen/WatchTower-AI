"""FastAPI app: background probe loop + GET /health returning a snapshot whose
JSON matches frontend/src/lib/types.ts exactly."""
import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import backtest, config, diagnostics
from .community import CommunityState
from .models import BacktestReport, HealthSnapshot, LocalDiagnosis
from .monitoring import init_sentry
from .probes import ProbeState, build_targets, probe_all
from .store import ProbeHistoryStore

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("watchtower")

# httpx logs every request URL at INFO ("HTTP Request: GET https://...?key=...").
# Gemini passes its API key as a query param, so that line leaks the secret —
# raise httpx (and its transport, httpcore) to WARNING to suppress it entirely.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def _probe_loop(app: FastAPI) -> None:
    client: httpx.AsyncClient = app.state.client
    state: ProbeState = app.state.probe_state
    loop = asyncio.get_running_loop()
    while True:
        cycle_start = loop.time()
        try:
            await probe_all(client, state, app.state.targets)
            log.info("probe cycle complete: %s", state.updated_at)
        except Exception:  # never let the loop die
            log.exception("probe cycle failed")
        elapsed = loop.time() - cycle_start
        await asyncio.sleep(max(0, config.PROBE_INTERVAL - elapsed))


async def _community_loop(app: FastAPI) -> None:
    """Refresh Reddit community signals on their own cadence, fully decoupled
    from probing. Corroboration only: any failure is swallowed here so it can
    never touch the probe loop or the /health snapshot."""
    client: httpx.AsyncClient = app.state.client
    community: CommunityState = app.state.community
    loop = asyncio.get_running_loop()
    while True:
        cycle_start = loop.time()
        try:
            await community.poll(client)
        except Exception:  # never let the loop die (CommunityState already guards)
            log.exception("community poll failed")
        elapsed = loop.time() - cycle_start
        await asyncio.sleep(max(0, config.COMMUNITY_INTERVAL - elapsed))


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_sentry()  # Layer 1: no-op when SENTRY_DSN is unset.
    app.state.client = httpx.AsyncClient(timeout=config.PROBE_TIMEOUT)
    app.state.probe_state = None
    try:
        app.state.targets = await build_targets(app.state.client)
    except Exception:
        log.exception("failed to build probe targets at startup")
        app.state.targets = []
    log.info("probe targets: %s", [(t["id"], t["model"]) for t in app.state.targets])
    history_store = ProbeHistoryStore()
    history_store.init()
    history_store.cleanup_old()
    initial_history = (
        history_store.load_history(app.state.targets) if app.state.targets else {}
    )
    restored = sum(len(pts) for pts in initial_history.values())
    if restored:
        log.info("restored probe history from sqlite: %s points", restored)
    app.state.probe_state = ProbeState(
        app.state.targets,
        history_store=history_store,
        initial_history=initial_history,
    )

    # Community signals (Reddit) — corroboration source, attached to probe_state
    # so the snapshot can surface it. Built from the probed provider names; never
    # blocks startup if Reddit is unreachable.
    provider_names = list(dict.fromkeys(t["name"] for t in app.state.targets))
    app.state.community = CommunityState(provider_names)
    app.state.probe_state.community = app.state.community

    if app.state.targets:
        try:
            await probe_all(app.state.client, app.state.probe_state, app.state.targets)
        except Exception:
            log.exception("initial probe cycle failed")
    try:
        await app.state.community.poll(app.state.client)  # best-effort warm-up
    except Exception:
        log.exception("initial community poll failed")

    task = asyncio.create_task(_probe_loop(app))
    community_task = asyncio.create_task(_community_loop(app))
    try:
        yield
    finally:
        for t in (task, community_task):
            t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        with contextlib.suppress(asyncio.CancelledError):
            await community_task
        await app.state.client.aclose()


app = FastAPI(
    title="WatchTower AI — Probe Engine",
    lifespan=lifespan,
    docs_url="/docs" if config.ENABLE_DOCS else None,
    redoc_url="/redoc" if config.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if config.ENABLE_DOCS else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=config.CORS_ALLOW_HEADERS,
)


@app.get("/health", response_model=HealthSnapshot)
async def health() -> HealthSnapshot:
    if app.state.probe_state is None:
        raise HTTPException(status_code=503, detail="Probe engine not yet initialized")
    return HealthSnapshot(**app.state.probe_state.snapshot())


@app.get("/diagnose", response_model=LocalDiagnosis)
async def diagnose() -> LocalDiagnosis:
    """Local environment diagnosis cross-referenced with the probe layer.
    Answers: is the problem yours (DNS/TCP/key), your account (quota/config),
    or the service's? The verdict reflects the real per-provider probe status."""
    providers: list[dict] = []
    if app.state.probe_state is not None:
        providers = app.state.probe_state.snapshot()["providers"]
    result = await diagnostics.diagnose(app.state.client, providers)
    return LocalDiagnosis(**result)


@app.get("/backtest", response_model=BacktestReport)
async def backtest_report() -> BacktestReport:
    """Detection lead-time backtest over the VU Amsterdam dataset. All numbers
    computed from the CSV; the one estimated quantity (impact-window start) is
    flagged. Returns 503 if the dataset isn't bundled with the deployment."""
    try:
        return BacktestReport(**backtest.build_report())
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="VU dataset not available")


@app.get("/")
async def root() -> dict:
    return {"service": "watchtower-probe-engine", "probe_interval": config.PROBE_INTERVAL}
