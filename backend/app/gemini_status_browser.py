"""Gemini AI Studio official status — headless-browser adapter (isolated).

Google blocks server-side HTTP calls to MakerSuiteService/ListIncidentsHistory.
This module opens the public status page in Chromium and captures the same RPC
response the UI uses. No screenshots or vision models.

Removal: delete this file, drop the import in official_status.py, and remove the
shutdown hook in main.py. Toggle without deleting: GEMINI_STATUS_BROWSER=0.

Setup: pip install playwright && playwright install chromium
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from . import config

log = logging.getLogger("watchtower.gemini_status_browser")

STATUS_PAGE_URL = "https://aistudio.google.com/status"
RPC_PATH_FRAGMENT = "ListIncidentsHistory"

_playwright: Any | None = None
_browser: Any | None = None
_lock = asyncio.Lock()


def enabled() -> bool:
    return config.GEMINI_STATUS_BROWSER


def available() -> bool:
    """True when the feature is on and playwright is importable."""
    if not enabled():
        return False
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return True


def _parse_rpc_body(raw: bytes, content_type: str = "") -> Any:
    """Return JSON (dict/list) or raw bytes for protobuf decoding upstream."""
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace").lstrip(")]}'\n")
    if "json" in content_type.lower() or text[:1] in "[{":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return raw


async def _ensure_browser():
    global _playwright, _browser
    if _browser is not None:
        return _browser
    async with _lock:
        if _browser is not None:
            return _browser
        from playwright.async_api import async_playwright

        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(headless=True)
        log.info("Gemini status browser started (headless Chromium)")
        return _browser


async def shutdown() -> None:
    """Release browser resources — call from app lifespan teardown."""
    global _playwright, _browser
    async with _lock:
        if _browser is not None:
            await _browser.close()
            _browser = None
        if _playwright is not None:
            await _playwright.stop()
            _playwright = None


async def fetch_incidents() -> Any | None:
    """Load AI Studio status page and return ListIncidentsHistory payload."""
    if not enabled():
        return None
    if not available():
        log.warning(
            "Gemini browser status enabled but playwright missing "
            "(pip install playwright && playwright install chromium)"
        )
        return None

    timeout_ms = int(config.GEMINI_STATUS_BROWSER_TIMEOUT * 1000)
    page = None
    try:
        browser = await _ensure_browser()
        page = await browser.new_page()

        def _is_incidents_rpc(response) -> bool:
            return (
                response.request.method == "POST"
                and RPC_PATH_FRAGMENT in response.url
            )

        async with page.expect_response(_is_incidents_rpc, timeout=timeout_ms) as pending:
            await page.goto(STATUS_PAGE_URL, wait_until="domcontentloaded", timeout=timeout_ms)

        response = await pending.value
        if response.status != 200:
            log.warning("Gemini status RPC HTTP %s", response.status)
            return None
        raw = await response.body()
        content_type = response.headers.get("content-type", "")
        payload = _parse_rpc_body(raw, content_type)
        if payload is None:
            log.warning("Gemini status RPC returned empty body")
        return payload
    except Exception as exc:
        log.warning("Gemini browser status fetch failed: %s", exc)
        return None
    finally:
        if page is not None:
            await page.close()
