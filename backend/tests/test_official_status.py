"""Tests for official status-page integration."""
import json
from pathlib import Path

from app.official_status import OfficialStatusState, parse_statuspage_summary
from app.probes import _build_alerts

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestParseStatuspage:
    def test_operational_claude(self):
        sig = parse_statuspage_summary(
            "Claude",
            "https://status.claude.com/",
            _load("status_claude_operational.json"),
        )
        assert sig["status"] == "operational"
        assert sig["active"] is False
        assert sig["headline"] is None

    def test_major_incident_openai(self):
        sig = parse_statuspage_summary(
            "GPT",
            "https://status.openai.com/",
            _load("status_openai_major.json"),
        )
        assert sig["status"] == "major_outage"
        assert sig["active"] is True
        assert sig["headline"] == "Elevated errors on API"
        assert sig["impactLabel"] == "Major impact"
        assert sig["latestPhase"] == "monitoring"
        assert "monitoring the results" in (sig["latestUpdate"] or "")


class TestAlertFusion:
    def _impaired_gpt(self):
        return [
            {
                "id": "gpt-flagship",
                "name": "GPT",
                "status": "down",
                "healthScore": 0,
                "latencyMs": 5000,
                "qaCorrect": False,
            }
        ]

    def test_official_acknowledged_fusion(self):
        official = {
            "GPT": {
                "providerId": "GPT",
                "status": "major_outage",
                "headline": "Elevated errors on API",
                "latestUpdate": "Investigating",
                "latestPhase": "investigating",
                "impactLabel": "Major impact",
                "pageUrl": "https://status.openai.com/",
                "active": True,
            }
        }
        alerts = _build_alerts(self._impaired_gpt(), official=official)
        assert len(alerts) == 1
        assert alerts[0]["officialAcknowledged"] is True
        assert alerts[0]["fusionMode"] == "official_acknowledged"
        assert "Official status acknowledges" in alerts[0]["attribution"]
        assert alerts[0]["severity"] == "warning"

    def test_probe_ahead_of_official(self):
        official = {
            "GPT": {
                "providerId": "GPT",
                "status": "operational",
                "headline": None,
                "pageUrl": "https://status.openai.com/",
                "active": False,
            }
        }
        alerts = _build_alerts(self._impaired_gpt(), official=official)
        assert alerts[0]["fusionMode"] == "probe_ahead_of_official"
        assert "ahead of official acknowledgment" in alerts[0]["insight"]

    def test_official_only_alert(self):
        providers = [
            {
                "id": "gpt-flagship",
                "name": "GPT",
                "status": "operational",
                "healthScore": 95,
                "latencyMs": 800,
                "qaCorrect": True,
            }
        ]
        official = {
            "GPT": {
                "providerId": "GPT",
                "status": "degraded",
                "headline": "FedRAMP degraded",
                "latestUpdate": "Investigating",
                "latestPhase": "investigating",
                "pageUrl": "https://status.openai.com/",
                "active": True,
            }
        }
        alerts = _build_alerts(providers, official=official)
        assert any(a["fusionMode"] == "official_only" for a in alerts)


class TestOfficialStatusState:
    def test_signals_include_gemini_unavailable(self):
        state = OfficialStatusState(["Claude", "GPT", "Gemini"])
        sigs = state.signals()
        ids = [s["providerId"] for s in sigs]
        assert "Claude" in ids
        assert "GPT" in ids
        assert "Gemini" in ids
        gemini = next(s for s in sigs if s["providerId"] == "Gemini")
        assert gemini["status"] == "unavailable"
