"""Sentry integration for WatchTower AI.

- init_sentry(): initialise the SDK (no-op without SENTRY_DSN).
- report_incidents(): for each degraded/down provider, send a Sentry event
  (Layer 1) with intelligent fingerprinting (Layer 2) so repeated probe cycles
  of the same model+anomaly collapse into a single issue — no alert storm.

When Sentry isn't initialised (no DSN, e.g. in tests), every sentry_sdk call
here is a safe no-op, so the backend runs normally without Sentry."""
from __future__ import annotations

import logging

import sentry_sdk

from . import config
from .redaction import scrub

log = logging.getLogger("watchtower.monitoring")


def _before_send(event, _hint):
    """Redact `key=...` query values from every string in an outgoing event.
    Covers error events: breadcrumbs, request.url, exception messages, etc."""
    return scrub(event)


def _before_send_transaction(event, _hint):
    """Same redaction for performance transactions — the httpx integration puts
    the probed URL (with Gemini's `?key=`) in span descriptions and data."""
    return scrub(event)

# Provider status -> Sentry event level.
_LEVEL = {"degraded": "warning", "down": "error"}


def init_sentry() -> bool:
    """Initialise Sentry if a DSN is configured. Returns True if initialised.

    Note: the spec used os.environ["SENTRY_DSN"] directly; we guard on a missing
    DSN instead so the backend still boots locally / in CI without Sentry."""
    if not config.SENTRY_DSN:
        log.info("SENTRY_DSN not set; Sentry disabled (events/traces are no-ops)")
        return False
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        environment=config.SENTRY_ENVIRONMENT,
        traces_sample_rate=config.SENTRY_TRACES_SAMPLE_RATE,
        # Strip Gemini's `?key=...` from URLs before anything leaves the process.
        before_send=_before_send,
        before_send_transaction=_before_send_transaction,
    )
    log.info("Sentry initialised (environment=%s)", config.SENTRY_ENVIRONMENT)
    return True


def _attribution_scope(p: dict, providers: list[dict]) -> str:
    """Short attribution category for tagging (sibling-aware, low cardinality)."""
    siblings = [q for q in providers if q["name"] == p["name"] and q["id"] != p["id"]]
    if any(q["status"] == "operational" for q in siblings):
        return "model-specific"
    if siblings:  # other tiers exist, none healthy
        return "provider-wide"
    if any(q["status"] == "operational" for q in providers):
        return "cloud-side"
    return "inconclusive"


def build_incident_event(p: dict, providers: list[dict], detected_at: str) -> dict:
    """Build the Sentry event dict for an impaired provider (Layers 1 + 2).
    Pure — no SDK calls — so it's unit-testable without initialising Sentry."""
    anomaly_type = p["status"]  # "degraded" | "down"
    scope = _attribution_scope(p, providers)
    return {
        "message": f"{p['name']} {p.get('tier', '')} ({p.get('model', '?')}) {anomaly_type}",
        "level": _LEVEL[anomaly_type],
        "tags": {
            "provider": p["name"],
            "tier": p.get("tier"),
            "anomaly_type": anomaly_type,
            "attribution": scope,
        },
        "extra": {
            "health_score": p["healthScore"],
            "latency_ms": p["latencyMs"],
            "qa_probe": "pass" if p["qaCorrect"] else "fail",
            "model": p.get("model"),
            "detected_at": detected_at,
        },
        # Layer 2: group by probe target + anomaly type. Repeated cycles of the
        # same model+anomaly collapse into ONE issue (no storm); a provider's
        # flagship and mid stay distinct issues since the models genuinely differ.
        "fingerprint": [p["id"], anomaly_type],
    }


def report_incident(p: dict, providers: list[dict], detected_at: str) -> None:
    """Capture one Sentry event for an impaired provider (Layers 1 + 2)."""
    sentry_sdk.capture_event(build_incident_event(p, providers, detected_at))


def report_incidents(providers: list[dict], detected_at: str) -> int:
    """Report every degraded/down provider. Returns how many events were sent."""
    count = 0
    for p in providers:
        if p["status"] not in _LEVEL:
            continue
        try:
            report_incident(p, providers, detected_at)
            count += 1
        except Exception:  # never let monitoring break the probe loop
            log.exception("failed to report incident for %s", p.get("id"))
    if count:
        log.info("reported %d incident(s) to Sentry", count)
    return count
