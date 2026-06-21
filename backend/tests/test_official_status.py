"""Tests for official status-page integration."""
import json
from pathlib import Path

from app.official_status import (
    OfficialStatusState,
    is_relevant_to_monitored_models,
    parse_gemini_incidents,
    parse_statuspage_summary,
)
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
        assert sig["headline"] == "All systems operational"

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

    def test_minor_incident_openai(self):
        sig = parse_statuspage_summary(
            "GPT",
            "https://status.openai.com/",
            _load("status_openai_minor.json"),
        )
        assert sig["status"] == "degraded"
        assert sig["active"] is True
        assert sig["impactLabel"] == "Minor impact"
        assert "FedRAMP" in (sig["headline"] or "")

    def test_minor_incident_openai_filtered_for_probed_models(self):
        sig = parse_statuspage_summary(
            "GPT",
            "https://status.openai.com/",
            _load("status_openai_minor.json"),
            monitored_models=["gpt-5", "gpt-5-mini"],
        )
        assert sig["status"] == "operational"
        assert sig["active"] is False
        assert sig["headline"] == "All systems operational"

    def test_fable_incident_filtered_for_opus_sonnet(self):
        payload = {
            "components": [
                {"name": "Claude API (api.anthropic.com)", "status": "operational"},
            ],
            "incidents": [
                {
                    "name": "We've suspended access to Claude Mythos 5 and Claude Fable 5",
                    "status": "investigating",
                    "impact": "major",
                    "updated_at": "2026-06-21T12:00:00Z",
                    "incident_updates": [
                        {
                            "body": "Access to Mythos and Fable models is paused.",
                            "status": "investigating",
                        }
                    ],
                }
            ],
            "status": {"description": "Partial System Outage"},
        }
        sig = parse_statuspage_summary(
            "Claude",
            "https://status.claude.com/",
            payload,
            monitored_models=["claude-opus-4-8", "claude-sonnet-4-6"],
        )
        assert sig["status"] == "operational"
        assert sig["active"] is False
        assert sig["headline"] == "All systems operational"

    def test_operational_ignores_contradictory_page_banner(self):
        payload = {
            "components": [
                {"name": "Responses", "status": "operational"},
                {"name": "Fine-tuning", "status": "operational"},
            ],
            "incidents": [],
            "status": {"description": "Partial System Degradation"},
        }
        sig = parse_statuspage_summary(
            "GPT",
            "https://status.openai.com/",
            payload,
        )
        assert sig["status"] == "operational"
        assert sig["active"] is False
        assert sig["headline"] == "All systems operational"

    def test_opus_incident_still_surfaces(self):
        payload = {
            "components": [
                {"name": "Claude API (api.anthropic.com)", "status": "operational"},
            ],
            "incidents": [
                {
                    "name": "Elevated errors on Claude Opus",
                    "status": "investigating",
                    "impact": "minor",
                    "updated_at": "2026-06-21T12:00:00Z",
                    "incident_updates": [
                        {"body": "Investigating elevated Opus error rates.", "status": "investigating"}
                    ],
                }
            ],
        }
        sig = parse_statuspage_summary(
            "Claude",
            "https://status.claude.com/",
            payload,
            monitored_models=["claude-opus-4-8", "claude-sonnet-4-6"],
        )
        assert sig["active"] is True
        assert "Opus" in (sig["headline"] or "")


class TestModelRelevance:
    def test_fable_not_relevant_when_monitoring_opus_sonnet(self):
        text = "We've suspended access to Claude Mythos 5 and Claude Fable 5"
        assert not is_relevant_to_monitored_models(
            "Claude", text, ["claude-opus-4-8", "claude-sonnet-4-6"]
        )

    def test_generic_api_outage_is_relevant(self):
        assert is_relevant_to_monitored_models(
            "GPT", "Elevated errors on API", ["gpt-5", "gpt-5-mini"]
        )

    def test_fedramp_not_relevant_for_standard_api_models(self):
        assert not is_relevant_to_monitored_models(
            "GPT",
            "FedRAMP workspaces and API orgs have degraded performance",
            ["gpt-5", "gpt-5-mini"],
        )
    def test_operational_when_only_resolved_incidents(self):
        sig = parse_gemini_incidents(
            "https://aistudio.google.com/status",
            _load("status_gemini_operational.json"),
        )
        assert sig["status"] == "operational"
        assert sig["active"] is False
        assert sig["headline"] == "All Systems Operational"
        assert "API: operational" in (sig["componentSummary"] or "")

    def test_wire_format_operational(self):
        wire = [
            [
                [
                    "inc-resolved",
                    "Past issue",
                    1,
                    [[4, "2026-06-20", ["1"], "Resolved"]],
                    1,
                    [1],
                ]
            ]
        ]
        sig = parse_gemini_incidents("https://aistudio.google.com/status", wire)
        assert sig["status"] == "operational"
        assert sig["headline"] == "All Systems Operational"
        assert sig["componentSummary"]

    def test_wire_format_active_incident(self):
        wire = [
            [
                [
                    "inc-active",
                    "Elevated Gemini API errors",
                    1,
                    [[1, "2026-06-21 10:00", ["1"], "Investigating elevated errors."]],
                    1,
                    [1, 3],
                ]
            ]
        ]
        sig = parse_gemini_incidents("https://aistudio.google.com/status", wire)
        assert sig["status"] == "partial_outage"
        assert sig["active"] is True
        assert sig["headline"] == "Elevated Gemini API errors"
        assert sig["latestPhase"] == "detected"

    def test_partial_outage(self):
        sig = parse_gemini_incidents(
            "https://aistudio.google.com/status",
            _load("status_gemini_partial.json"),
        )
        assert sig["status"] == "partial_outage"
        assert sig["active"] is True
        assert sig["headline"] == "Elevated errors on Gemini API"
        assert sig["impactLabel"] == "Partial impact"
        assert sig["latestPhase"] == "update"
        assert "API" in (sig["componentSummary"] or "")

    def test_studio_only_incident_filtered(self):
        wire = [
            [
                [
                    "inc-studio",
                    "Google AI Studio login issues",
                    1,
                    [[1, "2026-06-21 10:00", ["1"], "Studio UI degraded."]],
                    1,
                    [3],
                ]
            ]
        ]
        sig = parse_gemini_incidents(
            "https://aistudio.google.com/status",
            wire,
            monitored_models=["gemini-2.5-pro", "gemini-2.5-flash"],
        )
        assert sig["status"] == "operational"
        assert sig["active"] is False

    def test_protobuf_payload(self):
        from app.official_status import _decode_gemini_protobuf

        # Minimal gRPC-web frame wrapping one partial-outage incident.
        title = b"Gemini API latency elevated"
        event = b"\x08\x01\x12\x1bWe are investigating latency."
        incident = (
            b"\x12"
            + bytes([len(title)])
            + title
            + b"\x18\x01"
            + b"\x22"
            + bytes([len(event)])
            + event
            + b"\x30\x01"
        )
        body = b"\x0a" + bytes([len(incident)]) + incident
        frame = b"\x00" + len(body).to_bytes(4, "big") + body
        sig = parse_gemini_incidents(
            "https://aistudio.google.com/status",
            _decode_gemini_protobuf(frame),
        )
        assert sig["status"] == "partial_outage"
        assert sig["headline"] == "Gemini API latency elevated"


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
