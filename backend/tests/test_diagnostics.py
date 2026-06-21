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
    _ips_from_getaddrinfo,
    _local_health,
    build_verdict,
    check_dns,
    check_key,
    check_tcp,
    diagnose,
    egress_ip,
    environment_profile,
    resolve_ips,
    tcp_rtt_ms,
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


def _provs(*pairs):
    return [{"name": n, "status": s} for n, s in pairs]


_GREEN = [
    {"provider": "Claude", "check": "dns", "status": "pass", "detail": "ok"},
    {"provider": "Claude", "check": "tcp", "status": "pass", "detail": "ok"},
    {"provider": "Claude", "check": "key", "status": "pass", "detail": "ok"},
]


class TestVerdict:
    # Branch 1: any local check failed -> your environment.
    def test_branch1_local_red_is_your_side(self):
        checks = _checks(("Claude", "key", "fail"))
        v = build_verdict(checks, _provs(("Claude", "operational")))
        assert v["verdictKind"] == "your-side"
        assert "your environment has a problem" in v["verdict"].lower()
        assert v["localHealthy"] is False

    # Branch 2: local green + rate_limited/misconfigured -> account layer.
    def test_branch2_rate_limited_is_account_side(self):
        v = build_verdict(_GREEN, _provs(("Claude", "operational"), ("Gemini", "rate_limited")))
        assert v["verdictKind"] == "account-side"
        assert v["localHealthy"] is True
        assert "Gemini" in v["verdict"]
        assert "account layer" in v["verdict"].lower()
        assert "not a service outage" in v["verdict"].lower()
        assert "all clear" not in v["verdict"].lower()  # the bug we're fixing

    def test_branch2_misconfigured_is_account_side(self):
        v = build_verdict(_GREEN, _provs(("Gemini", "misconfigured")))
        assert v["verdictKind"] == "account-side"
        assert "configuration problem" in v["verdict"].lower()

    # Branch 3: local green + down -> service side.
    def test_branch3_down_is_service_side(self):
        v = build_verdict(_GREEN, _provs(("Claude", "operational"), ("Gemini", "down")))
        assert v["verdictKind"] == "service-side"
        assert "not yours" in v["verdict"].lower()
        assert "Gemini" in v["verdict"]

    def test_branch3_degraded_is_service_side(self):
        v = build_verdict(_GREEN, _provs(("GPT", "degraded")))
        assert v["verdictKind"] == "service-side"

    # Branch 4: local green AND all operational -> all-clear ONLY here.
    def test_branch4_all_operational_is_all_clear(self):
        v = build_verdict(_GREEN, _provs(("Claude", "operational"), ("GPT", "operational")))
        assert v["verdictKind"] == "all-clear"

    def test_all_clear_only_when_truly_all_operational(self):
        # The reported bug: rate_limited must NOT yield all-clear.
        v = build_verdict(_GREEN, _provs(("Gemini", "rate_limited")))
        assert v["verdictKind"] != "all-clear"

    # Priority + combination.
    def test_local_fail_beats_any_probe_status(self):
        checks = _checks(("Claude", "key", "fail"))
        v = build_verdict(checks, _provs(("Gemini", "down"), ("GPT", "rate_limited")))
        assert v["verdictKind"] == "your-side"

    def test_account_and_service_both_present(self):
        v = build_verdict(_GREEN, _provs(("Gemini", "rate_limited"), ("GPT", "down")))
        assert v["verdictKind"] == "account-side"  # user-actionable headline
        assert "Gemini" in v["verdict"] and "GPT" in v["verdict"]  # both surfaced

    def test_unknown_only_is_indeterminate(self):
        checks = _checks(("Claude", "key", "unknown"))
        v = build_verdict(checks, _provs(("Gemini", "down")))
        assert v["verdictKind"] == "indeterminate"
        assert v["localHealthy"] is None

    def test_empty_checks(self):
        v = build_verdict([], [])
        assert v["verdictKind"] == "indeterminate"


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
            return await diagnose(c, [{"name": "Claude", "status": "operational"}])

    result = _run_async(main())
    assert {c["check"] for c in result["checks"]} == {"dns", "tcp", "key"}
    assert result["verdictKind"] == "all-clear"
    assert "checkedAt" in result


def test_diagnose_rate_limited_is_not_all_clear(monkeypatch):
    # End-to-end: local green + a rate_limited provider must NOT be "all clear".
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
            return await diagnose(c, [{"name": "Gemini", "status": "rate_limited"}])

    result = _run_async(main())
    assert result["verdictKind"] == "account-side"
    assert "all clear" not in result["verdict"].lower()


# ---------------------------------------------------------------------------
# Environment profile (informational — never affects the verdict)
# ---------------------------------------------------------------------------

# A realistic getaddrinfo 5-tuple: (family, type, proto, canonname, sockaddr).
def _gai(*ips):
    return [(2, 1, 6, "", (ip, 443)) for ip in ips]


class TestResolveIps:
    def test_parses_and_dedupes(self):
        assert _ips_from_getaddrinfo(_gai("1.1.1.1", "2.2.2.2", "1.1.1.1")) == \
            ["1.1.1.1", "2.2.2.2"]

    def test_malformed_entries_skipped(self):
        # Defends against odd/mocked getaddrinfo shapes -> None, not a crash.
        assert _ips_from_getaddrinfo([("x",)]) is None

    def test_resolve_ips_success(self, monkeypatch):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _gai("9.9.9.9"))
        assert _run_async(resolve_ips("api.anthropic.com")) == ["9.9.9.9"]

    def test_resolve_ips_failure_is_none(self, monkeypatch):
        def boom(*a, **k):
            raise socket.gaierror("nope")
        monkeypatch.setattr(socket, "getaddrinfo", boom)
        assert _run_async(resolve_ips("api.anthropic.com")) is None


class TestTcpRtt:
    def test_returns_ms_int(self, monkeypatch):
        class FakeWriter:
            def close(self): pass
            async def wait_closed(self): pass

        async def fake_open(host, port):
            return (object(), FakeWriter())
        monkeypatch.setattr(diagnostics.asyncio, "open_connection", fake_open)
        rtt = _run_async(tcp_rtt_ms("api.anthropic.com"))
        assert isinstance(rtt, int) and rtt >= 0

    def test_failure_is_none(self, monkeypatch):
        async def fake_open(host, port):
            raise OSError("refused")
        monkeypatch.setattr(diagnostics.asyncio, "open_connection", fake_open)
        assert _run_async(tcp_rtt_ms("api.anthropic.com")) is None


class TestEgressIp:
    def test_parses_ip(self):
        def handler(req):
            return httpx.Response(200, json={"ip": "203.0.113.7"})

        async def main():
            async with _client(handler) as c:
                return await egress_ip(c)
        assert _run_async(main()) == "203.0.113.7"

    def test_failure_is_none(self):
        def handler(req):
            raise httpx.ConnectError("down", request=req)

        async def main():
            async with _client(handler) as c:
                return await egress_ip(c)
        assert _run_async(main()) is None

    def test_non_200_is_none(self):
        def handler(req):
            return httpx.Response(500)

        async def main():
            async with _client(handler) as c:
                return await egress_ip(c)
        assert _run_async(main()) is None


class TestEnvironmentProfile:
    def _stub_net(self, monkeypatch, *, ip_ok=True):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _gai("1.2.3.4"))

        class FakeWriter:
            def close(self): pass
            async def wait_closed(self): pass

        async def fake_open(host, port):
            return (object(), FakeWriter())
        monkeypatch.setattr(diagnostics.asyncio, "open_connection", fake_open)

        def handler(req):
            return httpx.Response(200, json={"ip": "203.0.113.7"} if ip_ok else {})
        return handler

    def test_full_profile(self, monkeypatch):
        handler = self._stub_net(monkeypatch)

        async def main():
            async with _client(handler) as c:
                return await environment_profile(c)
        prof = _run_async(main())
        assert prof["egressIp"] == "203.0.113.7"
        assert len(prof["hosts"]) == len(PROVIDERS)
        h = prof["hosts"][0]
        assert h["resolvedIps"] == ["1.2.3.4"]
        assert isinstance(h["tcpRttMs"], int)

    def test_graceful_when_everything_fails(self, monkeypatch):
        def boom(*a, **k):
            raise socket.gaierror("nope")
        monkeypatch.setattr(socket, "getaddrinfo", boom)

        async def fake_open(host, port):
            raise OSError("refused")
        monkeypatch.setattr(diagnostics.asyncio, "open_connection", fake_open)

        def handler(req):
            raise httpx.ConnectError("down", request=req)

        async def main():
            async with _client(handler) as c:
                return await environment_profile(c)
        prof = _run_async(main())
        assert prof["egressIp"] is None
        for h in prof["hosts"]:
            assert h["resolvedIps"] is None and h["tcpRttMs"] is None


def test_diagnose_includes_profile_without_affecting_verdict(monkeypatch):
    claude = _claude()
    monkeypatch.setattr(diagnostics, "PROVIDERS", [claude])
    monkeypatch.setattr(claude, "key", lambda: "sk-test")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: _gai("1.2.3.4"))

    class FakeWriter:
        def close(self): pass
        async def wait_closed(self): pass

    async def fake_open(host, port):
        return (object(), FakeWriter())
    monkeypatch.setattr(diagnostics.asyncio, "open_connection", fake_open)

    def handler(req):
        # Key check + ipify both hit this; ipify path returns an ip.
        if "ipify" in str(req.url):
            return httpx.Response(200, json={"ip": "203.0.113.7"})
        return httpx.Response(200, json={"data": []})

    async def main():
        async with _client(handler) as c:
            return await diagnose(c, [{"name": "Claude", "status": "operational"}])

    result = _run_async(main())
    assert result["verdictKind"] == "all-clear"  # profile didn't change verdict
    assert result["profile"]["egressIp"] == "203.0.113.7"
    assert result["profile"]["hosts"][0]["resolvedIps"] == ["1.2.3.4"]
