"""Tests for local environment diagnostics.

Network is never touched: DNS/TCP are monkeypatched and key checks go through
httpx.MockTransport. Covers per-check classification, the verdict logic (the
product's core "your problem vs the service's"), and graceful degradation."""
import asyncio
import socket

import httpx

from app import diagnostics
from app.diagnostics import (
    PROVIDERS,
    _classify_key,
    _local_health,
    build_verdict,
    check_dns,
    check_key,
    check_tcp,
    diagnose,
)


def _run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _claude():
    return next(p for p in PROVIDERS if p.name == "Claude")


# --- key classification ----------------------------------------------------

class TestClassifyKey:
    def test_200_pass(self):
        assert _classify_key(200)[0] == "pass"

    def test_429_is_pass_key_valid(self):
        # Authenticated but throttled => the key works.
        assert _classify_key(429)[0] == "pass"

    def test_401_fail(self):
        status, detail = _classify_key(401)
        assert status == "fail" and "401" in detail

    def test_403_fail(self):
        assert _classify_key(403)[0] == "fail"

    def test_400_fail(self):
        assert _classify_key(400)[0] == "fail"

    def test_500_unknown(self):
        assert _classify_key(500)[0] == "unknown"


# --- DNS / TCP checks ------------------------------------------------------

class TestDns:
    def test_resolves(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [("x",)])
        r = _run_async(check_dns("Claude", "api.anthropic.com"))
        assert r["status"] == "pass"

    def test_resolution_failure(self, monkeypatch):
        def boom(*a, **k):
            raise socket.gaierror("nope")
        monkeypatch.setattr(socket, "getaddrinfo", boom)
        r = _run_async(check_dns("Claude", "api.anthropic.com"))
        assert r["status"] == "fail"
        assert "DNS" in r["detail"]

    def test_unexpected_error_is_unknown(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("weird")
        monkeypatch.setattr(socket, "getaddrinfo", boom)
        r = _run_async(check_dns("Claude", "api.anthropic.com"))
        assert r["status"] == "unknown"


class TestTcp:
    def test_connects(self, monkeypatch):
        class FakeWriter:
            def close(self): pass
            async def wait_closed(self): pass

        async def fake_open(host, port):
            return (object(), FakeWriter())
        monkeypatch.setattr(diagnostics.asyncio, "open_connection", fake_open)
        r = _run_async(check_tcp("Claude", "api.anthropic.com"))
        assert r["status"] == "pass"

    def test_connection_refused(self, monkeypatch):
        async def fake_open(host, port):
            raise OSError("refused")
        monkeypatch.setattr(diagnostics.asyncio, "open_connection", fake_open)
        r = _run_async(check_tcp("Claude", "api.anthropic.com"))
        assert r["status"] == "fail"


# --- key check via MockTransport -------------------------------------------

def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestCheckKey:
    def test_valid_key(self):
        def handler(req):
            return httpx.Response(200, json={"data": []})

        async def main():
            async with _client(handler) as c:
                return await check_key(c, _claude())
        assert _run_async(main())["status"] == "pass"

    def test_invalid_key(self):
        def handler(req):
            return httpx.Response(401, json={"error": "bad key"})

        async def main():
            async with _client(handler) as c:
                return await check_key(c, _claude())
        assert _run_async(main())["status"] == "fail"

    def test_network_error_is_unknown_not_key_failure(self):
        # The critical distinction: a dead network must NOT be blamed on the key.
        def handler(req):
            raise httpx.ConnectError("network down", request=req)

        async def main():
            async with _client(handler) as c:
                return await check_key(c, _claude())
        r = _run_async(main())
        assert r["status"] == "unknown"
        assert "network" in r["detail"]


# --- verdict logic (the core value) ----------------------------------------

def _checks(*statuses):
    # statuses: list of (provider, check, status, detail-ish)
    return [
        {"provider": p, "check": c, "status": s, "detail": f"{p} {c} {s}"}
        for p, c, s in statuses
    ]


class TestVerdict:
    def test_local_red_is_your_side(self):
        checks = _checks(("Claude", "key", "fail"))
        v = build_verdict(checks, anomalies=[])
        assert v["verdictKind"] == "your-side"
        assert "your side" in v["verdict"].lower()
        assert v["localHealthy"] is False

    def test_local_green_plus_anomaly_is_service_side(self):
        checks = _checks(("Claude", "dns", "pass"), ("Claude", "tcp", "pass"),
                         ("Claude", "key", "pass"))
        v = build_verdict(checks, anomalies=["Gemini"])
        assert v["verdictKind"] == "service-side"
        assert "Gemini" in v["verdict"]
        assert "not yours" in v["verdict"]

    def test_local_green_no_anomaly_is_all_clear(self):
        checks = _checks(("Claude", "dns", "pass"), ("Claude", "key", "pass"))
        v = build_verdict(checks, anomalies=[])
        assert v["verdictKind"] == "all-clear"

    def test_unknown_only_is_indeterminate(self):
        checks = _checks(("Claude", "key", "unknown"))
        v = build_verdict(checks, anomalies=["Gemini"])
        assert v["verdictKind"] == "indeterminate"
        assert v["localHealthy"] is None

    def test_fail_takes_precedence_over_anomaly(self):
        # Your broken key is your problem first, even if a service is also down.
        checks = _checks(("Claude", "key", "fail"), ("GPT", "dns", "pass"))
        v = build_verdict(checks, anomalies=["GPT"])
        assert v["verdictKind"] == "your-side"

    def test_empty_checks(self):
        v = build_verdict([], anomalies=[])
        assert v["verdictKind"] == "indeterminate"

    def test_service_side_dedupes_provider_names(self):
        checks = _checks(("Claude", "dns", "pass"))
        v = build_verdict(checks, anomalies=["Gemini", "Gemini"])
        assert v["verdict"].count("Gemini") == 1


class TestLocalHealth:
    def test_all_pass(self):
        assert _local_health(_checks(("C", "dns", "pass"))) is True

    def test_any_fail(self):
        assert _local_health(_checks(("C", "dns", "pass"), ("C", "key", "fail"))) is False

    def test_unknown_without_fail(self):
        assert _local_health(_checks(("C", "dns", "pass"), ("C", "key", "unknown"))) is None


# --- diagnose() integration ------------------------------------------------

def test_diagnose_builds_full_result(monkeypatch):
    # Force exactly one configured provider (Claude) and stub the network.
    claude = _claude()
    monkeypatch.setattr(diagnostics, "PROVIDERS", [claude])
    monkeypatch.setattr(claude, "key", lambda: "sk-test")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [("x",)])

    class FakeWriter:
        def close(self): pass
        async def wait_closed(self): pass

    async def fake_open(host, port):
        return (object(), FakeWriter())
    monkeypatch.setattr(diagnostics.asyncio, "open_connection", fake_open)

    def handler(req):
        return httpx.Response(200, json={"data": []})

    async def main():
        async with _client(handler) as c:
            return await diagnose(c, anomalies=[])

    result = _run_async(main())
    assert {c["check"] for c in result["checks"]} == {"dns", "tcp", "key"}
    assert result["verdictKind"] == "all-clear"
    assert "checkedAt" in result
