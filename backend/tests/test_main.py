"""Tests for main.py: FastAPI endpoint responses.

Uses a standalone FastAPI app with the same routes but no lifespan, so no real
API calls are made."""
from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import config
from app.models import HealthSnapshot
from app.probes import ProbeResult, ProbeState


def _make_targets():
    return [
        {"id": "claude-flagship", "name": "Claude", "tier": "flagship",
         "model": "claude-opus-4", "probe": None, "has_key": True},
        {"id": "gpt-flagship", "name": "GPT", "tier": "flagship",
         "model": "gpt-5", "probe": None, "has_key": True},
    ]


def _build_test_app(targets=None, apply_results=True):
    """Create a fresh app with seeded state — no lifespan network calls."""
    if targets is None:
        targets = _make_targets()

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    test_app = FastAPI(title="test", lifespan=noop_lifespan)
    state = ProbeState(targets)

    if apply_results:
        state.apply(
            targets[0],
            ProbeResult(available=True, latency_ms=350, qa_correct=True,
                        token_rate=80, http_status=200),
        )
        state.apply(
            targets[1],
            ProbeResult(available=True, latency_ms=500, qa_correct=True,
                        token_rate=60, http_status=200),
        )

    test_app.state.targets = targets
    test_app.state.probe_state = state

    @test_app.get("/health", response_model=HealthSnapshot)
    async def health() -> HealthSnapshot:
        return HealthSnapshot(**test_app.state.probe_state.snapshot())

    @test_app.get("/")
    async def root() -> dict:
        return {"service": "watchtower-probe-engine", "probe_interval": config.PROBE_INTERVAL}

    return test_app


class TestRootEndpoint:
    def test_root_returns_service_info(self):
        app = _build_test_app()
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "watchtower-probe-engine"
        assert "probe_interval" in data


class TestHealthEndpoint:
    def test_health_returns_snapshot(self):
        app = _build_test_app()
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert "alerts" in data
        assert "updatedAt" in data

    def test_health_provider_count(self):
        app = _build_test_app()
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/health")
        data = resp.json()
        assert len(data["providers"]) == 2

    def test_health_provider_fields(self):
        app = _build_test_app()
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/health")
        data = resp.json()
        p = data["providers"][0]
        required = {"id", "name", "status", "healthScore", "latencyMs",
                    "tokenRate", "qaCorrect", "latencyHistory", "tier", "model"}
        assert required.issubset(p.keys())

    def test_health_has_operational_providers(self):
        app = _build_test_app()
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/health")
        data = resp.json()
        statuses = {p["status"] for p in data["providers"]}
        assert "operational" in statuses

    def test_health_no_alerts_when_all_ok(self):
        app = _build_test_app()
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/health")
        data = resp.json()
        assert data["alerts"] == []

    def test_health_with_degraded_provider(self):
        targets = _make_targets()
        app = _build_test_app(targets=targets)
        # Override GPT with a bad result
        app.state.probe_state.apply(
            targets[1],
            ProbeResult(available=True, latency_ms=3000, qa_correct=False,
                        token_rate=10, http_status=200),
        )
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/health")
        data = resp.json()
        gpt = next(p for p in data["providers"] if p["id"] == "gpt-flagship")
        assert gpt["status"] in ("degraded", "down")
        assert len(data["alerts"]) >= 1

    def test_health_all_unknown_no_results(self):
        app = _build_test_app(apply_results=False)
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/health")
        data = resp.json()
        for p in data["providers"]:
            assert p["status"] == "unknown"
        # unknown providers don't generate alerts
        assert data["alerts"] == []

    def test_health_response_validates_as_model(self):
        app = _build_test_app()
        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.get("/health")
        # Should parse without error
        snap = HealthSnapshot(**resp.json())
        assert len(snap.providers) == 2
