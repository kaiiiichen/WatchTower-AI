"""Offline tests for Sentry incident reporting (Layers 1 + 2).

These assert the event payload built by monitoring.build_incident_event without
initialising the SDK, so no DSN / network is needed and no global Sentry state
leaks into other tests. Layer 3 (transaction/spans) is covered by integration
verification (a live probe cycle), since spans require an initialised client."""
from app import monitoring


def _prov(pid, name, status, tier, model, score, latency=1000, qa=False):
    return {
        "id": pid, "name": name, "status": status, "healthScore": score,
        "latencyMs": latency, "qaCorrect": qa, "tier": tier, "model": model,
    }


def test_down_event_payload():
    providers = [
        _prov("claude-flagship", "Claude", "operational", "flagship", "claude-opus-4-8", 99, qa=True),
        _prov("gemini-flagship", "Gemini", "down", "flagship", "gemini-3.1-pro", 0, 0),
    ]
    ev = monitoring.build_incident_event(providers[1], providers, "2026-06-21T00:00:00Z")
    assert ev["level"] == "error"
    assert ev["tags"]["provider"] == "Gemini"
    assert ev["tags"]["anomaly_type"] == "down"
    assert ev["tags"]["attribution"] == "cloud-side"  # sibling-less, others healthy
    assert ev["extra"]["health_score"] == 0
    assert ev["extra"]["qa_probe"] == "fail"
    assert ev["fingerprint"] == ["gemini-flagship", "down"]


def test_degraded_is_warning_and_model_specific():
    providers = [
        _prov("claude-flagship", "Claude", "operational", "flagship", "claude-opus-4-8", 99, qa=True),
        _prov("claude-mid", "Claude", "degraded", "mid", "claude-sonnet-4-6", 55, 3000),
    ]
    ev = monitoring.build_incident_event(providers[1], providers, "t")
    assert ev["level"] == "warning"
    assert ev["tags"]["attribution"] == "model-specific"  # healthy sibling tier
    assert ev["fingerprint"] == ["claude-mid", "degraded"]


def test_attribution_scopes():
    scope = monitoring._attribution_scope
    flagship_up = _prov("c-f", "Claude", "operational", "flagship", "m", 99, qa=True)
    mid_down = _prov("c-m", "Claude", "down", "mid", "m2", 0, 0)
    gpt_up = _prov("g-f", "GPT", "operational", "flagship", "g", 95, qa=True)

    # healthy sibling -> model-specific
    assert scope(mid_down, [flagship_up, mid_down]) == "model-specific"
    # all tiers of provider down -> provider-wide
    flagship_down = _prov("c-f", "Claude", "down", "flagship", "m", 0, 0)
    assert scope(mid_down, [flagship_down, mid_down]) == "provider-wide"
    # no sibling, another provider healthy -> cloud-side
    assert scope(mid_down, [mid_down, gpt_up]) == "cloud-side"
    # nothing healthy, no sibling -> inconclusive
    assert scope(mid_down, [mid_down]) == "inconclusive"


def test_report_incidents_counts_only_impaired():
    providers = [
        _prov("claude-flagship", "Claude", "operational", "flagship", "m", 99, qa=True),
        _prov("gemini-flagship", "Gemini", "down", "flagship", "g", 0, 0),
        _prov("gpt-flagship", "GPT", "degraded", "flagship", "x", 60, 2500),
    ]
    # Sentry not initialised here -> capture_event is a safe no-op; we assert the
    # count of impaired providers that would be reported.
    assert monitoring.report_incidents(providers, "t") == 2


def test_init_sentry_noop_without_dsn(monkeypatch):
    monkeypatch.setattr(monitoring.config, "SENTRY_DSN", None)
    assert monitoring.init_sentry() is False
