"""Tests for Downdetector corroboration (parsing, spike logic, hub merge)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx

from app import config
from app.community_downdetector import (
    _create_browserbase_session,
    _parse_summary_response,
    compute_spike,
    count_recent_timestamps,
    enabled,
    fetch_provider_signal,
    filter_recent_comments,
    headline_indicates_problem,
    _extract_headline,
    _relative_hours,
    _smoke_prereqs_ok,
)
from app.community_hub import CommunityHubState
from app.community_shared import merge_provider_signal


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestParsing:
    def test_relative_hours(self):
        assert _relative_hours("just now") == 0.0
        assert _relative_hours("30 minutes ago") == 0.5
        assert _relative_hours("3 hours ago") == 3.0
        assert _relative_hours("2 days ago") is None

    def test_headline_problem(self):
        ok = "User reports indicate possible problems at OpenAI"
        calm = "User reports show no current problems with OpenAI"
        assert headline_indicates_problem(ok) is True
        assert headline_indicates_problem(calm) is False

    def test_extract_headline(self):
        body = "Skip\nUser reports show no current problems with OpenAI\nMore"
        assert "no current problems" in _extract_headline(body)

    def test_filter_recent(self):
        comments = [
            {"text": "a", "age": "2 hours ago"},
            {"text": "b", "age": "2 days ago"},
            {"text": "c", "age": "just now"},
        ]
        kept = filter_recent_comments(comments, recent_hours=24)
        assert len(kept) == 2
        assert kept[0]["text"] == "a"

    def test_count_recent_timestamps(self):
        section = (
            "SomeUser\nError in message stream\n3 hours ago\n"
            "OtherUser\nCan't log in\n2 days ago\n"
            "Another\nAPI down\njust now\n"
        )
        assert count_recent_timestamps(section, recent_hours=24) == 2

    def test_compute_spike(self):
        assert compute_spike(headline_problem=True, recent_count=0) is True
        assert compute_spike(headline_problem=False, recent_count=5) is True
        assert compute_spike(headline_problem=False, recent_count=4) is False
        assert compute_spike(headline_problem=False, recent_count=2, problems_found=True) is True
        assert compute_spike(headline_problem=False, recent_count=2, problems_found=False) is False


class TestSummaryParse:
    def test_parse_json(self):
        out = _parse_summary_response(
            '{"problems_found": true, "summary": "Users report login failures."}'
        )
        assert out == {
            "problems_found": True,
            "summary": "Users report login failures.",
            "comments": [],
        }

    def test_parse_with_comments(self):
        out = _parse_summary_response(
            '{"problems_found": true, '
            '"summary": "Users report chat failures.", '
            '"comments": ['
            '{"age": "3 hours ago", "body": "Error in message stream on every device."}, '
            '{"age": "1 hour ago", "body": "x"}, '
            '{"age": "5 hours ago", "body": "Can log in but cannot send any message."}'
            "]}"
        )
        assert out is not None
        assert out["problems_found"] is True
        assert len(out["comments"]) == 2
        assert out["comments"][0]["text"] == "Error in message stream on every device."
        assert out["comments"][0]["age"] == "3 hours ago"

    def test_parse_skips_username_only_bodies(self):
        out = _parse_summary_response(
            '{"problems_found": false, "summary": "Mixed chatter.", '
            '"comments": [{"age": "2 hours ago", "body": "jsmith"}]}'
        )
        assert out == {
            "problems_found": False,
            "summary": "Mixed chatter.",
            "comments": [],
        }

    def test_parse_fenced_json(self):
        out = _parse_summary_response(
            '```json\n{"problems_found": false, "summary": "No clear pattern."}\n```'
        )
        assert out == {
            "problems_found": False,
            "summary": "No clear pattern.",
            "comments": [],
        }

    def test_parse_invalid_returns_none(self):
        assert _parse_summary_response("not json") is None
        assert _parse_summary_response('{"problems_found": true}') is None


class TestMerge:
    def test_merge_adds_downdetector_source_and_spike(self):
        hn = {
            "providerId": "GPT",
            "source": "hackernews",
            "status": "normal",
            "complaintRate": 0.1,
            "baseline": 0.08,
            "postCount": 10,
            "matchedPosts": 1,
            "searchQuery": "OpenAI",
            "lookbackHours": 24,
            "sampledAt": "2026-01-01T00:00:00+00:00",
        }
        dd = {
            "source": "Downdetector",
            "count": 6,
            "spike": True,
            "headline": "User reports indicate problems",
            "summary": "Login failures.",
            "comments": [{"text": "can't log in", "age": "1 hour ago"}],
            "url": "https://downdetector.com/status/openai/#comments",
        }
        merged = merge_provider_signal(hn, dd)
        assert merged["status"] == "spike"
        assert "Downdetector" in merged["source"]
        assert len(merged["sources"]) == 2
        assert merged["sources"][1]["source"] == "Downdetector"
        assert merged["complaintRate"] == 0.1

    def test_merge_hn_only_when_no_dd(self):
        hn = {
            "providerId": "Claude",
            "source": "hackernews",
            "status": "spike",
            "complaintRate": 0.5,
            "baseline": 0.1,
            "postCount": 20,
            "matchedPosts": 10,
            "searchQuery": "Claude",
            "lookbackHours": 24,
            "sampledAt": None,
        }
        merged = merge_provider_signal(hn, None)
        assert merged["status"] == "spike"
        assert merged["source"] == "hackernews"
        assert len(merged["sources"]) == 1


class TestEnabled:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.setattr(config, "DOWNDETECTOR_ENABLED", False)
        monkeypatch.setattr(config, "BROWSERBASE_API_KEY", "bb-key")
        assert enabled() is False

    def test_requires_api_key(self, monkeypatch):
        monkeypatch.setattr(config, "DOWNDETECTOR_ENABLED", True)
        monkeypatch.setattr(config, "BROWSERBASE_API_KEY", None)
        assert enabled() is False


class TestHubPolling:
    def test_polls_dd_for_all_providers_when_operational(self, monkeypatch):
        monkeypatch.setattr(config, "DOWNDETECTOR_ENABLED", True)
        monkeypatch.setattr(config, "BROWSERBASE_API_KEY", "bb-key")

        hub = CommunityHubState(["GPT", "Claude"])

        with patch(
            "app.community_hub.fetch_provider_signal",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_dd:
            async def main():
                async with httpx.AsyncClient() as client:
                    await hub.poll(client)

            _run(main())
            assert mock_dd.call_count == 2
            for name in ("GPT", "Claude"):
                sig = hub.by_provider()[name]
                assert len(sig.get("sources", [])) == 1

    def test_keeps_previous_dd_on_fetch_failure(self, monkeypatch):
        monkeypatch.setattr(config, "DOWNDETECTOR_ENABLED", True)
        monkeypatch.setattr(config, "BROWSERBASE_API_KEY", "bb-key")

        hub = CommunityHubState(["GPT"])
        prior = {
            "source": "Downdetector",
            "count": 3,
            "spike": False,
            "headline": "User reports indicate no current problems",
            "summary": "Quiet cycle.",
            "comments": [],
            "url": "https://downdetector.com/status/openai/#comments",
        }
        hub._dd_latest["GPT"] = prior

        with patch(
            "app.community_hub.fetch_provider_signal",
            new_callable=AsyncMock,
            return_value=None,
        ):
            async def main():
                async with httpx.AsyncClient() as client:
                    await hub.poll(client)

            _run(main())
            sig = hub.by_provider()["GPT"]
            assert any(s.get("source") == "Downdetector" for s in sig["sources"])
            dd = next(s for s in sig["sources"] if s["source"] == "Downdetector")
            assert dd["count"] == 3
            assert dd["headline"] == prior["headline"]

    def test_polls_dd_for_faulting_provider(self, monkeypatch):
        monkeypatch.setattr(config, "DOWNDETECTOR_ENABLED", True)
        monkeypatch.setattr(config, "BROWSERBASE_API_KEY", "bb-key")

        hub = CommunityHubState(["GPT"])

        dd_entry = {
            "source": "Downdetector",
            "count": 7,
            "spike": True,
            "headline": "User reports indicate problems",
            "summary": None,
            "comments": [],
            "url": "https://downdetector.com/status/openai/#comments",
        }

        with patch(
            "app.community_hub.fetch_provider_signal",
            new_callable=AsyncMock,
            return_value=dd_entry,
        ) as mock_dd:
            async def main():
                def hn_handler(request: httpx.Request) -> httpx.Response:
                    return httpx.Response(200, json={"hits": []})

                transport = httpx.MockTransport(hn_handler)
                async with httpx.AsyncClient(transport=transport) as client:
                    await hub.poll(client)

            _run(main())
            mock_dd.assert_called_once()
            sig = hub.by_provider()["GPT"]
            assert sig["status"] == "spike"
            assert any(s.get("source") == "Downdetector" for s in sig["sources"])


class TestFetchGraceful:
    def test_returns_none_when_disabled(self, monkeypatch):
        monkeypatch.setattr(config, "DOWNDETECTOR_ENABLED", False)

        async def main():
            async with httpx.AsyncClient() as client:
                return await fetch_provider_signal(client, "GPT")

        assert _run(main()) is None


class TestBrowserbaseSession:
    def test_accepts_201_created(self, monkeypatch):
        monkeypatch.setattr(config, "BROWSERBASE_API_KEY", "test-key")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                201,
                json={"id": "sess-1", "connectUrl": "wss://connect.example"},
            )

        async def main():
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                return await _create_browserbase_session(client)

        session = _run(main())
        assert session == {"id": "sess-1", "connectUrl": "wss://connect.example"}

    def test_rejects_non_success(self, monkeypatch):
        monkeypatch.setattr(config, "BROWSERBASE_API_KEY", "test-key")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="rate limited")

        async def main():
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                return await _create_browserbase_session(client)

        assert _run(main()) is None


class TestSmokeCli:
    def test_prereqs_missing_enabled(self, monkeypatch):
        monkeypatch.setattr(config, "DOWNDETECTOR_ENABLED", False)
        monkeypatch.setattr(config, "BROWSERBASE_API_KEY", "key")
        assert "DOWNDETECTOR_ENABLED" in (_smoke_prereqs_ok() or "")

    def test_prereqs_missing_api_key(self, monkeypatch):
        monkeypatch.setattr(config, "DOWNDETECTOR_ENABLED", True)
        monkeypatch.setattr(config, "BROWSERBASE_API_KEY", None)
        assert "BROWSERBASE_API_KEY" in (_smoke_prereqs_ok() or "")

    def test_cli_exits_when_prereqs_missing(self, monkeypatch, capsys):
        from app.community_downdetector import _smoke_main

        monkeypatch.setattr(config, "DOWNDETECTOR_ENABLED", False)
        monkeypatch.setattr(config, "BROWSERBASE_API_KEY", None)
        code = _smoke_main(["--provider", "GPT"])
        assert code == 1
        assert "DOWNDETECTOR_ENABLED" in capsys.readouterr().err
