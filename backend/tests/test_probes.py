"""Tests for probes.py: helper functions, scoring, ProbeState, alerts,
probe adapters, and probe_all orchestration.

All network calls are mocked via httpx.MockTransport."""
import asyncio
from unittest.mock import patch

import httpx
import pytest

from app import config, probes
from app.probes import (
    ProbeResult,
    ProbeState,
    _build_alerts,
    _qa_ok,
    _run_one,
    _score_and_status,
    _token_rate,
    pick_latest,
    probe_all,
)


# ---------------------------------------------------------------------------
# _qa_ok
# ---------------------------------------------------------------------------

class TestQaOk:
    def test_contains_expected(self):
        assert _qa_ok("The answer is 4.") is True

    def test_exact_match(self):
        assert _qa_ok("4") is True

    def test_wrong_answer(self):
        assert _qa_ok("5") is False

    def test_empty_string(self):
        assert _qa_ok("") is False

    def test_none(self):
        assert _qa_ok(None) is False

    def test_whitespace_around(self):
        assert _qa_ok("  4  ") is True


# ---------------------------------------------------------------------------
# _token_rate
# ---------------------------------------------------------------------------

class TestTokenRate:
    def test_normal(self):
        # 100 tokens in 500ms = 200 tok/s
        assert _token_rate(100, 500) == 200

    def test_zero_tokens(self):
        assert _token_rate(0, 500) == 0

    def test_none_tokens(self):
        assert _token_rate(None, 500) == 0

    def test_zero_latency(self):
        assert _token_rate(100, 0) == 0

    def test_negative_latency(self):
        assert _token_rate(100, -1) == 0

    def test_rounding(self):
        # 10 tokens in 300ms = 33.33 -> 33
        assert _token_rate(10, 300) == 33


# ---------------------------------------------------------------------------
# pick_latest
# ---------------------------------------------------------------------------

class TestPickLatest:
    def test_picks_latest_by_version(self):
        models = ["claude-3-opus-20240229", "claude-opus-4-20250514"]
        assert pick_latest(models, include="opus") == "claude-opus-4-20250514"

    def test_exclude_filters(self):
        models = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
        assert pick_latest(models, include="flash", exclude=("lite",)) == "gemini-2.5-flash"

    def test_no_match(self):
        assert pick_latest(["gpt-4o"], include="opus") is None

    def test_empty_list(self):
        assert pick_latest([], include="opus") is None

    def test_case_insensitive(self):
        models = ["Claude-Opus-4-20250514"]
        assert pick_latest(models, include="opus") == "Claude-Opus-4-20250514"


# ---------------------------------------------------------------------------
# _score_and_status
# ---------------------------------------------------------------------------

class TestScoreAndStatus:
    def test_none_result(self):
        score, status = _score_and_status(None)
        assert score == 0
        assert status == "unknown"

    def test_unavailable(self):
        r = ProbeResult(available=False, latency_ms=100, qa_correct=False, token_rate=0, http_status=500)
        score, status = _score_and_status(r)
        assert score == 0
        assert status == "down"

    def test_operational_fast_qa_pass(self):
        r = ProbeResult(available=True, latency_ms=500, qa_correct=True, token_rate=100, http_status=200)
        score, status = _score_and_status(r)
        assert score == 100
        assert status == "operational"

    def test_degraded_qa_fail(self):
        # qa fail costs 35 -> score 65, which is >= 50 -> degraded
        r = ProbeResult(available=True, latency_ms=500, qa_correct=False, token_rate=100, http_status=200)
        score, status = _score_and_status(r)
        assert score == 65
        assert status == "degraded"

    def test_degraded_high_latency(self):
        # latency 2000ms: penalty = min(40, (2000-1000)/100*2) = min(40, 20) = 20
        # score = 100 - 20 = 80, >= 50 -> degraded (but actually >=85 is operational)
        r = ProbeResult(available=True, latency_ms=2000, qa_correct=True, token_rate=50, http_status=200)
        score, status = _score_and_status(r)
        assert score == 80
        assert status == "degraded"

    def test_down_qa_fail_and_high_latency(self):
        # qa fail (-35) + latency 3000ms (-40 capped) = 25
        r = ProbeResult(available=True, latency_ms=3000, qa_correct=False, token_rate=10, http_status=200)
        score, status = _score_and_status(r)
        assert score == 25
        assert status == "down"

    def test_operational_boundary(self):
        # latency 1375ms: penalty = min(40, (1375-1000)/100*2) = min(40, 7.5) = 7.5
        # score = 100 - 7.5 = 92.5 -> round to 92 -> >= 85 -> operational
        r = ProbeResult(available=True, latency_ms=1375, qa_correct=True, token_rate=50, http_status=200)
        score, status = _score_and_status(r)
        assert score >= 85
        assert status == "operational"

    def test_latency_penalty_caps_at_40(self):
        # latency 10_000ms: penalty = min(40, (10000-1000)/100*2) = 40
        r = ProbeResult(available=True, latency_ms=10_000, qa_correct=True, token_rate=10, http_status=200)
        score, status = _score_and_status(r)
        assert score == 60
        assert status == "degraded"

    def test_score_never_negative(self):
        r = ProbeResult(available=True, latency_ms=50_000, qa_correct=False, token_rate=0, http_status=200)
        score, status = _score_and_status(r)
        assert score >= 0


# ---------------------------------------------------------------------------
# ProbeState
# ---------------------------------------------------------------------------

def _make_targets():
    return [
        {"id": "claude-flagship", "name": "Claude", "tier": "flagship",
         "model": "claude-opus-4", "probe": None, "has_key": True},
        {"id": "gpt-flagship", "name": "GPT", "tier": "flagship",
         "model": "gpt-5", "probe": None, "has_key": True},
    ]


class TestProbeState:
    def test_init_seeds_unknown(self):
        targets = _make_targets()
        state = ProbeState(targets)
        snap = state.snapshot()
        assert len(snap["providers"]) == 2
        for p in snap["providers"]:
            assert p["status"] == "unknown"
            assert p["healthScore"] == 0

    def test_apply_updates_state(self):
        targets = _make_targets()
        state = ProbeState(targets)
        result = ProbeResult(available=True, latency_ms=400, qa_correct=True, token_rate=80, http_status=200)
        state.apply(targets[0], result)
        snap = state.snapshot()
        claude = next(p for p in snap["providers"] if p["id"] == "claude-flagship")
        assert claude["status"] == "operational"
        assert claude["healthScore"] == 100
        assert claude["latencyMs"] == 400
        assert claude["tokenRate"] == 80
        assert claude["qaCorrect"] is True

    def test_apply_none_result(self):
        targets = _make_targets()
        state = ProbeState(targets)
        state.apply(targets[0], None)
        snap = state.snapshot()
        claude = next(p for p in snap["providers"] if p["id"] == "claude-flagship")
        assert claude["status"] == "unknown"
        assert claude["latencyMs"] == 0

    def test_latency_history_accumulates(self):
        targets = _make_targets()
        state = ProbeState(targets)
        for i in range(3):
            result = ProbeResult(available=True, latency_ms=100 + i * 10,
                                 qa_correct=True, token_rate=50, http_status=200)
            state.apply(targets[0], result)
        snap = state.snapshot()
        claude = next(p for p in snap["providers"] if p["id"] == "claude-flagship")
        assert len(claude["latencyHistory"]) == 3

    def test_history_respects_maxlen(self):
        targets = _make_targets()
        state = ProbeState(targets)
        for i in range(config.HISTORY_LEN + 5):
            result = ProbeResult(available=True, latency_ms=100,
                                 qa_correct=True, token_rate=50, http_status=200)
            state.apply(targets[0], result)
        snap = state.snapshot()
        claude = next(p for p in snap["providers"] if p["id"] == "claude-flagship")
        assert len(claude["latencyHistory"]) == config.HISTORY_LEN

    def test_snapshot_includes_updated_at(self):
        targets = _make_targets()
        state = ProbeState(targets)
        snap = state.snapshot()
        assert "updatedAt" in snap

    def test_snapshot_includes_alerts(self):
        targets = _make_targets()
        state = ProbeState(targets)
        snap = state.snapshot()
        assert "alerts" in snap

    def test_seed_preserves_tier_and_model(self):
        targets = _make_targets()
        state = ProbeState(targets)
        snap = state.snapshot()
        claude = next(p for p in snap["providers"] if p["id"] == "claude-flagship")
        assert claude["tier"] == "flagship"
        assert claude["model"] == "claude-opus-4"


# ---------------------------------------------------------------------------
# _build_alerts
# ---------------------------------------------------------------------------

class TestBuildAlerts:
    def test_no_alerts_when_all_operational(self):
        providers = [
            {"id": "claude", "name": "Claude", "status": "operational",
             "healthScore": 98, "latencyMs": 400, "qaCorrect": True, "tier": "flagship", "model": "m"},
        ]
        alerts = _build_alerts(providers)
        assert alerts == []

    def test_alert_for_degraded(self):
        providers = [
            {"id": "claude", "name": "Claude", "status": "operational",
             "healthScore": 98, "latencyMs": 400, "qaCorrect": True, "tier": "flagship", "model": "m"},
            {"id": "gemini", "name": "Gemini", "status": "degraded",
             "healthScore": 60, "latencyMs": 2000, "qaCorrect": False, "tier": "flagship", "model": "g"},
        ]
        alerts = _build_alerts(providers)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "warning"
        assert "Gemini" in alerts[0]["title"]
        assert "degraded" in alerts[0]["title"]
        assert "Claude" in alerts[0]["recommendedAlternative"]

    def test_alert_for_down(self):
        providers = [
            {"id": "claude", "name": "Claude", "status": "operational",
             "healthScore": 98, "latencyMs": 400, "qaCorrect": True, "tier": "flagship", "model": "m"},
            {"id": "gpt", "name": "GPT", "status": "down",
             "healthScore": 0, "latencyMs": 0, "qaCorrect": False, "tier": "flagship", "model": "g"},
        ]
        alerts = _build_alerts(providers)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "critical"

    def test_no_healthy_alternative(self):
        providers = [
            {"id": "claude", "name": "Claude", "status": "down",
             "healthScore": 0, "latencyMs": 0, "qaCorrect": False, "tier": "flagship", "model": "m"},
            {"id": "gpt", "name": "GPT", "status": "down",
             "healthScore": 0, "latencyMs": 0, "qaCorrect": False, "tier": "flagship", "model": "g"},
        ]
        alerts = _build_alerts(providers)
        assert len(alerts) == 2
        for a in alerts:
            assert "No healthy alternative" in a["recommendedAlternative"]
            assert "Inconclusive" in a["attribution"]

    def test_alert_fields_complete(self):
        providers = [
            {"id": "claude", "name": "Claude", "status": "degraded",
             "healthScore": 55, "latencyMs": 3000, "qaCorrect": False, "tier": "mid", "model": "claude-sonnet"},
        ]
        alerts = _build_alerts(providers)
        a = alerts[0]
        required_keys = {"id", "severity", "providerId", "title", "attribution",
                         "recoveryEta", "recommendedAlternative", "insight", "createdAt"}
        assert required_keys.issubset(a.keys())

    def test_unknown_status_not_alerted(self):
        providers = [
            {"id": "claude", "name": "Claude", "status": "unknown",
             "healthScore": 0, "latencyMs": 0, "qaCorrect": False, "tier": "flagship", "model": "m"},
        ]
        alerts = _build_alerts(providers)
        assert alerts == []


# ---------------------------------------------------------------------------
# _run_one — probe adapter execution
# ---------------------------------------------------------------------------

class TestRunOne:
    def test_missing_key_returns_none(self):
        target = {"id": "claude-flagship", "has_key": False, "probe": None, "model": "m"}
        result = asyncio.get_event_loop().run_until_complete(
            _run_one(httpx.AsyncClient(), target)
        )
        assert result is None

    def test_successful_probe(self):
        async def fake_probe(client, model):
            return "4", 10, 200

        target = {"id": "test", "has_key": True, "probe": fake_probe, "model": "m"}

        async def run():
            async with httpx.AsyncClient() as client:
                return await _run_one(client, target)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result is not None
        assert result.available is True
        assert result.qa_correct is True
        assert result.http_status == 200
        assert result.latency_ms >= 0

    def test_non_200_probe(self):
        async def fake_probe(client, model):
            return None, None, 500

        target = {"id": "test", "has_key": True, "probe": fake_probe, "model": "m"}

        async def run():
            async with httpx.AsyncClient() as client:
                return await _run_one(client, target)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result is not None
        assert result.available is False
        assert result.qa_correct is False
        assert result.token_rate == 0

    def test_exception_in_probe(self):
        async def exploding_probe(client, model):
            raise ConnectionError("boom")

        target = {"id": "test", "has_key": True, "probe": exploding_probe, "model": "m"}

        async def run():
            async with httpx.AsyncClient() as client:
                return await _run_one(client, target)

        result = asyncio.get_event_loop().run_until_complete(run())
        assert result is not None
        assert result.available is False
        assert result.error is not None
        assert "ConnectionError" in result.error


# ---------------------------------------------------------------------------
# Probe adapters (Claude, GPT, Gemini) via MockTransport
# ---------------------------------------------------------------------------

class TestProbeAdapters:
    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_probe_claude_success(self):
        async def main():
            transport = httpx.MockTransport(lambda r: httpx.Response(200, json={
                "content": [{"text": "4"}],
                "usage": {"output_tokens": 5},
            }))
            async with httpx.AsyncClient(transport=transport) as c:
                text, tokens, status = await probes._probe_claude(c, "claude-opus-4")
            assert text == "4"
            assert tokens == 5
            assert status == 200
        self._run(main())

    def test_probe_claude_error(self):
        async def main():
            transport = httpx.MockTransport(lambda r: httpx.Response(429, json={}))
            async with httpx.AsyncClient(transport=transport) as c:
                text, tokens, status = await probes._probe_claude(c, "claude-opus-4")
            assert text is None
            assert tokens is None
            assert status == 429
        self._run(main())

    def test_probe_gpt_success(self):
        async def main():
            transport = httpx.MockTransport(lambda r: httpx.Response(200, json={
                "choices": [{"message": {"content": "4"}}],
                "usage": {"completion_tokens": 3},
            }))
            async with httpx.AsyncClient(transport=transport) as c:
                text, tokens, status = await probes._probe_gpt(c, "gpt-5")
            assert text == "4"
            assert tokens == 3
            assert status == 200
        self._run(main())

    def test_probe_gpt_error(self):
        async def main():
            transport = httpx.MockTransport(lambda r: httpx.Response(500, json={}))
            async with httpx.AsyncClient(transport=transport) as c:
                text, tokens, status = await probes._probe_gpt(c, "gpt-5")
            assert text is None
            assert status == 500
        self._run(main())

    def test_probe_gemini_success(self):
        async def main():
            transport = httpx.MockTransport(lambda r: httpx.Response(200, json={
                "candidates": [{"content": {"parts": [{"text": "4"}]}}],
                "usageMetadata": {"candidatesTokenCount": 2},
            }))
            async with httpx.AsyncClient(transport=transport) as c:
                text, tokens, status = await probes._probe_gemini(c, "gemini-2.5-pro")
            assert text == "4"
            assert tokens == 2
            assert status == 200
        self._run(main())

    def test_probe_gemini_error(self):
        async def main():
            transport = httpx.MockTransport(lambda r: httpx.Response(403, json={}))
            async with httpx.AsyncClient(transport=transport) as c:
                text, tokens, status = await probes._probe_gemini(c, "gemini-2.5-pro")
            assert text is None
            assert status == 403
        self._run(main())

    def test_probe_gemini_empty_candidates(self):
        async def main():
            transport = httpx.MockTransport(lambda r: httpx.Response(200, json={
                "candidates": [],
                "usageMetadata": {},
            }))
            async with httpx.AsyncClient(transport=transport) as c:
                text, tokens, status = await probes._probe_gemini(c, "gemini-2.5-pro")
            assert text == ""
            assert tokens is None
            assert status == 200
        self._run(main())


# ---------------------------------------------------------------------------
# probe_all — end-to-end orchestration
# ---------------------------------------------------------------------------

class TestProbeAll:
    def test_probe_all_applies_results(self):
        async def ok_probe(client, model):
            return "4", 10, 200

        targets = [
            {"id": "a-flagship", "name": "A", "tier": "flagship",
             "model": "a-1", "probe": ok_probe, "has_key": True},
            {"id": "b-flagship", "name": "B", "tier": "flagship",
             "model": "b-1", "probe": ok_probe, "has_key": True},
        ]
        state = ProbeState(targets)

        async def run():
            async with httpx.AsyncClient() as c:
                await probe_all(c, state, targets)

        asyncio.get_event_loop().run_until_complete(run())
        snap = state.snapshot()
        for p in snap["providers"]:
            assert p["status"] == "operational"

    def test_probe_all_handles_missing_key(self):
        targets = [
            {"id": "a-flagship", "name": "A", "tier": "flagship",
             "model": "a-1", "probe": None, "has_key": False},
        ]
        state = ProbeState(targets)

        async def run():
            async with httpx.AsyncClient() as c:
                await probe_all(c, state, targets)

        asyncio.get_event_loop().run_until_complete(run())
        snap = state.snapshot()
        assert snap["providers"][0]["status"] == "unknown"
