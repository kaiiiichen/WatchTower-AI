"""Official status-page source — authoritative provider acknowledgments.

Polls Statuspage JSON APIs (Claude + OpenAI) and surfaces what the provider has
publicly said. CORROBORATION + ATTRIBUTION layer: when the official page already
acknowledges an incident, alerts cite their wording instead of guessing.

PRINCIPLE: same as community.py — fetch/parse failures degrade to "unavailable"
and never touch the probe loop. Gemini has no stable public Statuspage API yet."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Callable

import httpx
import sentry_sdk

from . import config

log = logging.getLogger("watchtower.official_status")

# Statuspage impact -> human label (used in signal summaries).
IMPACT_LABELS = {
    "critical": "Critical impact",
    "major": "Major impact",
    "minor": "Minor impact",
}

COMPONENT_STATUS_RANK = {
    "operational": 0,
    "under_maintenance": 1,
    "degraded_performance": 2,
    "partial_outage": 3,
    "major_outage": 4,
}

COMPONENT_TO_SIGNAL = {
    "operational": "operational",
    "degraded_performance": "degraded",
    "partial_outage": "partial_outage",
    "major_outage": "major_outage",
    "under_maintenance": "maintenance",
}

STATUS_PAGES: dict[str, dict] = {
    "Claude": {
        "summary_url": "https://status.claude.com/api/v2/summary.json",
        "page_url": "https://status.claude.com/",
        "component_match": lambda name: "claude api" in name.lower()
        or "api.anthropic.com" in name.lower(),
    },
    "GPT": {
        "summary_url": "https://status.openai.com/api/v2/summary.json",
        "page_url": "https://status.openai.com/",
        "component_match": lambda name: name.lower() == "apis"
        or " api" in name.lower()
        or name.lower().startswith("api"),
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _impact_label(impact: str) -> str:
    return IMPACT_LABELS.get(impact, impact.capitalize() + " impact")


def _worst_component_status(components: list[dict], match: Callable[[str], bool]) -> str:
    matched = [c for c in components if match(c.get("name") or "")]
    pool = matched or components
    if not pool:
        return "operational"
    return max(pool, key=lambda c: COMPONENT_STATUS_RANK.get(c.get("status", ""), 0))[
        "status"
    ]


def _component_summary(components: list[dict], match: Callable[[str], bool]) -> str | None:
    matched = [c for c in components if match(c.get("name") or "")]
    if not matched:
        return None
    parts = [
        f"{c.get('name')}: {(c.get('status') or 'unknown').replace('_', ' ')}"
        for c in matched[:3]
    ]
    return "; ".join(parts)


def _latest_update(incident: dict) -> tuple[str | None, str | None]:
    updates = incident.get("incident_updates") or []
    if not updates:
        return incident.get("status"), None
    latest = updates[-1]
    return latest.get("status"), (latest.get("body") or "").strip() or None


def parse_statuspage_summary(provider: str, page_url: str, payload: dict) -> dict:
    """Turn a Statuspage summary.json into an OfficialStatusSignal dict."""
    meta = STATUS_PAGES[provider]
    components = payload.get("components") or []
    comp_status = _worst_component_status(components, meta["component_match"])
    signal_status = COMPONENT_TO_SIGNAL.get(comp_status, "operational")

    incidents = payload.get("incidents") or []
    headline: str | None = None
    latest_phase: str | None = None
    latest_update: str | None = None
    impact_label: str | None = None

    if incidents:
        # Summary API lists active incidents; take the most recently updated.
        incident = max(
            incidents,
            key=lambda i: i.get("updated_at") or i.get("created_at") or "",
        )
        headline = (incident.get("name") or "").strip() or None
        latest_phase, latest_update = _latest_update(incident)
        impact = incident.get("impact") or "none"
        if impact != "none":
            impact_label = _impact_label(impact)
        # An active incident elevates the headline status even if components lag.
        if signal_status == "operational" and latest_phase not in (None, "resolved"):
            signal_status = "degraded"

    active = signal_status != "operational" or bool(headline)

    return {
        "providerId": provider,
        "status": signal_status,
        "headline": headline,
        "latestUpdate": latest_update,
        "latestPhase": latest_phase,
        "impactLabel": impact_label,
        "componentSummary": _component_summary(components, meta["component_match"]),
        "pageUrl": page_url,
        "active": active,
        "sampledAt": _now_iso(),
    }


async def fetch_summary(client: httpx.AsyncClient, url: str) -> dict | None:
    try:
        r = await client.get(url, headers={"Accept": "application/json"})
        if r.status_code != 200:
            log.warning("status page %s HTTP %s", url, r.status_code)
            return None
        return r.json()
    except Exception as exc:
        log.warning("status page %s fetch failed: %s", url, exc)
        return None


def _unavailable_signal(provider: str, page_url: str | None = None) -> dict:
    return {
        "providerId": provider,
        "status": "unavailable",
        "headline": None,
        "latestUpdate": None,
        "latestPhase": None,
        "impactLabel": None,
        "componentSummary": None,
        "pageUrl": page_url or "",
        "active": False,
        "sampledAt": None,
    }


class OfficialStatusState:
    """Cached official status signals per provider."""

    def __init__(self, provider_names: list[str]) -> None:
        self._providers = [n for n in provider_names if n in STATUS_PAGES]
        # Gemini: no stable Statuspage JSON — surface as unavailable in signals().
        self._gemini = "Gemini" in provider_names
        self._latest: dict[str, dict] = {
            n: _unavailable_signal(n, STATUS_PAGES[n]["page_url"]) for n in self._providers
        }
        self._last_poll: dict[str, float] = {}

    async def _poll_one(self, client: httpx.AsyncClient, provider: str) -> dict:
        meta = STATUS_PAGES[provider]
        payload = await fetch_summary(client, meta["summary_url"])
        if payload is None:
            return _unavailable_signal(provider, meta["page_url"])
        return parse_statuspage_summary(provider, meta["page_url"], payload)

    async def poll(self, client: httpx.AsyncClient) -> None:
        now = time.monotonic()
        for provider in self._providers:
            last = self._last_poll.get(provider)
            if last is not None and now - last < config.OFFICIAL_STATUS_INTERVAL:
                continue
            try:
                self._latest[provider] = await self._poll_one(client, provider)
            except Exception:
                log.exception("official status poll failed for %s", provider)
                sentry_sdk.capture_exception()
                self._latest[provider] = _unavailable_signal(
                    provider, STATUS_PAGES[provider]["page_url"]
                )
            self._last_poll[provider] = time.monotonic()

    def signals(self) -> list[dict]:
        out = [self._latest[n] for n in self._providers]
        if self._gemini:
            out.append(_unavailable_signal("Gemini", "https://aistudio.google.com/status"))
        return out

    def by_provider(self) -> dict[str, dict]:
        m = dict(self._latest)
        if self._gemini:
            m["Gemini"] = _unavailable_signal("Gemini", "https://aistudio.google.com/status")
        return m
