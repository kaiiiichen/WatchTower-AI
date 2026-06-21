"""Hacker News community-signal source — the "fast leg" of the community-signal layer.

Uses the public Algolia HN Search API (no auth) to find recent stories mentioning each
AI provider, then looks for outage chatter ("down", "outage", "not working", ...).

PRINCIPLE: this is CORROBORATION, never a dependency. Every network/parse error
degrades to an "unavailable" signal and the probe pipeline keeps running untouched."""
from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime, timezone

import httpx

from . import config

log = logging.getLogger("watchtower.community")

# Fault keywords. Multi-word phrases are matched as substrings.
FAULT_KEYWORDS = (
    "down",
    "outage",
    "not working",
    "broken",
    "error",
    "slow",
    "is it just me",
)

# Provider name -> HN search queries, tried in order until one returns stories.
PROVIDER_QUERIES: dict[str, tuple[str, ...]] = {
    "Claude": ("Anthropic Claude", "Claude API"),
    "GPT": ("OpenAI", "ChatGPT"),
    "Gemini": ("Google Gemini", "Gemini API"),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fault_hit(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in FAULT_KEYWORDS)


def count_complaints(posts: list[dict]) -> tuple[int, int]:
    matched = sum(1 for p in posts if _fault_hit(p.get("title", "") + " " + p.get("body", "")))
    return matched, len(posts)


def complaint_rate(posts: list[dict]) -> float:
    matched, total = count_complaints(posts)
    return matched / total if total else 0.0


def _extract_stories(payload: dict) -> list[dict]:
    hits = payload.get("hits") or []
    posts: list[dict] = []
    for h in hits:
        posts.append(
            {
                "title": h.get("title") or h.get("story_title") or "",
                "body": h.get("story_text") or h.get("comment_text") or "",
            }
        )
    return posts


async def fetch_hn_stories(
    client: httpx.AsyncClient,
    query: str,
) -> list[dict] | None:
    """Fetch recent HN stories matching `query`. Returns None on ANY failure."""
    since = int(time.time()) - config.COMMUNITY_LOOKBACK_HOURS * 3600
    url = f"{config.HN_ALGOLIA_BASE.rstrip('/')}/search_by_date"
    try:
        r = await client.get(
            url,
            params={
                "query": query,
                "tags": "story",
                "hitsPerPage": config.COMMUNITY_POST_LIMIT,
                "numericFilters": f"created_at_i>{since}",
            },
        )
        if r.status_code != 200:
            log.warning("hn search %r HTTP %s", query, r.status_code)
            return None
        return _extract_stories(r.json())
    except Exception as exc:
        log.warning("hn search %r failed: %s", query, exc)
        return None


def classify(rate: float, baseline: list[float]) -> str:
    if len(baseline) >= config.COMMUNITY_MIN_BASELINE:
        mean = sum(baseline) / len(baseline)
        is_spike = (
            rate >= config.COMMUNITY_SPIKE_MIN_RATE
            and rate >= mean * config.COMMUNITY_SPIKE_FACTOR
            and rate - mean >= config.COMMUNITY_SPIKE_DELTA
        )
        if is_spike:
            return "spike"
        if rate - mean >= config.COMMUNITY_ELEVATED_DELTA:
            return "elevated"
        return "normal"
    if rate >= config.COMMUNITY_SPIKE_MIN_RATE:
        return "elevated"
    return "normal"


def _unavailable_signal(provider: str, search_query: str | None) -> dict:
    return {
        "providerId": provider,
        "source": "hackernews",
        "searchQuery": search_query,
        "lookbackHours": config.COMMUNITY_LOOKBACK_HOURS,
        "status": "unavailable",
        "complaintRate": 0.0,
        "baseline": 0.0,
        "postCount": 0,
        "matchedPosts": 0,
        "sampledAt": None,
    }


class CommunityState:
    """Rolling complaint-rate baseline + latest cached HN signal per provider."""

    def __init__(self, provider_names: list[str]) -> None:
        self._providers = [n for n in provider_names if n in PROVIDER_QUERIES]
        self._baseline: dict[str, deque] = {
            n: deque(maxlen=config.COMMUNITY_BASELINE_LEN) for n in self._providers
        }
        self._latest: dict[str, dict] = {
            n: _unavailable_signal(n, PROVIDER_QUERIES[n][0]) for n in self._providers
        }
        self._last_poll: dict[str, float] = {}

    async def _poll_one(self, client: httpx.AsyncClient, provider: str) -> dict:
        posts: list[dict] | None = None
        used_query: str | None = None
        for query in PROVIDER_QUERIES[provider]:
            posts = await fetch_hn_stories(client, query)
            if posts is not None:
                used_query = query
                break
        if posts is None:
            return _unavailable_signal(provider, PROVIDER_QUERIES[provider][0])

        rate = complaint_rate(posts)
        matched, total = count_complaints(posts)
        base = list(self._baseline[provider])
        status = classify(rate, base)
        baseline_mean = sum(base) / len(base) if base else 0.0
        self._baseline[provider].append(rate)
        return {
            "providerId": provider,
            "source": "hackernews",
            "searchQuery": used_query,
            "lookbackHours": config.COMMUNITY_LOOKBACK_HOURS,
            "status": status,
            "complaintRate": round(rate, 3),
            "baseline": round(baseline_mean, 3),
            "postCount": total,
            "matchedPosts": matched,
            "sampledAt": _now_iso(),
        }

    async def poll(self, client: httpx.AsyncClient) -> None:
        now = time.monotonic()
        for provider in self._providers:
            last = self._last_poll.get(provider)
            if last is not None and now - last < config.COMMUNITY_INTERVAL:
                continue
            try:
                self._latest[provider] = await self._poll_one(client, provider)
            except Exception:
                log.exception("community poll failed for %s", provider)
                self._latest[provider] = _unavailable_signal(
                    provider, PROVIDER_QUERIES[provider][0]
                )
            self._last_poll[provider] = time.monotonic()

    def signals(self) -> list[dict]:
        return [self._latest[n] for n in self._providers]

    def by_provider(self) -> dict[str, dict]:
        return dict(self._latest)
