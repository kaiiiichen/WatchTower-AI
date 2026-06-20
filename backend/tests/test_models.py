"""Tests for models.py: Pydantic model construction and validation."""
import pytest
from pydantic import ValidationError

from app.models import Alert, HealthSnapshot, LatencyPoint, ProviderHealth


class TestLatencyPoint:
    def test_valid(self):
        lp = LatencyPoint(t="2025-01-01T00:00:00Z", ms=150)
        assert lp.t == "2025-01-01T00:00:00Z"
        assert lp.ms == 150

    def test_missing_field(self):
        with pytest.raises(ValidationError):
            LatencyPoint(t="2025-01-01T00:00:00Z")


class TestProviderHealth:
    def _valid_kwargs(self, **overrides):
        defaults = {
            "id": "claude-flagship",
            "name": "Claude",
            "status": "operational",
            "healthScore": 98,
            "latencyMs": 400,
            "tokenRate": 74,
            "qaCorrect": True,
            "latencyHistory": [{"t": "2025-01-01T00:00:00Z", "ms": 400}],
        }
        defaults.update(overrides)
        return defaults

    def test_valid_minimal(self):
        p = ProviderHealth(**self._valid_kwargs())
        assert p.id == "claude-flagship"
        assert p.tier is None
        assert p.model is None

    def test_with_optional_fields(self):
        p = ProviderHealth(**self._valid_kwargs(tier="flagship", model="claude-opus-4"))
        assert p.tier == "flagship"
        assert p.model == "claude-opus-4"

    def test_all_statuses(self):
        for s in ("operational", "degraded", "down", "unknown"):
            p = ProviderHealth(**self._valid_kwargs(status=s))
            assert p.status == s

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            ProviderHealth(**self._valid_kwargs(status="exploded"))

    def test_invalid_tier(self):
        with pytest.raises(ValidationError):
            ProviderHealth(**self._valid_kwargs(tier="ultra"))

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            ProviderHealth(id="x", name="X")

    def test_empty_latency_history(self):
        p = ProviderHealth(**self._valid_kwargs(latencyHistory=[]))
        assert p.latencyHistory == []

    def test_serialization_camel_case(self):
        p = ProviderHealth(**self._valid_kwargs())
        d = p.model_dump()
        assert "healthScore" in d
        assert "latencyMs" in d
        assert "tokenRate" in d
        assert "qaCorrect" in d
        assert "latencyHistory" in d


class TestAlert:
    def _valid_kwargs(self, **overrides):
        defaults = {
            "id": "alert-claude-degraded",
            "severity": "warning",
            "providerId": "claude",
            "title": "Claude is degraded",
            "attribution": "Cloud-side.",
            "recoveryEta": "~10 min.",
            "recommendedAlternative": "Route to GPT.",
            "insight": "Latency spiked.",
            "createdAt": "2025-01-01T00:00:00Z",
        }
        defaults.update(overrides)
        return defaults

    def test_valid(self):
        a = Alert(**self._valid_kwargs())
        assert a.severity == "warning"

    def test_all_severities(self):
        for s in ("info", "warning", "critical"):
            a = Alert(**self._valid_kwargs(severity=s))
            assert a.severity == s

    def test_invalid_severity(self):
        with pytest.raises(ValidationError):
            Alert(**self._valid_kwargs(severity="panic"))

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            Alert(id="a", severity="info")


class TestHealthSnapshot:
    def test_valid(self):
        snap = HealthSnapshot(
            providers=[
                ProviderHealth(
                    id="claude", name="Claude", status="operational",
                    healthScore=98, latencyMs=400, tokenRate=74,
                    qaCorrect=True, latencyHistory=[],
                )
            ],
            alerts=[],
            updatedAt="2025-01-01T00:00:00Z",
        )
        assert len(snap.providers) == 1
        assert snap.updatedAt == "2025-01-01T00:00:00Z"

    def test_empty_providers(self):
        snap = HealthSnapshot(providers=[], alerts=[], updatedAt="2025-01-01T00:00:00Z")
        assert snap.providers == []

    def test_missing_updated_at(self):
        with pytest.raises(ValidationError):
            HealthSnapshot(providers=[], alerts=[])
