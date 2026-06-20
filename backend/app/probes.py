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

from . import config

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
        return None, None, r.status_code
    text, tokens = parse_fn(r.json())
    return text, tokens, r.status_code


def _parse_claude(data: dict) -> tuple[str, int | None]:
    text = "".join(b.get("text", "") for b in data.get("content", []))
    return text, data.get("usage", {}).get("output_tokens")


def _parse_gpt(data: dict) -> tuple[str, int | None]:
    text = data["choices"][0]["message"]["content"]
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
    except Exception as exc:
        latency_ms = round((loop.time() - start) * 1000)
        log.warning("probe %s failed: %s: %s", target["id"], type(exc).__name__, exc)
        return ProbeResult(False, latency_ms, False, 0, None, "probe_error")


# --- Scoring ---------------------------------------------------------------


def _score_and_status(r: ProbeResult | None) -> tuple[int, str]:
    if r is None:
        return 0, "unknown"
    if not r.available:
        return 0, "down"
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

    def __init__(self, targets: list[dict]) -> None:
        self._targets = targets
        self._history: dict[str, deque] = {t["id"]: deque(maxlen=config.HISTORY_LEN) for t in targets}
        self._latest: dict[str, dict] = {}
        for t in targets:
            self._latest[t["id"]] = _build_provider_health(
                target=t, status="unknown", score=0, latency=0,
                token_rate=0, qa_correct=False, history=[],
            )
        self.updated_at = _now_iso()

    def apply(self, target: dict, result: ProbeResult | None) -> None:
        tid = target["id"]
        score, status = _score_and_status(result)
        latency = result.latency_ms if result else 0
        if result is not None:
            self._history[tid].append({"t": _now_iso(), "ms": latency})
        self._latest[tid] = _build_provider_health(
            target=target, status=status, score=score, latency=latency,
            token_rate=result.token_rate if result else 0,
            qa_correct=result.qa_correct if result else False,
            history=list(self._history[tid]),
        )
        self.updated_at = _now_iso()

    def snapshot(self) -> dict:
        providers = [self._latest[t["id"]] for t in self._targets]
        return {
            "providers": providers,
            "alerts": _build_alerts(providers),
            "updatedAt": self.updated_at,
        }


def _build_alerts(providers: list[dict]) -> list[dict]:
    """Minimal rule-based alerts; full 'Agent' chain is a later module."""
    healthy = [p for p in providers if p["status"] == "operational"]
    best = max(healthy, key=lambda p: p["healthScore"], default=None)
    alerts: list[dict] = []
    for p in providers:
        if p["status"] in ("degraded", "down"):
            label = f"{p['name']} {p.get('tier', '')}".strip()
            alt = (
                f"Route to {best['name']} {best.get('tier', '')} "
                f"(health {best['healthScore']}, ~{best['latencyMs']}ms)."
                if best
                else "No healthy alternative currently available."
            )
            alerts.append(
                {
                    "id": f"alert-{p['id']}-{p['status']}",
                    "severity": "critical" if p["status"] == "down" else "warning",
                    "providerId": p["id"],
                    "title": f"{label} is {p['status']}",
                    "attribution": (
                        "Cloud-side: other targets respond normally from the same probe."
                        if healthy
                        else "Inconclusive: multiple targets affected — check your network."
                    ),
                    "recoveryEta": "Unknown (history-based estimate pending).",
                    "recommendedAlternative": alt,
                    "insight": (
                        f"{label} ({p.get('model', '?')}) health is {p['healthScore']}/100 "
                        f"(latency {p['latencyMs']}ms, QA {'pass' if p['qaCorrect'] else 'fail'})."
                    ),
                    "createdAt": _now_iso(),
                }
            )
    return alerts


async def probe_all(client: httpx.AsyncClient, state: ProbeState, targets: list[dict]) -> None:
    results = await asyncio.gather(*(_run_one(client, t) for t in targets))
    for target, result in zip(targets, results):
        state.apply(target, result)
