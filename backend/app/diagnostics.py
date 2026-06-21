"""Local environment diagnostics — the product's core question: *is it your
problem or the service's?*

Three checks per configured provider:
  - DNS: can this machine resolve the provider host?
  - TCP: can it open a socket to :443?
  - KEY: does a minimal authenticated request come back 200 (vs 401/403/400)?

Then one verdict that fuses the local result with the probe layer:
  - local all green + a provider's probe is anomalous -> "it's {provider}'s problem, not yours"
  - any local check red (DNS/TCP/key)               -> "it's your side: {what failed}"

PRINCIPLE: every check is wrapped so a failure degrades to "unknown" (and the
verdict to "indeterminate") — diagnostics never crashes /diagnose or the app."""
from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable

import httpx

from . import config

log = logging.getLogger("watchtower.diagnostics")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class _DiagProvider:
    name: str
    host: str
    key: Callable[[], str | None]
    key_check: Callable[[httpx.AsyncClient], Awaitable[httpx.Response]]


# Minimal, cheap authenticated requests (list-models) to validate the key without
# spending generation quota. Key material is read at call time from config.
PROVIDERS: list[_DiagProvider] = [
    _DiagProvider(
        name="Claude",
        host="api.anthropic.com",
        key=lambda: config.ANTHROPIC_API_KEY,
        key_check=lambda c: c.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": config.ANTHROPIC_API_KEY or "",
                "anthropic-version": "2023-06-01",
            },
        ),
    ),
    _DiagProvider(
        name="GPT",
        host="api.openai.com",
        key=lambda: config.OPENAI_API_KEY,
        key_check=lambda c: c.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {config.OPENAI_API_KEY or ''}"},
        ),
    ),
    _DiagProvider(
        name="Gemini",
        host="generativelanguage.googleapis.com",
        key=lambda: config.GEMINI_API_KEY,
        # Gemini takes the key as a query param (kept out of logs by redaction).
        key_check=lambda c: c.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": config.GEMINI_API_KEY or ""},
        ),
    ),
]


def _check(provider: str, check: str, status: str, detail: str) -> dict:
    return {"provider": provider, "check": check, "status": status, "detail": detail}


async def check_dns(provider: str, host: str) -> dict:
    """Can we resolve the host? Blocking getaddrinfo runs in a thread."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None, lambda: socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        )
        return _check(provider, "dns", "pass", f"resolved {host}")
    except socket.gaierror:
        return _check(provider, "dns", "fail", f"DNS resolution failed for {host}")
    except Exception as exc:  # never crash a check
        return _check(provider, "dns", "unknown", f"DNS check error: {type(exc).__name__}")


async def check_tcp(provider: str, host: str, port: int = 443) -> dict:
    """Can we open a TCP socket to host:443? (open_connection resolves too, but
    DNS is reported separately so the user sees which layer broke.)"""
    writer = None
    try:
        fut = asyncio.open_connection(host, port)
        _, writer = await asyncio.wait_for(fut, timeout=config.DIAGNOSTIC_TIMEOUT)
        return _check(provider, "tcp", "pass", f"connected to {host}:{port}")
    except (asyncio.TimeoutError, OSError):
        return _check(provider, "tcp", "fail", f"cannot connect to {host}:{port}")
    except Exception as exc:
        return _check(provider, "tcp", "unknown", f"TCP check error: {type(exc).__name__}")
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


def _classify_key(code: int) -> tuple[str, str]:
    """Map a key-check HTTP status to (status, detail). Distinguishes an invalid
    key (your problem) from a reachable-but-throttled or provider-side error."""
    if code == 200:
        return "pass", "key valid (HTTP 200)"
    if code == 429:
        # Authenticated but throttled -> the key itself works.
        return "pass", "key valid but rate-limited (HTTP 429)"
    if code == 401:
        return "fail", "key invalid / unauthorized (HTTP 401)"
    if code == 403:
        return "fail", "key lacks permission (HTTP 403)"
    if code == 400:
        return "fail", "key rejected (HTTP 400)"
    if code >= 500:
        return "unknown", f"provider error (HTTP {code}) — can't judge the key"
    return "unknown", f"unexpected HTTP {code}"


async def check_key(client: httpx.AsyncClient, prov: _DiagProvider) -> dict:
    """Minimal authenticated request. A network failure here is reported as
    'unknown' (not a key failure) so we don't blame the key for a dead network."""
    try:
        r = await prov.key_check(client)
    except Exception as exc:
        return _check(
            prov.name, "key", "unknown",
            f"couldn't reach provider ({type(exc).__name__}) — network, not key",
        )
    status, detail = _classify_key(r.status_code)
    return _check(prov.name, "key", status, detail)


async def diagnose_provider(client: httpx.AsyncClient, prov: _DiagProvider) -> list[dict]:
    """Run DNS + TCP (always) and KEY (only if a key is configured)."""
    coros = [check_dns(prov.name, prov.host), check_tcp(prov.name, prov.host)]
    if prov.key():
        coros.append(check_key(client, prov))
    return list(await asyncio.gather(*coros))


def _local_health(checks: list[dict]) -> bool | None:
    """True = all pass, False = any fail, None = inconclusive (some unknown)."""
    if any(c["status"] == "fail" for c in checks):
        return False
    if any(c["status"] == "unknown" for c in checks):
        return None
    return True


def build_verdict(checks: list[dict], anomalies: list[str]) -> dict:
    """Fuse local checks + probe anomalies into the attribution sentence.

    `anomalies` = provider names whose probe shows a genuine SERVICE fault
    (down/degraded). rate_limited/misconfigured are already self-attributed by
    the probe layer, so they're not passed here."""
    if not checks:
        return {
            "localHealthy": None,
            "verdictKind": "indeterminate",
            "verdict": "No configured providers to diagnose — set an API key first.",
        }

    local = _local_health(checks)

    if local is False:
        reasons = "; ".join(
            f"{c['provider']} {c['check'].upper()} — {c['detail']}"
            for c in checks
            if c["status"] == "fail"
        )
        return {
            "localHealthy": False,
            "verdictKind": "your-side",
            "verdict": f"It's on your side: {reasons}.",
        }

    if local is None:
        unknowns = ", ".join(
            f"{c['provider']} {c['check'].upper()}"
            for c in checks
            if c["status"] == "unknown"
        )
        return {
            "localHealthy": None,
            "verdictKind": "indeterminate",
            "verdict": f"Couldn't fully determine — inconclusive checks: {unknowns}. Treat as unverified.",
        }

    # Local all green.
    if anomalies:
        who = ", ".join(dict.fromkeys(anomalies))  # dedupe, keep order
        return {
            "localHealthy": True,
            "verdictKind": "service-side",
            "verdict": f"Your environment is healthy — it's {who}'s problem, not yours.",
        }
    return {
        "localHealthy": True,
        "verdictKind": "all-clear",
        "verdict": "All clear — your environment and every probed service look healthy.",
    }


async def diagnose(client: httpx.AsyncClient, anomalies: list[str] | None = None) -> dict:
    """Run diagnostics for every key-configured provider + build the verdict.
    Never raises — provider-level errors degrade to 'unknown' checks."""
    anomalies = anomalies or []
    configured = [p for p in PROVIDERS if p.key()]
    results = await asyncio.gather(
        *(diagnose_provider(client, p) for p in configured), return_exceptions=True
    )
    checks: list[dict] = []
    for prov, res in zip(configured, results):
        if isinstance(res, BaseException):
            log.warning("diagnostics for %s failed: %s", prov.name, res)
            checks.append(_check(prov.name, "key", "unknown", "diagnostic error"))
        else:
            checks.extend(res)

    verdict = build_verdict(checks, anomalies)
    return {"checks": checks, "checkedAt": _now_iso(), **verdict}
