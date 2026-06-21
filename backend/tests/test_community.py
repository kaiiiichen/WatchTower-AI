"""Tests for the Hacker News community-signal module.

Cover keyword counting, complaint rate, spike classification against a rolling
baseline, graceful degradation (HN failures never crash the pipeline), caching,
and the attribution upgrade in _build_alerts."""
import asyncio

import httpx

from app import config
from app.community import (
    CommunityState,
    classify,
    complaint_rate,
    count_complaints,
    fetch_hn_stories,
)
from app.probes import _build_alerts


def _run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _posts(*titles, bodies=None):
    bodies = bodies or [""] * len(titles)
    return [{"title": t, "body": b} for t, b in zip(titles, bodies)]


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


class TestClassify:
    def test_spike_when_high_and_above_baseline(self):
        baseline = [0.05, 0.06, 0.07, 0.05]
        assert classify(0.5, baseline) == "spike"

    def test_no_spike_without_enough_baseline(self):
        assert classify(0.5, [0.05]) == "elevated"

    def test_normal_when_near_baseline(self):
        baseline = [0.2, 0.22, 0.18, 0.21]
        assert classify(0.22, baseline) == "normal"

    def test_high_baseline_suppresses_spike(self):
        baseline = [0.38, 0.4, 0.37, 0.39]
        assert classify(0.4, baseline) == "normal"

    def test_elevated_between_normal_and_spike(self):
        baseline = [0.05, 0.06, 0.05, 0.06]
        assert classify(0.16, baseline) == "elevated"


def _client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_fetch_returns_none_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")

    async def main():
        async with _client(handler) as client:
            assert await fetch_hn_stories(client, "Claude") is None

    _run_async(main())


def test_fetch_returns_none_on_network_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    async def main():
        async with _client(handler) as client:
            assert await fetch_hn_stories(client, "Claude") is None

    _run_async(main())


def test_fetch_uses_algolia_search_by_date():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["query"] = request.url.params.get("query")
        seen["tags"] = request.url.params.get("tags")
        return httpx.Response(200, json={"hits": []})

    async def main():
        async with _client(handler) as client:
            await fetch_hn_stories(client, "Anthropic Claude")

    _run_async(main())
    assert "search_by_date" in seen["url"]
    assert seen["query"] == "Anthropic Claude"
    assert seen["tags"] == "story"


def test_fetch_parses_hits():
    payload = {
        "hits": [
            {"title": "Claude down", "story_text": ""},
            {"title": "nice", "story_text": "broken for me"},
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async def main():
        async with _client(handler) as client:
            return await fetch_hn_stories(client, "Claude")

    posts = _run_async(main())
    assert count_complaints(posts) == (2, 2)


def _spike_payload():
    hits = [{"title": "Claude is down", "story_text": ""} for _ in range(12)]
    hits += [{"title": "thanks", "story_text": ""} for _ in range(13)]
    return {"hits": hits}


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
    assert sig["source"] == "hackernews"
    assert sig["complaintRate"] == 0.0


def test_state_detects_spike_after_baseline():
    calm = {"hits": [{"title": "love it", "story_text": ""} for _ in range(25)]}
    payloads = [calm, calm, calm, _spike_payload()]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payloads.pop(0))

    async def main():
        async with _client(handler) as client:
            state = CommunityState(["Claude"])
            for _ in range(4):
                state._last_poll.clear()
                await state.poll(client)
            return state

    sig = _run_async(main()).by_provider()["Claude"]
    assert sig["status"] == "spike"
    assert sig["matchedPosts"] == 12
    assert sig["searchQuery"] == "Anthropic Claude"


def test_state_caches_within_interval():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"hits": []})

    async def main():
        async with _client(handler) as client:
            state = CommunityState(["Claude"])
            await state.poll(client)
            await state.poll(client)

    _run_async(main())
    assert calls["n"] == 1


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

    def test_upgrade_on_hn_spike(self):
        community = {
            "Gemini": {
                "status": "spike",
                "searchQuery": "Google Gemini",
                "complaintRate": 0.48,
                "baseline": 0.08,
                "postCount": 25,
                "sources": [
                    {
                        "source": "hackernews",
                        "spike": True,
                        "postCount": 25,
                        "complaintRate": 0.48,
                    },
                ],
            },
        }
        alerts = _build_alerts(self._impaired(), community)
        assert alerts[0]["communityConfirmed"] is True
        assert "CONFIRMED WIDESPREAD" in alerts[0]["insight"]
        assert "Hacker News (25 posts, rate 0.48/hr)" in alerts[0]["insight"]

    def test_upgrade_on_downdetector_only_spike(self):
        community = {
            "Gemini": {
                "status": "spike",
                "complaintRate": 0.0,
                "baseline": 0.0,
                "postCount": 0,
                "sources": [
                    {"source": "hackernews", "spike": False, "postCount": 0, "complaintRate": 0.0},
                    {"source": "Downdetector", "spike": True, "count": 14},
                ],
            },
        }
        alerts = _build_alerts(self._impaired(), community)
        assert alerts[0]["communityConfirmed"] is True
        assert "Downdetector (14 recent reports)" in alerts[0]["insight"]
        assert "Hacker News" not in alerts[0]["insight"]

    def test_upgrade_on_both_sources_spike(self):
        community = {
            "Gemini": {
                "status": "spike",
                "sources": [
                    {"source": "hackernews", "spike": True, "postCount": 20, "complaintRate": 0.4},
                    {"source": "Downdetector", "spike": True, "count": 8},
                ],
            },
        }
        alerts = _build_alerts(self._impaired(), community)
        insight = alerts[0]["insight"]
        assert "Hacker News (20 posts, rate 0.4/hr) + Downdetector (8 recent reports)" in insight

    def test_upgrade_fallback_without_sources(self):
        community = {
            "Gemini": {"status": "spike", "searchQuery": "Google Gemini",
                       "complaintRate": 0.48, "baseline": 0.08, "postCount": 25},
        }
        alerts = _build_alerts(self._impaired(), community)
        assert "community signal" in alerts[0]["insight"]

    def test_no_upgrade_when_only_elevated(self):
        community = {"Gemini": {"status": "elevated", "searchQuery": "Google Gemini",
                                "complaintRate": 0.2, "baseline": 0.08, "postCount": 25}}
        alerts = _build_alerts(self._impaired(), community)
        assert alerts[0]["communityConfirmed"] is False

    def test_no_upgrade_when_unavailable(self):
        community = {"Gemini": {"status": "unavailable", "searchQuery": "Google Gemini",
                                "complaintRate": 0.0, "baseline": 0.0, "postCount": 0}}
        alerts = _build_alerts(self._impaired(), community)
        assert alerts[0]["communityConfirmed"] is False
