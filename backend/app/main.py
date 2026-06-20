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
    app.state.probe_state = None
    try:
        app.state.targets = await build_targets(app.state.client)
    except Exception:
        log.exception("failed to build probe targets at startup")
        app.state.targets = []
    log.info("probe targets: %s", [(t["id"], t["model"]) for t in app.state.targets])
    app.state.probe_state = ProbeState(app.state.targets)
    if app.state.targets:
        try:
            await probe_all(app.state.client, app.state.probe_state, app.state.targets)
        except Exception:
            log.exception("initial probe cycle failed")
    task = asyncio.create_task(_probe_loop(app))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await app.state.client.aclose()


app = FastAPI(title="Watchtower AI — Probe Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthSnapshot)
async def health() -> HealthSnapshot:
    if app.state.probe_state is None:
        raise HTTPException(status_code=503, detail="Probe engine not yet initialized")
    return HealthSnapshot(**app.state.probe_state.snapshot())


@app.get("/")
async def root() -> dict:
    return {"service": "watchtower-probe-engine", "probe_interval": config.PROBE_INTERVAL}
