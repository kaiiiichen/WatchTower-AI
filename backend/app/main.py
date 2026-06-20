"""FastAPI app: background probe loop + GET /health returning a snapshot whose
JSON matches frontend/src/lib/types.ts exactly."""
import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .models import HealthSnapshot
from .probes import ProbeState, build_targets, probe_all

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("watchtower")


async def _probe_loop(app: FastAPI) -> None:
    client: httpx.AsyncClient = app.state.client
    state: ProbeState = app.state.probe_state
    while True:
        try:
            await probe_all(client, state, app.state.targets)
            log.info("probe cycle complete: %s", state.updated_at)
        except Exception:  # never let the loop die
            log.exception("probe cycle failed")
        await asyncio.sleep(config.PROBE_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(timeout=config.PROBE_TIMEOUT)
    # Dynamic model discovery (flagship + mid per provider) at startup.
    app.state.targets = await build_targets(app.state.client)
    log.info("probe targets: %s", [(t["id"], t["model"]) for t in app.state.targets])
    app.state.probe_state = ProbeState(app.state.targets)
    # One immediate probe so /health has real data fast, then loop in background.
    await probe_all(app.state.client, app.state.probe_state, app.state.targets)
    task = asyncio.create_task(_probe_loop(app))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await app.state.client.aclose()


app = FastAPI(
    title="Watchtower AI — Probe Engine",
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
    return HealthSnapshot(**app.state.probe_state.snapshot())


@app.get("/")
async def root() -> dict:
    return {"service": "watchtower-probe-engine", "probe_interval": config.PROBE_INTERVAL}
