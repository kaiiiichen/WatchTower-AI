"""Probe engine with dynamic model discovery.

At startup we ask each provider's list-models endpoint which models exist and
pick a "flagship" and a "mid" model by rule — avoiding hard-coded versions that
404 when a model is retired. Each provider is then probed at both tiers
concurrently (asyncio.gather), scored, and given a rolling latency history.

Discovery is implemented for Anthropic; OpenAI/Gemini currently fall back to the
env-configured model names (real discovery for them is a marked TODO)."""
from __future__ import annotations

import asyncio
import logging
import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import sentry_sdk

from . import config, monitoring
from .redaction import redact

log = logging.getLogger("watchtower.probes")

TIERS = ("flagship", "mid")


@dataclass
class ProbeResult:
    available: bool
    latency_ms: int
    qa_correct: bool
    token_rate: int
    http_status: int | None
    error: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _qa_ok(text: str | None) -> bool:
    return bool(text) and config.QA_EXPECTED in text


def _token_rate(output_tokens: int | None, latency_ms: int) -> int:
    if not output_tokens or latency_ms <= 0:
        return 0
    return round(output_tokens / (latency_ms / 1000))


# --- Model selection -------------------------------------------------------


def _version_key(name: str) -> tuple[tuple[int, ...], int]:
    """Sortable recency key from a model name.

    Splits out an 8-digit date suffix (YYYYMMDD) and compares the remaining
    version numbers lexicographically, with the date as tiebreak. So
    'claude-opus-4-1-20250805' (key (4,1),20250805) > 'claude-opus-4-20250514'
    > 'claude-3-opus-20240229'."""
    lower = name.lower()
    dates = re.findall(r"\d{8}", lower)
    date = max((int(d) for d in dates), default=0)
    rest = re.sub(r"\d{8}", "", lower)
    nums = tuple(int(n) for n in re.findall(r"\d+", rest))
    return (nums, date)


def pick_latest(
    models: list[str], *, include: str, exclude: tuple[str, ...] = ()
) -> str | None:
    """Latest model whose name contains `include` and none of `exclude`."""
    inc = include.lower()
    cands = [
        m
        for m in models
        if inc in m.lower() and not any(e.lower() in m.lower() for e in exclude)
    ]
    if not cands:
        return None
    return max(cands, key=_version_key)


# --- list-models endpoints -------------------------------------------------


async def _list_anthropic(client: httpx.AsyncClient) -> list[str]:
    r = await client.get(
        "https://api.anthropic.com/v1/models",
        headers={
            "x-api-key": config.ANTHROPIC_API_KEY or "",
            "anthropic-version": "2023-06-01",
        },
        params={"limit": 1000},
    )
    r.raise_for_status()
    return [m["id"] for m in r.json().get("data", [])]


def _select_anthropic(models: list[str]) -> dict[str, str | None]:
    # flagship: latest 'opus'; mid: latest 'sonnet'.
    return {
        "flagship": pick_latest(models, include="opus"),
        "mid": pick_latest(models, include="sonnet"),
    }


async def _list_openai(client: httpx.AsyncClient) -> list[str]:
    r = await client.get(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY or ''}"},
    )
    r.raise_for_status()
    return [m["id"] for m in r.json().get("data", [])]


# Non-flagship / non-chat OpenAI variants to keep out of the flagship pick.
# "pro" is excluded too: gpt-*-pro is served only by v1/responses, not
# v1/chat/completions, so it 404s our probe.
_OPENAI_EXCLUDE = (
    "mini", "nano", "audio", "realtime", "search", "preview", "pro",
    "tts", "transcribe", "image", "instruct", "embedding", "moderation",
)


def _select_openai(models: list[str]) -> dict[str, str | None]:
    # flagship: highest-version plain `gpt-*` chat model; mid: that family's -mini.
    gpts = [m for m in models if m.lower().startswith("gpt-")]
    flagship_cands = [
        m for m in gpts if not any(e in m.lower() for e in _OPENAI_EXCLUDE)
    ]
    if not flagship_cands:
        return {"flagship": None, "mid": None}
    flagship = max(flagship_cands, key=_version_key)
    exact_mini = f"{flagship}-mini"
    if exact_mini in models:
        mid = exact_mini
    else:
        mini_cands = [
            m
            for m in gpts
            if "mini" in m.lower()
            and not any(e in m.lower() for e in _OPENAI_EXCLUDE if e != "mini")
        ]
        mid = max(mini_cands, key=_version_key) if mini_cands else None
    return {"flagship": flagship, "mid": mid}


async def _list_gemini(client: httpx.AsyncClient) -> list[str]:
    r = await client.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": config.GEMINI_API_KEY or "", "pageSize": 1000},
    )
    r.raise_for_status()
    out: list[str] = []
    for m in r.json().get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            out.append(m["name"].split("/")[-1])  # strip "models/" prefix
    return out


def _select_gemini(models: list[str]) -> dict[str, str | None]:
    # flagship: latest 'pro'; mid: latest 'flash' excluding 'lite'.
    # Restrict to `gemini-*` chat models so non-Gemini entries (e.g.
    # deep-research-*, which only support the Interactions API) are ignored.
    gem = [m for m in models if m.lower().startswith("gemini-")]
    return {
        "flagship": pick_latest(gem, include="pro"),
        "mid": pick_latest(gem, include="flash", exclude=("lite",)),
    }


# --- Probe adapters (now take a model id) ----------------------------------

ProbeResponse = tuple[str | None, int | None, int]


async def _do_probe(
    client: httpx.AsyncClient,
    parse_fn,
    **request_kwargs,
) -> ProbeResponse:
    """Shared probe skeleton: POST, check status, delegate parsing."""
    r = await client.post(**request_kwargs)
    if r.status_code != 200:
        log.warning("probe HTTP %s: %s", r.status_code, redact(r.text[:200]))
        return None, None, r.status_code
    try:
        data = r.json()
    except Exception:
        log.warning("probe returned non-JSON response")
        return None, None, r.status_code
    text, tokens = parse_fn(data)
    return text, tokens, r.status_code


def _parse_claude(data: dict) -> tuple[str, int | None]:
    text = "".join(b.get("text", "") for b in data.get("content", []))
    return text, data.get("usage", {}).get("output_tokens")


def _parse_gpt(data: dict) -> tuple[str | None, int | None]:
    choices = data.get("choices") or []
    if not choices:
        log.warning("gpt probe returned empty choices")
        return None, None
    text = choices[0].get("message", {}).get("content")
    return text, data.get("usage", {}).get("completion_tokens")


def _parse_gemini(data: dict) -> tuple[str, int | None]:
    candidates = data.get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    text = "".join(p.get("text", "") for p in parts)
    return text, data.get("usageMetadata", {}).get("candidatesTokenCount")


async def _probe_claude(client, model):
    return await _do_probe(
        client,
        _parse_claude,
        url="https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": config.ANTHROPIC_API_KEY or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 16,
            "messages": [{"role": "user", "content": config.QA_QUESTION}],
        },
    )



async def _probe_gpt(client, model):
    return await _do_probe(
        client,
        _parse_gpt,
        url="https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {config.OPENAI_API_KEY or ''}",
            "content-type": "application/json",
        },
        json={
            "model": model,
            # gpt-5+ reject `max_tokens` (need `max_completion_tokens`), and
            # reasoning models spend tokens before answering — give enough budget
            # to emit the QA answer.
            "max_completion_tokens": 512,
            "messages": [{"role": "user", "content": config.QA_QUESTION}],
        },
    )



async def _probe_gemini(client, model):
    return await _do_probe(
        client,
        _parse_gemini,
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"content-type": "application/json"},
        params={"key": config.GEMINI_API_KEY or ""},
        json={
            "contents": [{"parts": [{"text": config.QA_QUESTION}]}],
            # Gemini 3.x spends "thinking" tokens; a tiny budget hits MAX_TOKENS
            # before any answer text is emitted.
            "generationConfig": {"maxOutputTokens": 512},
        },
    )



# --- Provider registry -----------------------------------------------------
# list_fn/select are None where dynamic discovery isn't implemented yet -> the
# provider falls back to its env-configured models.

PROVIDERS = [
    {
        "id": "claude",
        "name": "Claude",
        "key": lambda: config.ANTHROPIC_API_KEY,
        "probe": _probe_claude,
        "list_fn": _list_anthropic,
        "select": _select_anthropic,
        "fallback": lambda: {"flagship": config.ANTHROPIC_MODEL, "mid": config.ANTHROPIC_MODEL_MID},
    },
    {
        "id": "gpt",
        "name": "GPT",
        "key": lambda: config.OPENAI_API_KEY,
        "probe": _probe_gpt,
        "list_fn": _list_openai,
        "select": _select_openai,
        "fallback": lambda: {"flagship": config.OPENAI_MODEL, "mid": config.OPENAI_MODEL_MID},
    },
    {
        "id": "gemini",
        "name": "Gemini",
        "key": lambda: config.GEMINI_API_KEY,
        "probe": _probe_gemini,
        "list_fn": _list_gemini,
        "select": _select_gemini,
        "fallback": lambda: {"flagship": config.GEMINI_MODEL, "mid": config.GEMINI_MODEL_MID},
    },
]


def _tier_dict(src: dict, fallback: dict | None = None) -> dict[str, str | None]:
    """Build a {flagship, mid} dict, optionally filling gaps from fallback."""
    return {
        tier: src.get(tier) or (fallback.get(tier) if fallback else None)
        for tier in TIERS
    }


async def discover_models(client: httpx.AsyncClient, provider: dict) -> dict[str, str | None]:
    """Return {flagship, mid} model ids. Tries the provider's list-models
    endpoint; on any failure (or missing key / unimplemented), falls back to the
    env-configured names, per tier."""
    fb = provider["fallback"]()
    if not provider["list_fn"] or not provider["key"]():
        return _tier_dict(fb)
    try:
        models = await provider["list_fn"](client)
        sel = provider["select"](models)
        chosen = _tier_dict(sel, fb)
        log.info("discovered %s models: %s", provider["id"], chosen)
        return chosen
    except Exception as exc:
        log.warning("discovery failed for %s (%s); using env fallback", provider["id"], exc)
        return _tier_dict(fb)


async def build_targets(client: httpx.AsyncClient) -> list[dict]:
    """One probe target per (provider, tier) that resolved to a model."""
    targets: list[dict] = []
    for p in PROVIDERS:
        models = await discover_models(client, p)
        for tier in TIERS:
            model = models.get(tier)
            if not model:
                continue
            targets.append(
                {
                    "id": f"{p['id']}-{tier}",
                    "provider_id": p["id"],
                    "name": p["name"],
                    "tier": tier,
                    "model": model,
                    "probe": p["probe"],
                    "has_key": bool(p["key"]()),
                }
            )
    return targets


async def _run_one(client: httpx.AsyncClient, target: dict) -> ProbeResult | None:
    """None when the API key is missing (-> `unknown`)."""
    if not target["has_key"]:
        return None
    loop = asyncio.get_event_loop()
    start = loop.time()
    try:
        text, tokens, status = await target["probe"](client, target["model"])
        latency_ms = round((loop.time() - start) * 1000)
        ok = status == 200
        return ProbeResult(
            available=ok,
            latency_ms=latency_ms,
            qa_correct=ok and _qa_ok(text),
            token_rate=_token_rate(tokens, latency_ms) if ok else 0,
            http_status=status,
        )
    except httpx.TimeoutException as exc:
        latency_ms = round((loop.time() - start) * 1000)
        log.warning("probe %s timed out after %dms", target["id"], latency_ms)
        # exc can embed the request URL (with Gemini's ?key=) — redact before storing.
        return ProbeResult(False, latency_ms, False, 0, None, redact(f"TimeoutException: {exc}"))
    except httpx.ConnectError as exc:
        latency_ms = round((loop.time() - start) * 1000)
        log.warning("probe %s connection failed: %s", target["id"], redact(str(exc)))
        return ProbeResult(False, latency_ms, False, 0, None, redact(f"ConnectError: {exc}"))
    except Exception as exc:
        latency_ms = round((loop.time() - start) * 1000)
        log.error("probe %s unexpected error: %s: %s", target["id"], type(exc).__name__, redact(str(exc)))
        return ProbeResult(False, latency_ms, False, 0, None, "probe_error")


# --- Scoring ---------------------------------------------------------------


def _classify_failure(r: ProbeResult) -> str:
    """Map a non-200 / errored probe to a status that separates the user's own
    problem from a real service outage. "down" is reserved for genuine service
    faults so a quota cap or a bad model name never masquerades as an outage."""
    code = r.http_status
    if code == 429:
        return "rate_limited"  # your account: rate/quota limit
    if code is not None and 400 <= code < 500:
        return "misconfigured"  # your config: model/key unavailable (400/403/404)
    # 5xx, or no HTTP response at all (timeout/connect/unknown error) -> outage.
    return "down"


def _score_and_status(r: ProbeResult | None) -> tuple[int, str]:
    if r is None:
        return 0, "unknown"
    if not r.available:
        return 0, _classify_failure(r)
    score = 100.0
    if not r.qa_correct:
        score -= 35.0
    if r.latency_ms > 1000:
        score -= min(40.0, (r.latency_ms - 1000) / 100 * 2)
    score = max(0, round(score))
    if score >= 85:
        return score, "operational"
    if score >= 50:
        return score, "degraded"
    return score, "down"


# --- Trend warning (precursor) ---------------------------------------------


def latency_trend(latencies: list[int], window: int | None = None) -> dict | None:
    """Real-time trend over the last `window` latency samples — no ML, no history
    training. Returns None when there isn't enough data, else a summary dict with
    `degrading: bool`.

    "degrading" requires ALL three, so ordinary jitter can't trip it:
      - a mostly-monotonic climb (at most TREND_ALLOWED_DIPS non-increasing steps),
      - a large RELATIVE rise (>= TREND_MIN_RISE_RATIO across the window), and
      - a meaningful ABSOLUTE rise (>= TREND_MIN_RISE_MS) so a 50->80ms wobble on
        a fast provider doesn't count."""
    window = window or config.TREND_WINDOW
    if len(latencies) < window:
        return None
    seg = latencies[-window:]
    first, last = seg[0], seg[-1]
    if first <= 0:
        return None
    ups = sum(1 for a, b in zip(seg, seg[1:]) if b > a)
    rise = last - first
    rise_ratio = rise / first
    degrading = (
        ups >= (window - 1) - config.TREND_ALLOWED_DIPS
        and rise_ratio >= config.TREND_MIN_RISE_RATIO
        and rise >= config.TREND_MIN_RISE_MS
    )
    return {
        "degrading": degrading,
        "first": first,
        "last": last,
        "riseRatio": round(rise_ratio, 2),
        "window": window,
    }


# --- Shared dict builder ---------------------------------------------------


def _build_provider_health(
    *, target: dict, status: str, score: int, latency: int,
    token_rate: int, qa_correct: bool, history: list,
) -> dict:
    """Single source of truth for the provider-health dict shape."""
    return {
        "id": target["id"],
        "name": target["name"],
        "status": status,
        "healthScore": score,
        "latencyMs": latency,
        "tokenRate": token_rate,
        "qaCorrect": qa_correct,
        "latencyHistory": history,
        "tier": target["tier"],
        "model": target["model"],
    }


# --- In-memory state -------------------------------------------------------


class ProbeState:
    """Latest health per target id + a rolling latency history."""

    def __init__(
        self,
        targets: list[dict],
        *,
        history_store=None,
        initial_history: dict[str, list[dict]] | None = None,
    ) -> None:
        self._targets = targets
        self._history_store = history_store
        # Optional corroboration sources. None in tests / when unset.
        self.community = None
        self.official = None
        self._history: dict[str, deque] = {t["id"]: deque(maxlen=config.HISTORY_LEN)for t in targets}
        if initial_history:
            for tid, points in initial_history.items():
                if tid in self._history:
                    for pt in points:
                        self._history[tid].append(pt)
        self._latest: dict[str, dict] = {}
        for t in targets:
            self._latest[t["id"]] = _build_provider_health(
                target=t, status="unknown", score=0, latency=0,
                token_rate=0, qa_correct=False,
                history=list(self._history[t["id"]]),
            )
        self.updated_at = _now_iso()

    def apply(self, target: dict, result: ProbeResult | None) -> None:
        tid = target["id"]
        score, status = _score_and_status(result)
        latency = result.latency_ms if result else 0
        ts: str | None = None
        if result is not None:
            ts = _now_iso()
            self._history[tid].append({"t": ts, "ms": latency})
        # Trend warning: a provider that is still healthy NOW but whose latency is
        # steadily climbing is flagged "degrading" — a pre-emptive heads-up. Only
        # overrides "operational"; an already-impaired status (degraded/down/...)
        # is a real problem, not a precursor.
        if status == "operational":
            trend = latency_trend([pt["ms"] for pt in self._history[tid]])
            if trend and trend["degrading"]:
                status = "degrading"
        if result is not None and self._history_store is not None and ts is not None:
            self._history_store.record(
                target=target,
                timestamp=ts,
                status=status,
                health_score=score,
                latency_ms=latency,
                token_rate=result.token_rate,
                qa_pass=result.qa_correct,
            )
        self._latest[tid] = _build_provider_health(
            target=target, status=status, score=score, latency=latency,
            token_rate=result.token_rate if result else 0,
            qa_correct=result.qa_correct if result else False,
            history=list(self._history[tid]),
        )
        self.updated_at = _now_iso()

    def snapshot(self) -> dict:
        providers = [self._latest[t["id"]] for t in self._targets]
        community = self.community.by_provider() if self.community else None
        official = self.official.by_provider() if self.official else None
        return {
            "providers": providers,
            "alerts": _build_alerts(providers, community, official),
            "updatedAt": self.updated_at,
            "community": self.community.signals() if self.community else [],
            "official": self.official.signals() if self.official else [],
        }


def _official_acknowledged(sig: dict | None) -> bool:
    if not sig or sig.get("status") == "unavailable":
        return False
    return bool(sig.get("active"))


def _official_attribution_text(sig: dict) -> str:
    chunks: list[str] = []
    if sig.get("headline"):
        chunks.append(f'Official status acknowledges: "{sig["headline"]}"')
    if sig.get("impactLabel"):
        chunks.append(f"({sig['impactLabel']})")
    phase = sig.get("latestPhase")
    body = sig.get("latestUpdate")
    if phase and body:
        chunks.append(f"Latest {phase}: {body[:240]}")
    elif body:
        chunks.append(body[:240])
    page = sig.get("pageUrl") or "status page"
    return " ".join(chunks) + f" — source: {page}"


def _build_alerts(
    providers: list[dict],
    community: dict | None = None,
    official: dict | None = None,
) -> list[dict]:
    """Per-MODEL rule-based alerts. Two tiers of the same provider are compared
    so we can tell a model-specific problem (one tier impaired, the other fine)
    apart from a provider-wide outage, and prefer same-provider failover.

    `community` maps provider name -> latest Reddit signal dict (or None). When a
    probe anomaly coincides with a community-signal spike, the alert is upgraded
    to a confirmed widespread event. It's purely additive corroboration — absent
    or unavailable community data changes nothing.

    `official` maps provider name -> latest Statuspage signal. When the provider
    has already posted an incident, attribution cites their wording; when probes
    fire but the page is still green, we note the detection-gap window.
    Full 'Agent' chain is a later module."""
    community = community or {}
    official = official or {}
    healthy = [p for p in providers if p["status"] == "operational"]
    best_global = max(healthy, key=lambda p: p["healthScore"], default=None)
    alerts: list[dict] = []

    # Genuine service faults (the service's problem) vs account/config faults
    # (your problem). The whole point of the product: don't conflate the two.
    SERVICE_FAULTS = ("degraded", "down")
    CONFIG_FAULTS = ("rate_limited", "misconfigured")

    # Precursor pass: "degrading" providers are still healthy now but trending
    # down — emit a forward-looking heads-up (info), NOT an incident alert.
    for p in providers:
        if p["status"] != "degrading":
            continue
        label = f"{p['name']} {p.get('tier', '')}".strip()
        model = p.get("model", "?")
        trend = latency_trend([pt["ms"] for pt in p.get("latencyHistory", [])])
        if trend:
            pct = round(trend["riseRatio"] * 100)
            detail = (
                f"Latency has climbed ~{pct}% over the last {trend['window']} probes "
                f"({trend['first']}→{trend['last']}ms) while still responding."
            )
        else:
            detail = "Latency is trending upward while still responding."
        alerts.append(
            {
                "id": f"alert-{p['id']}-degrading",
                "severity": "info",
                "providerId": p["id"],
                "title": f"{label} ({model}) performance is trending down",
                "attribution": (
                    f"Early-warning trend, not a fault yet — {detail} Predicted from the "
                    f"live latency curve, before any outage."
                ),
                "recoveryEta": "Predictive — no incident yet; watching the trend.",
                "recommendedAlternative": (
                    f"Pre-warm {best_global['name']} {best_global.get('tier')} "
                    f"({best_global.get('model')}) in case this continues."
                    if best_global and best_global["name"] != p["name"]
                    else "No action needed yet — heads-up only."
                ),
                "insight": (
                    f"⚠️ {label} ({model}) performance is steadily degrading and may be "
                    f"heading toward a problem. {detail} This is a pre-emptive heads-up "
                    f"from the real-time trend — no incident has occurred yet."
                ),
                "communityConfirmed": False,
                "officialAcknowledged": False,
                "fusionMode": None,
                "createdAt": _now_iso(),
            }
        )

    for p in providers:
        status = p["status"]
        if status not in SERVICE_FAULTS + CONFIG_FAULTS:
            continue
        label = f"{p['name']} {p.get('tier', '')}".strip()
        model = p.get("model", "?")
        # Siblings = the same provider's other tier(s).
        siblings = [q for q in providers if q["name"] == p["name"] and q["id"] != p["id"]]
        healthy_siblings = [q for q in siblings if q["status"] == "operational"]
        best_sibling = max(healthy_siblings, key=lambda q: q["healthScore"], default=None)

        # Failover: prefer the same provider's healthy tier (cheaper switch),
        # otherwise the healthiest model anywhere. Useful for both fault classes
        # (route elsewhere while a service recovers OR while you fix your config).
        alt_target = best_sibling or best_global
        if alt_target:
            same = alt_target["name"] == p["name"]
            alt = (
                f"Route to {alt_target['name']} {alt_target.get('tier')} "
                f"({alt_target.get('model')}, health {alt_target['healthScore']}, "
                f"~{alt_target['latencyMs']}ms)"
                + (" — same provider, minimal switch." if same else ".")
            )
        else:
            alt = "No healthy alternative currently available."

        community_confirmed = False
        official_acknowledged = False
        fusion_mode: str | None = None
        off = official.get(p["name"])

        if status in CONFIG_FAULTS:
            # Your problem, not the service's — so community chatter can't (and
            # shouldn't) corroborate it, and this is never "down".
            severity = "warning"
            if status == "rate_limited":
                title = f"{label} ({model}) is rate-limited"
                attribution = (
                    f"Your account: {label} returned HTTP 429 (rate/quota limit) for "
                    f"{model} — an account-side limit on your key, not a {p['name']} outage."
                )
                insight = (
                    f"{label} ({model}) is rate-limited (HTTP 429): your account hit a "
                    f"request-rate or quota limit. This is your account's problem, NOT a "
                    f"{p['name']} service outage."
                )
                recovery = "Clears when your rate/quota window resets — check your provider quota dashboard."
            else:  # misconfigured
                title = f"{label} ({model}) is misconfigured"
                attribution = (
                    f"Your config: {label} returned a 4xx for {model} — the model name may "
                    f"be unavailable to your key, or the key lacks access/permission. "
                    f"Not a {p['name']} outage."
                )
                insight = (
                    f"{label} ({model}) is unavailable due to configuration (HTTP 4xx): the "
                    f"model isn't available to your key, or a key/permission problem. This is "
                    f"your configuration's problem, NOT a {p['name']} service outage."
                )
                recovery = "Won't self-recover — fix the model name or key/permissions in your config."
        else:
            # Service fault: attribute model-specific vs provider-wide vs cloud-side.
            if best_sibling:
                attribution = (
                    f"Model-specific: {label} ({model}) is impaired, but the same "
                    f"provider's {best_sibling.get('tier')} model ({best_sibling.get('model')}, "
                    f"health {best_sibling['healthScore']}) is healthy — looks like a per-model "
                    f"issue, not a {p['name']}-wide outage."
                )
            elif siblings:  # has other tiers, none healthy
                others = ", ".join(s.get("tier", "?") for s in siblings)
                attribution = (
                    f"Provider-wide: every probed {p['name']} model is impaired "
                    f"({others} too) — likely a {p['name']} outage, not model-specific."
                )
            elif healthy:
                attribution = "Cloud-side: other providers respond normally from the same probe."
            else:
                attribution = "Inconclusive: multiple providers affected — check your network."

            severity = "critical" if status == "down" else "warning"
            title = f"{label} ({model}) is {status}"
            recovery = "Unknown (history-based estimate pending)."
            insight = (
                f"{label} ({model}) health is {p['healthScore']}/100 "
                f"(latency {p['latencyMs']}ms, QA {'pass' if p['qaCorrect'] else 'fail'})."
            )

            if _official_acknowledged(off):
                official_acknowledged = True
                fusion_mode = "official_acknowledged"
                attribution = _official_attribution_text(off) + " " + attribution
                if status == "down":
                    severity = "warning"
                recovery = "Follow the provider's status page for official ETA."
            elif off and off.get("status") == "operational" and not off.get("active"):
                fusion_mode = "probe_ahead_of_official"
                insight += (
                    " WatchTower probes detect an anomaly, but the official status "
                    "page still shows Operational — you may be ahead of official "
                    "acknowledgment (see Detection Gap)."
                )

            # Community corroboration: a SERVICE anomaly + a Reddit complaint spike
            # for the same provider => confirmed widespread event when not yet officially
            # acknowledged. Corroboration only — never the basis for the alert itself.
            sig = community.get(p["name"])
            community_confirmed = bool(sig and sig.get("status") == "spike")
            if community_confirmed and not official_acknowledged:
                sub = sig.get("subreddit")
                insight += (
                    f" CONFIRMED WIDESPREAD EVENT — community signal is spiking on "
                    f"r/{sub} (complaint rate {sig.get('complaintRate')} vs baseline "
                    f"{sig.get('baseline')} over {sig.get('postCount')} posts). Probe "
                    f"anomaly + community spike corroborate each other; this looks like "
                    f"a real outage the provider has not acknowledged on its status page yet."
                )
            elif community_confirmed and official_acknowledged:
                insight += (
                    " Community chatter corroborates the official incident post."
                )

        alerts.append(
            {
                "id": f"alert-{p['id']}-{status}",
                "severity": severity,
                "providerId": p["id"],
                "title": title,
                "attribution": attribution,
                "recoveryEta": recovery,
                "recommendedAlternative": alt,
                "insight": insight,
                "communityConfirmed": community_confirmed,
                "officialAcknowledged": official_acknowledged,
                "fusionMode": fusion_mode,
                "createdAt": _now_iso(),
            }
        )

    # Official-only: status page reports an issue but probes still pass.
    for name, off in official.items():
        if not _official_acknowledged(off):
            continue
        tiers = [p for p in providers if p["name"] == name]
        if any(p["status"] in SERVICE_FAULTS for p in tiers):
            continue
        headline = off.get("headline") or "Active incident"
        alerts.append(
            {
                "id": f"alert-{name}-official-only",
                "severity": "info",
                "providerId": tiers[0]["id"] if tiers else name.lower(),
                "title": f"{name}: official status page reports an issue",
                "attribution": _official_attribution_text(off),
                "recoveryEta": "Follow the provider's status page for updates.",
                "recommendedAlternative": (
                    "Your probes still pass — may be regional or model-specific. "
                    "Watch latency trends."
                ),
                "insight": (
                    f"The official status page for {name} reports an active incident "
                    f'("{headline}"), but WatchTower QA probes still pass from your '
                    f"network. This can mean a partial outage or a model you are not probing."
                ),
                "communityConfirmed": False,
                "officialAcknowledged": True,
                "fusionMode": "official_only",
                "createdAt": _now_iso(),
            }
        )
    return alerts


async def _run_one_traced(client: httpx.AsyncClient, target: dict) -> ProbeResult | None:
    """Layer 3: wrap each provider probe in a Sentry span (no-op without init)."""
    # 2.x renamed span `description` -> `name` (same span label); spec said description.
    with sentry_sdk.start_span(op="probe", name=f"probe_{target['id']}"):
        return await _run_one(client, target)


async def probe_all(client: httpx.AsyncClient, state: ProbeState, targets: list[dict]) -> None:
    # Layer 3: one transaction per probe cycle, one span per provider probe.
    with sentry_sdk.start_transaction(op="probe_cycle", name="AI Provider Probe Cycle"):
        results = await asyncio.gather(
            *(_run_one_traced(client, t) for t in targets), return_exceptions=True
        )
    for target, result in zip(targets, results):
        if isinstance(result, BaseException):
            log.error("probe %s raised unexpectedly: %s", target["id"], result)
            state.apply(target, ProbeResult(False, 0, False, 0, None, str(result)))
        else:
            state.apply(target, result)
    # Layers 1 + 2: report degraded/down providers to Sentry (no-op without init).
    monitoring.report_incidents(state.snapshot()["providers"], state.updated_at)
