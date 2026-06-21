"""Official status-page source — authoritative provider acknowledgments.

Polls Statuspage JSON APIs (Claude + OpenAI) and the Google AI Studio MakerSuite
RPC (Gemini). Surfaces what the provider has publicly said. CORROBORATION +
ATTRIBUTION layer: when the official page already acknowledges an incident, alerts
cite their wording instead of guessing.

PRINCIPLE: same as community.py — fetch/parse failures degrade to "unavailable"
and never touch the probe loop."""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable

import httpx
import sentry_sdk

from . import config

log = logging.getLogger("watchtower.official_status")

# Statuspage impact -> human label (used in signal summaries).
IMPACT_LABELS = {
    "none": None,
    "minor": "Minor impact",
    "major": "Major impact",
    "critical": "Critical impact",
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

STATUSPAGE_PROVIDERS: dict[str, dict] = {
    "Claude": {
        "summary_url": "https://status.claude.com/api/v2/summary.json",
        "page_url": "https://status.claude.com/",
        "component_match": lambda name: "claude api" in name.lower()
        or "api.anthropic.com" in name.lower(),
    },
    "GPT": {
        "summary_url": "https://status.openai.com/api/v2/summary.json",
        "page_url": "https://status.openai.com/",
        # OpenAI split "APIs" into per-surface components; keep probe-relevant ones.
        "component_match": lambda name: name.lower()
        in {
            "responses",
            "realtime",
            "batch",
            "fine-tuning",
            "codex api",
            "conversations",
            "agent",
            "files",
            "file uploads",
        }
        or name.lower().endswith(" api"),
    },
}

GEMINI_STATUS = {
    "provider": "Gemini",
    "page_url": "https://aistudio.google.com/status",
}

# MakerSuite incident severity (field 3 on lVe).
GEMINI_SEVERITY_PARTIAL = 1
GEMINI_SEVERITY_MAJOR = 2

# MakerSuite event phase (field 1 on XUe) -> Statuspage-like phase labels.
GEMINI_PHASE_LABELS = {
    0: "",
    1: "detected",
    2: "identified",
    3: "mitigated",
    4: "resolved",
    5: "update",
}

# MakerSuite service tags (field 6 on lVe).
GEMINI_SERVICES = {
    0: "Unspecified",
    1: "API",
    2: "Multimodal Live API",
    3: "Google AI Studio",
}

# Status-page text that targets products we never probe (even when no model name appears).
NON_PROBE_PHRASES: dict[str, tuple[str, ...]] = {
    "Claude": (
        "claude code",
        "cowork",
        "claude for government",
    ),
    "GPT": ("fedramp",),
    "Gemini": (),
}

CLAUDE_MODEL_FAMILIES = ("opus", "sonnet", "haiku", "fable", "mythos")

# MakerSuite service tags that map to our Gemini generateContent probes.
GEMINI_PROBE_SERVICE_TAGS = {1}  # API


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _impact_label(impact: str) -> str | None:
    return IMPACT_LABELS.get(impact)


def _monitored_families(provider: str, model_ids: list[str]) -> set[str]:
    """Derive searchable family tokens from the models we actually probe."""
    families: set[str] = set()
    for mid in model_ids:
        m = mid.lower()
        if provider == "Claude":
            for fam in CLAUDE_MODEL_FAMILIES:
                if fam in m:
                    families.add(fam)
        elif provider == "GPT":
            if m.startswith("gpt"):
                families.add("gpt")
            if "mini" in m:
                families.add("mini")
            if "nano" in m:
                families.add("nano")
            if re.search(r"\bo\d", m):
                families.add("o-series")
        elif provider == "Gemini":
            if m.startswith("gemini"):
                families.add("gemini")
            if "flash" in m:
                families.add("flash")
            if "pro" in m:
                families.add("pro")
            if "lite" in m:
                families.add("lite")
    return families


def _mentioned_families(provider: str, text: str) -> set[str]:
    """Families explicitly named in status-page copy."""
    t = text.lower()
    found: set[str] = set()
    if provider == "Claude":
        for fam in CLAUDE_MODEL_FAMILIES:
            if fam in t:
                found.add(fam)
    elif provider == "GPT":
        if re.search(r"\bgpt[\s\-]?\d", t) or "chatgpt" in t:
            found.add("gpt")
        if re.search(r"\bo[\s\-]?\d", t):
            found.add("o-series")
        if re.search(r"\bmini\b", t) and "gpt" in t:
            found.add("mini")
        if re.search(r"\bnano\b", t) and "gpt" in t:
            found.add("nano")
    elif provider == "Gemini":
        if "gemini" in t:
            found.add("gemini")
        if re.search(r"\bflash\b", t):
            found.add("flash")
        if re.search(r"\bpro\b", t):
            found.add("pro")
        if re.search(r"\blite\b", t):
            found.add("lite")
    return found


def _incident_text(incident: dict) -> str:
    parts = [(incident.get("name") or "").strip()]
    for upd in incident.get("incident_updates") or []:
        parts.append((upd.get("body") or "").strip())
    return "\n".join(p for p in parts if p)


def is_relevant_to_monitored_models(
    provider: str, text: str, monitored_models: list[str] | None
) -> bool:
    """True when status-page copy is about models/services we probe.

    - Generic API outages (no specific model named) -> relevant.
    - Names only non-monitored families (e.g. Fable when probing Opus) -> not relevant.
    - Names at least one monitored family -> relevant.
    - Known non-probe products (FedRAMP, Claude Code, …) -> not relevant.
    """
    if not monitored_models:
        return True
    if not (text or "").strip():
        return True

    lower = text.lower()
    for phrase in NON_PROBE_PHRASES.get(provider, ()):
        if phrase in lower:
            return False

    monitored = _monitored_families(provider, monitored_models)
    mentioned = _mentioned_families(provider, text)
    if not mentioned:
        return True
    return bool(mentioned & monitored)


def _filter_statuspage_incidents(
    provider: str, incidents: list[dict], monitored_models: list[str] | None
) -> list[dict]:
    if not monitored_models:
        return incidents
    return [
        inc
        for inc in incidents
        if is_relevant_to_monitored_models(provider, _incident_text(inc), monitored_models)
    ]


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


def parse_statuspage_summary(
    provider: str,
    page_url: str,
    payload: dict,
    *,
    monitored_models: list[str] | None = None,
) -> dict:
    """Turn a Statuspage summary.json into an OfficialStatusSignal dict."""
    meta = STATUSPAGE_PROVIDERS[provider]
    components = payload.get("components") or []
    comp_status = _worst_component_status(components, meta["component_match"])
    signal_status = COMPONENT_TO_SIGNAL.get(comp_status, "operational")

    incidents = _filter_statuspage_incidents(
        provider, payload.get("incidents") or [], monitored_models
    )
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
        impact_label = _impact_label(impact)
        # An active incident elevates the headline status even if components lag.
        if signal_status == "operational" and latest_phase not in (None, "resolved"):
            signal_status = "degraded"

    active = signal_status != "operational" or bool(headline)
    comp_summary = _component_summary(components, meta["component_match"])
    if not active:
        # Probed components are clear and no relevant incident — ignore the page-level
        # banner (e.g. OpenAI "Partial System Degradation" for unrelated surfaces).
        headline = "All systems operational"

    return {
        "providerId": provider,
        "status": signal_status,
        "headline": headline,
        "latestUpdate": latest_update,
        "latestPhase": latest_phase,
        "impactLabel": impact_label,
        "componentSummary": comp_summary,
        "pageUrl": page_url,
        "active": active,
        "sampledAt": _now_iso(),
    }


def _pb_get(obj: dict | None, *keys: str | int) -> Any:
    if not isinstance(obj, dict):
        return None
    for key in keys:
        if key in obj:
            return obj[key]
        skey = str(key)
        if skey in obj:
            return obj[skey]
    return None


def _pb_list(obj: dict | None, field: str | int) -> list:
    val = _pb_get(obj, field)
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def _event_timestamp(event: dict) -> float:
    ts = _pb_get(event, "timestamp", 3)
    if isinstance(ts, dict):
        seconds = _pb_get(ts, "seconds") or 0
        nanos = _pb_get(ts, "nanos") or 0
        try:
            return float(seconds) + float(nanos) / 1_000_000_000
        except (TypeError, ValueError):
            return 0.0
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


def _normalize_gemini_incidents(payload: Any) -> list[dict]:
    """Extract incident objects from MakerSuite ListIncidentsHistory payloads."""
    if isinstance(payload, bytes):
        return _decode_gemini_protobuf(payload)

    wire = _find_gemini_wire_incidents(payload)
    if wire:
        return [_wire_incident_to_dict(inc) for inc in wire]

    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict):
            if _pb_list(payload[0], 1):
                return _pb_list(payload[0], 1)
            return [item for item in payload if isinstance(item, dict)]
        return []
    if not isinstance(payload, dict):
        return []

    for key in ("incidents", "1"):
        incidents = payload.get(key)
        if isinstance(incidents, list):
            return incidents
        if isinstance(incidents, dict):
            return [incidents]

    if _pb_get(payload, "id", "title", 1, 2):
        return [payload]
    return _pb_list(payload, 1)


def _find_gemini_wire_incidents(payload: Any) -> list[list] | None:
    """Browser JSON+protobuf nests incidents as [[id, title, severity, events, …]]."""

    def walk(node: Any) -> list[list] | None:
        if not isinstance(node, list) or not node:
            return None
        if isinstance(node[0], str) and len(node) >= 4:
            return [node]
        if isinstance(node[0], list) and node[0] and isinstance(node[0][0], str):
            return node
        for item in node:
            found = walk(item)
            if found:
                return found
        return None

    return walk(payload)


def _wire_event_to_dict(event: list) -> dict:
    return {
        "1": event[0] if event else None,
        "3": event[1] if len(event) > 1 else None,
        "4": event[3] if len(event) > 3 else "",
    }


def _wire_incident_to_dict(incident: list) -> dict:
    services = incident[5] if len(incident) > 5 else []
    if not isinstance(services, list):
        services = [services]
    events_raw = incident[3] if len(incident) > 3 else []
    return {
        "1": incident[0],
        "2": incident[1],
        "3": incident[2],
        "4": [
            _wire_event_to_dict(ev)
            for ev in events_raw
            if isinstance(ev, list)
        ],
        "6": services,
    }


def _gemini_operational_components() -> str:
    return "; ".join(
        f"{GEMINI_SERVICES[k]}: operational"
        for k in sorted(GEMINI_SERVICES)
        if k != 0
    )


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, pos
        shift += 7
    raise ValueError("truncated varint")


def _parse_proto_fields(data: bytes) -> dict[int, list[Any]]:
    pos = 0
    fields: dict[int, list[Any]] = {}
    while pos < len(data):
        tag, pos = _read_varint(data, pos)
        field_num = tag >> 3
        wire_type = tag & 0x07
        if wire_type == 0:
            val, pos = _read_varint(data, pos)
        elif wire_type == 2:
            length, pos = _read_varint(data, pos)
            val = data[pos : pos + length]
            pos += length
        else:
            break
        fields.setdefault(field_num, []).append(val)
    return fields


def _decode_gemini_event(data: bytes) -> dict:
    fields = _parse_proto_fields(data)
    phase_vals = fields.get(1, [])
    ts_vals = fields.get(3, [])
    desc_vals = fields.get(4, [])
    event: dict[str, Any] = {}
    if phase_vals:
        event["1"] = phase_vals[0]
    if desc_vals:
        raw = desc_vals[0]
        event["4"] = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    if ts_vals:
        ts_raw = ts_vals[0]
        if isinstance(ts_raw, bytes):
            ts_fields = _parse_proto_fields(ts_raw)
            seconds = ts_fields.get(1, [0])[0]
            event["3"] = datetime.fromtimestamp(int(seconds), tz=timezone.utc).isoformat()
        else:
            event["3"] = ts_raw
    return event


def _decode_gemini_incident(data: bytes) -> dict:
    fields = _parse_proto_fields(data)
    incident: dict[str, Any] = {}
    if vals := fields.get(1):
        raw = vals[0]
        incident["1"] = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    if vals := fields.get(2):
        raw = vals[0]
        incident["2"] = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    if vals := fields.get(3):
        incident["3"] = vals[0]
    if vals := fields.get(5):
        incident["5"] = vals[0]
    if vals := fields.get(6):
        incident["6"] = list(vals)
    incident["4"] = [
        _decode_gemini_event(ev) for ev in fields.get(4, []) if isinstance(ev, bytes)
    ]
    return incident


def _decode_gemini_protobuf(data: bytes) -> list[dict]:
    """Decode MakerSuite ListIncidentsHistory protobuf (gRPC-web body)."""
    pos = 0
    chunks: list[bytes] = []
    while pos + 5 <= len(data):
        if data[pos] != 0:
            pos += 1
            continue
        length = int.from_bytes(data[pos + 1 : pos + 5], "big")
        pos += 5
        chunks.append(data[pos : pos + length])
        pos += length
    body = chunks[0] if chunks else data
    outer = _parse_proto_fields(body)
    return [
        _decode_gemini_incident(raw)
        for raw in outer.get(1, [])
        if isinstance(raw, bytes)
    ]


def _gemini_incident_events(incident: dict) -> list[dict]:
    return _pb_list(incident, "events") or _pb_list(incident, 4)


def _gemini_incident_active(incident: dict) -> bool:
    events = _gemini_incident_events(incident)
    if not events:
        return True
    # Mirror AI Studio UI: hide incidents that already have a Resolved event.
    return not any(_pb_get(event, "phase", 1) == 4 for event in events)


def _gemini_latest_event(incident: dict) -> dict | None:
    events = _gemini_incident_events(incident)
    if not events:
        return None
    return max(events, key=_event_timestamp)


def _gemini_service_summary(incident: dict) -> str | None:
    tags = _pb_list(incident, "services") or _pb_list(incident, 6)
    names = [GEMINI_SERVICES.get(int(tag), str(tag)) for tag in tags if tag is not None]
    if not names and (svc := _pb_get(incident, "service", 5)) is not None:
        names = [GEMINI_SERVICES.get(int(svc), str(svc))]
    return ", ".join(names) if names else None


def _gemini_incident_relevant(
    incident: dict, monitored_models: list[str] | None
) -> bool:
    if not monitored_models:
        return True
    tags = _pb_list(incident, "services") or _pb_list(incident, 6)
    if tags:
        tag_set = {int(t) for t in tags if t is not None}
        if tag_set and tag_set.isdisjoint(GEMINI_PROBE_SERVICE_TAGS):
            return False
    title = (_pb_get(incident, "title", 2) or "").strip()
    body_parts = [
        (_pb_get(event, "description", 4) or "").strip()
        for event in _gemini_incident_events(incident)
    ]
    text = "\n".join([title, *body_parts])
    return is_relevant_to_monitored_models("Gemini", text, monitored_models)


def parse_gemini_incidents(
    page_url: str,
    payload: Any,
    *,
    monitored_models: list[str] | None = None,
) -> dict:
    """Turn MakerSuite ListIncidentsHistory JSON into an OfficialStatusSignal dict."""
    incidents = [
        inc
        for inc in _normalize_gemini_incidents(payload)
        if _gemini_incident_active(inc)
        and _gemini_incident_relevant(inc, monitored_models)
    ]

    if not incidents:
        return {
            "providerId": GEMINI_STATUS["provider"],
            "status": "operational",
            "headline": "All Systems Operational",
            "latestUpdate": None,
            "latestPhase": None,
            "impactLabel": None,
            "componentSummary": _gemini_operational_components(),
            "pageUrl": page_url,
            "active": False,
            "sampledAt": _now_iso(),
        }

    worst = max(
        incidents,
        key=lambda inc: _pb_get(inc, "severity", 3) or 0,
    )
    headline = (_pb_get(worst, "title", 2) or "").strip() or None
    severity = _pb_get(worst, "severity", 3) or 0
    if severity >= GEMINI_SEVERITY_MAJOR:
        signal_status = "major_outage"
        impact_label = "Major impact"
    elif severity >= GEMINI_SEVERITY_PARTIAL:
        signal_status = "partial_outage"
        impact_label = "Partial impact"
    else:
        signal_status = "degraded"
        impact_label = None

    latest_event = _gemini_latest_event(worst)
    phase_num = _pb_get(latest_event, "phase", 1) if latest_event else None
    latest_phase = GEMINI_PHASE_LABELS.get(int(phase_num), None) if phase_num is not None else None
    latest_update = (_pb_get(latest_event, "description", 4) or "").strip() or None

    summaries = sorted(
        {summary for inc in incidents if (summary := _gemini_service_summary(inc))}
    )

    return {
        "providerId": GEMINI_STATUS["provider"],
        "status": signal_status,
        "headline": headline,
        "latestUpdate": latest_update,
        "latestPhase": latest_phase,
        "impactLabel": impact_label,
        "componentSummary": "; ".join(summaries[:3]) if summaries else None,
        "pageUrl": page_url,
        "active": True,
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

    def __init__(
        self,
        provider_names: list[str],
        monitored_models: dict[str, list[str]] | None = None,
    ) -> None:
        self._statuspage = [n for n in provider_names if n in STATUSPAGE_PROVIDERS]
        self._gemini = "Gemini" in provider_names
        self._monitored_models = monitored_models or {}
        self._latest: dict[str, dict] = {
            n: _unavailable_signal(n, STATUSPAGE_PROVIDERS[n]["page_url"])
            for n in self._statuspage
        }
        if self._gemini:
            self._latest["Gemini"] = _unavailable_signal(
                "Gemini", GEMINI_STATUS["page_url"]
            )
        self._last_poll: dict[str, float] = {}

    async def _poll_statuspage(self, client: httpx.AsyncClient, provider: str) -> dict:
        meta = STATUSPAGE_PROVIDERS[provider]
        payload = await fetch_summary(client, meta["summary_url"])
        if payload is None:
            return _unavailable_signal(provider, meta["page_url"])
        return parse_statuspage_summary(
            provider,
            meta["page_url"],
            payload,
            monitored_models=self._monitored_models.get(provider),
        )

    async def _poll_gemini(self, client: httpx.AsyncClient) -> dict:
        # Isolated adapter — see gemini_status_browser.py (delete-friendly).
        from . import gemini_status_browser

        _ = client  # Gemini uses browser fetch, not httpx.
        payload = await gemini_status_browser.fetch_incidents()
        if payload is None:
            return _unavailable_signal("Gemini", GEMINI_STATUS["page_url"])
        return parse_gemini_incidents(
            GEMINI_STATUS["page_url"],
            payload,
            monitored_models=self._monitored_models.get("Gemini"),
        )

    async def poll(self, client: httpx.AsyncClient) -> None:
        now = time.monotonic()
        for provider in self._statuspage:
            last = self._last_poll.get(provider)
            if last is not None and now - last < config.OFFICIAL_STATUS_INTERVAL:
                continue
            try:
                self._latest[provider] = await self._poll_statuspage(client, provider)
            except Exception:
                log.exception("official status poll failed for %s", provider)
                sentry_sdk.capture_exception()
                self._latest[provider] = _unavailable_signal(
                    provider, STATUSPAGE_PROVIDERS[provider]["page_url"]
                )
            self._last_poll[provider] = time.monotonic()

        if self._gemini:
            last = self._last_poll.get("Gemini")
            if last is None or now - last >= config.OFFICIAL_STATUS_INTERVAL:
                try:
                    self._latest["Gemini"] = await self._poll_gemini(client)
                except Exception:
                    log.exception("official status poll failed for Gemini")
                    sentry_sdk.capture_exception()
                    self._latest["Gemini"] = _unavailable_signal(
                        "Gemini", GEMINI_STATUS["page_url"]
                    )
                self._last_poll["Gemini"] = time.monotonic()

    def signals(self) -> list[dict]:
        order = [*self._statuspage]
        if self._gemini:
            order.append("Gemini")
        return [self._latest[n] for n in order]

    def by_provider(self) -> dict[str, dict]:
        return dict(self._latest)
