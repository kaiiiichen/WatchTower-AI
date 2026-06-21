"""Tests for the Reddit community-signal module.

Cover keyword counting, complaint rate, spike classification against a rolling
baseline, graceful degradation (the core principle: Reddit failures never crash
the pipeline), caching, and the attribution upgrade in _build_alerts."""
import asyncio

import httpx

from app import config
from app.community import (
    CommunityState,
    classify,
    complaint_rate,
    count_complaints,
    fetch_subreddit,
)
from app.probes import _build_alerts


def _run_async(coro):
    # Match the repo's async-test idiom (see test_discovery) rather than the
    # pytest-asyncio marker, which closes the shared loop the legacy tests reuse.
    return asyncio.get_event_loop().run_until_complete(coro)


def _posts(*titles, bodies=None):
    bodies = bodies or [""] * len(titles)
    return [{"title": t, "body": b} for t, b in zip(titles, bodies)]


# --- keyword counting / complaint rate -------------------------------------

class TestKeywords:
    def test_matches_title_keyword(self):
        matched, total = count_complaints(_posts("Claude is down again", "love it"))
        assert (matched, total) == (1, 2)

    def test_matches_body_keyword(self):
        posts = _posts("Question", bodies=["anyone else getting an error?"])
        assert count_complaints(posts) == (1, 1)

    def test_multiword_phrase(self):
        assert count_complaints(_posts("is it just me or is it slow"))[0] == 1

    def test_case_insensitive(self):
        assert count_complaints(_posts("OUTAGE right now"))[0] == 1

    def test_no_keywords(self):
        assert count_complaints(_posts("great model", "love the new update")) == (0, 2)

    def test_complaint_rate(self):
        assert complaint_rate(_posts("down", "fine", "broken", "ok")) == 0.5

    def test_complaint_rate_empty(self):
        assert complaint_rate([]) == 0.0


# --- spike classification --------------------------------------------------

class TestClassify:
    def test_spike_when_high_and_above_baseline(self):
        baseline = [0.05, 0.06, 0.07, 0.05]  # calm history
        assert classify(0.5, baseline) == "spike"

    def test_no_spike_without_enough_baseline(self):
        # Too few samples to trust -> at most "elevated", never "spike".
        assert classify(0.5, [0.05]) == "elevated"

    def test_normal_when_near_baseline(self):
        baseline = [0.2, 0.22, 0.18, 0.21]
        assert classify(0.22, baseline) == "normal"

    def test_high_baseline_suppresses_spike(self):
        # A chronically noisy subreddit: 0.4 isn't a spike if baseline ~0.38.
        baseline = [0.38, 0.4, 0.37, 0.39]
        assert classify(0.4, baseline) == "normal"

    def test_elevated_between_normal_and_spike(self):
        baseline = [0.05, 0.06, 0.05, 0.06]
        # Above baseline by >ELEVATED_DELTA but below absolute spike floor.
        assert classify(0.16, baseline) == "elevated"


# --- fetch + graceful degradation ------------------------------------------

def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_fetch_returns_none_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    async def main():
        async with _client(handler) as client:
            assert await fetch_subreddit(client, "ClaudeAI") is None

    _run_async(main())


def test_fetch_returns_none_on_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    async def main():
        async with _client(handler) as client:
            assert await fetch_subreddit(client, "ClaudeAI") is None

    _run_async(main())


def test_fetch_sends_required_user_agent():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["ua"] = request.headers.get("user-agent")
        return httpx.Response(200, json={"data": {"children": []}})

    async def main():
        async with _client(handler) as client:
            await fetch_subreddit(client, "ClaudeAI")

    _run_async(main())
    assert seen["ua"] == config.REDDIT_USER_AGENT
    assert "watchtower" in seen["ua"]


def test_fetch_parses_listing():
    payload = {
        "data": {
            "children": [
                {"data": {"title": "Claude down", "selftext": ""}},
                {"data": {"title": "nice", "selftext": "broken for me"}},
            ]
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async def main():
        async with _client(handler) as client:
            return await fetch_subreddit(client, "ClaudeAI")

    posts = _run_async(main())
    assert count_complaints(posts) == (2, 2)


# --- CommunityState: polling, caching, degradation -------------------------

def _spike_payload():
    children = [{"data": {"title": "Claude is down", "selftext": ""}} for _ in range(12)]
    children += [{"data": {"title": "thanks", "selftext": ""}} for _ in range(13)]
    return {"data": {"children": children}}


def test_state_only_maps_known_providers():
    state = CommunityState(["Claude", "GPT", "Gemini", "Mystery"])
    sigs = state.signals()
    assert {s["providerId"] for s in sigs} == {"Claude", "GPT", "Gemini"}


def test_state_degrades_to_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async def main():
        async with _client(handler) as client:
            state = CommunityState(["Claude"])
            await state.poll(client)
            return state

    sig = _run_async(main()).by_provider()["Claude"]
    assert sig["status"] == "unavailable"
    assert sig["complaintRate"] == 0.0


def test_state_detects_spike_after_baseline():
    # Pre-seed a calm baseline so the next high reading reads as a spike.
    calm = {"data": {"children": [{"data": {"title": "love it", "selftext": ""}}] * 25}}
    payloads = [calm, calm, calm, _spike_payload()]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payloads.pop(0))

    async def main():
        async with _client(handler) as client:
            state = CommunityState(["Claude"])
            # Force a fresh poll each time by resetting the cache guard.
            for _ in range(4):
                state._last_poll.clear()
                await state.poll(client)
            return state

    sig = _run_async(main()).by_provider()["Claude"]
    assert sig["status"] == "spike"
    assert sig["matchedPosts"] == 12


def test_state_caches_within_interval():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"data": {"children": []}})

    async def main():
        async with _client(handler) as client:
            state = CommunityState(["Claude"])
            await state.poll(client)
            await state.poll(client)  # within interval -> cache hit, no refetch

    _run_async(main())
    assert calls["n"] == 1


# --- attribution upgrade ---------------------------------------------------

class TestAttributionUpgrade:
    def _impaired(self):
        return [
            {"id": "gemini-flagship", "name": "Gemini", "status": "down",
             "healthScore": 0, "latencyMs": 0, "qaCorrect": False,
             "tier": "flagship", "model": "gemini-3-pro"},
        ]

    def test_no_upgrade_without_community(self):
        alerts = _build_alerts(self._impaired())
        assert alerts[0]["communityConfirmed"] is False
        assert "CONFIRMED WIDESPREAD" not in alerts[0]["insight"]

    def test_upgrade_on_spike(self):
        community = {
            "Gemini": {"status": "spike", "subreddit": "Bard",
                       "complaintRate": 0.48, "baseline": 0.08, "postCount": 25},
        }
        alerts = _build_alerts(self._impaired(), community)
        assert alerts[0]["communityConfirmed"] is True
        assert "CONFIRMED WIDESPREAD" in alerts[0]["insight"]
        assert "status page" in alerts[0]["insight"]

    def test_no_upgrade_when_only_elevated(self):
        community = {"Gemini": {"status": "elevated", "subreddit": "Bard",
                                "complaintRate": 0.2, "baseline": 0.08, "postCount": 25}}
        alerts = _build_alerts(self._impaired(), community)
        assert alerts[0]["communityConfirmed"] is False

    def test_no_upgrade_when_unavailable(self):
        community = {"Gemini": {"status": "unavailable", "subreddit": "Bard",
                                "complaintRate": 0.0, "baseline": 0.0, "postCount": 0}}
        alerts = _build_alerts(self._impaired(), community)
        assert alerts[0]["communityConfirmed"] is False
