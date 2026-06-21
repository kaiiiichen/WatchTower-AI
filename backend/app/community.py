"""Reddit community-signal source — the "fast leg" of the community-signal layer.

Watches public subreddits for a spike in outage chatter ("down", "outage",
"not working", ...) and turns it into a per-provider corroboration signal.

PRINCIPLE: this is CORROBORATION, never a dependency. Every network/parse error
degrades to a "unavailable" signal and the probe pipeline keeps running
untouched — if Reddit is down, the main detection chain is unaffected.

Reddit's public JSON endpoints need no auth but DO require a unique User-Agent or
they aggressively rate-limit (HTTP 429). We poll each subreddit at most once per
COMMUNITY_INTERVAL (60s, far under Reddit's threshold) and cache the latest
result, so the snapshot is served from memory between polls."""
from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime, timezone

import httpx

from . import config

log = logging.getLogger("watchtower.community")

# Fault keywords. Multi-word phrases are matched as substrings, so "is it just
# me" catches the classic "is it just me or is X down" outage post.
FAULT_KEYWORDS = (
    "down",
    "outage",
    "not working",
    "broken",
    "error",
    "slow",
    "is it just me",
)

# Provider name -> candidate subreddits, tried in order until one returns posts.
# Gemini's community has churned (Bard -> Gemini), so we list fallbacks; whichever
# responds first wins, and if none do the signal is simply "unavailable".
SUBREDDITS: dict[str, tuple[str, ...]] = {
    "Claude": ("ClaudeAI",),
    "GPT": ("OpenAI",),
    "Gemini": ("Bard", "GeminiAI", "GoogleGeminiAI"),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fault_hit(text: str) -> bool:
    """True if any fault keyword appears in the (lowercased) text."""
    low = text.lower()
    return any(kw in low for kw in FAULT_KEYWORDS)


def count_complaints(posts: list[dict]) -> tuple[int, int]:
    """Return (matched, total). A post matches if its title OR body has a keyword."""
    matched = sum(1 for p in posts if _fault_hit(p.get("title", "") + " " + p.get("body", "")))
    return matched, len(posts)


def complaint_rate(posts: list[dict]) -> float:
    matched, total = count_complaints(posts)
    return matched / total if total else 0.0


def _extract_posts(payload: dict) -> list[dict]:
    """Pull {title, body} out of a Reddit listing JSON, tolerating odd shapes."""
    children = (payload.get("data") or {}).get("children") or []
    posts: list[dict] = []
    for c in children:
        d = (c or {}).get("data") or {}
        posts.append({"title": d.get("title") or "", "body": d.get("selftext") or ""})
    return posts


async def fetch_subreddit(client: httpx.AsyncClient, subreddit: str) -> list[dict] | None:
    """Fetch the newest posts for one subreddit. Returns None on ANY failure so
    callers can degrade gracefully — this never raises."""
    url = f"https://www.reddit.com/r/{subreddit}/new.json"
    try:
        r = await client.get(
            url,
            params={"limit": config.COMMUNITY_POST_LIMIT},
            headers={"User-Agent": config.REDDIT_USER_AGENT},
        )
        if r.status_code != 200:
            log.warning("reddit r/%s HTTP %s", subreddit, r.status_code)
            return None
        return _extract_posts(r.json())
    except Exception as exc:  # network, JSON, anything — degrade, don't crash
        log.warning("reddit r/%s fetch failed: %s", subreddit, exc)
        return None


def classify(rate: float, baseline: list[float]) -> str:
    """Classify a complaint rate against its rolling baseline.

    "spike"    -> rate is both absolutely high AND well above its own baseline
                  (needs enough baseline history to be trustworthy).
    "elevated" -> noticeably above baseline but short of a confirmed spike.
    "normal"   -> business as usual.
    """
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
    # Not enough history yet: only an absolute outlier reads as elevated.
    if rate >= config.COMMUNITY_SPIKE_MIN_RATE:
        return "elevated"
    return "normal"


def _unavailable_signal(provider: str, subreddit: str | None) -> dict:
    return {
        "providerId": provider,
        "subreddit": subreddit,
        "status": "unavailable",
        "complaintRate": 0.0,
        "baseline": 0.0,
        "postCount": 0,
        "matchedPosts": 0,
        "sampledAt": None,
    }


class CommunityState:
    """Holds the rolling complaint-rate baseline + latest cached signal per
    provider. `signals()` is read by the snapshot; `poll()` refreshes it."""

    def __init__(self, provider_names: list[str]) -> None:
        # Keep only providers we have a subreddit mapping for, preserving order.
        self._providers = [n for n in provider_names if n in SUBREDDITS]
        self._baseline: dict[str, deque] = {
            n: deque(maxlen=config.COMMUNITY_BASELINE_LEN) for n in self._providers
        }
        self._latest: dict[str, dict] = {
            n: _unavailable_signal(n, SUBREDDITS[n][0]) for n in self._providers
        }
        self._last_poll: dict[str, float] = {}

    async def _poll_one(self, client: httpx.AsyncClient, provider: str) -> dict:
        """Fetch + classify one provider. Never raises; returns a signal dict."""
        posts: list[dict] | None = None
        used_sub: str | None = None
        for sub in SUBREDDITS[provider]:
            posts = await fetch_subreddit(client, sub)
            if posts is not None:
                used_sub = sub
                break
        if posts is None:
            # All candidate subreddits failed: keep the baseline, mark unavailable.
            return _unavailable_signal(provider, SUBREDDITS[provider][0])

        rate = complaint_rate(posts)
        matched, total = count_complaints(posts)
        base = list(self._baseline[provider])
        status = classify(rate, base)
        baseline_mean = sum(base) / len(base) if base else 0.0
        # Append AFTER classifying so a real spike doesn't pollute its own baseline.
        self._baseline[provider].append(rate)
        return {
            "providerId": provider,
            "subreddit": used_sub,
            "status": status,
            "complaintRate": round(rate, 3),
            "baseline": round(baseline_mean, 3),
            "postCount": total,
            "matchedPosts": matched,
            "sampledAt": _now_iso(),
        }

    async def poll(self, client: httpx.AsyncClient) -> None:
        """Refresh every mapped provider. Per-provider failures are isolated."""
        now = time.monotonic()
        for provider in self._providers:
            # Cache guard: skip a refetch if we polled within the interval
            # (defends against the loop firing faster than COMMUNITY_INTERVAL).
            last = self._last_poll.get(provider)
            if last is not None and now - last < config.COMMUNITY_INTERVAL:
                continue
            try:
                self._latest[provider] = await self._poll_one(client, provider)
            except Exception:  # belt-and-suspenders; _poll_one shouldn't raise
                log.exception("community poll failed for %s", provider)
                self._latest[provider] = _unavailable_signal(
                    provider, SUBREDDITS[provider][0]
                )
            self._last_poll[provider] = time.monotonic()

    def signals(self) -> list[dict]:
        """Latest cached signal per provider (the cache the snapshot serves)."""
        return [self._latest[n] for n in self._providers]

    def by_provider(self) -> dict[str, dict]:
        """Map provider name -> latest signal, for attribution lookups."""
        return dict(self._latest)
