"""Community-signal hub — merges HN (community.py) with optional Downdetector.

HN polling is unchanged. When enabled, Downdetector runs for every provider each
cycle. Corroboration only; failures degrade gracefully."""
from __future__ import annotations

import logging

import httpx

from .community import CommunityState
from .community_downdetector import enabled as dd_enabled
from .community_downdetector import fetch_provider_signal
from .community_shared import merge_provider_signal

log = logging.getLogger("watchtower.community.hub")


class CommunityHubState:
    """Facade used by main.py / ProbeState — same interface as CommunityState."""

    def __init__(self, provider_names: list[str]) -> None:
        self._hn = CommunityState(provider_names)
        self._dd_latest: dict[str, dict | None] = {n: None for n in self._hn._providers}

    async def poll(self, client: httpx.AsyncClient) -> None:
        await self._hn.poll(client)

        if not dd_enabled():
            for provider in self._hn._providers:
                self._dd_latest[provider] = None
            return

        for provider in self._hn._providers:
            try:
                fresh = await fetch_provider_signal(client, provider)
            except Exception:
                log.exception("downdetector poll failed for %s", provider)
                continue
            if fresh is not None:
                self._dd_latest[provider] = fresh
            elif self._dd_latest.get(provider) is not None:
                log.info(
                    "downdetector %s: no data this cycle — keeping previous result",
                    provider,
                )

    def signals(self) -> list[dict]:
        return [self._merged_for(p) for p in self._hn._providers]

    def by_provider(self) -> dict[str, dict]:
        return {p: self._merged_for(p) for p in self._hn._providers}

    def _merged_for(self, provider: str) -> dict:
        hn_sig = self._hn.by_provider().get(provider)
        if hn_sig is None:
            return {
                "providerId": provider,
                "source": "hackernews",
                "status": "unavailable",
                "complaintRate": 0.0,
                "baseline": 0.0,
                "postCount": 0,
                "matchedPosts": 0,
                "lookbackHours": 24,
                "searchQuery": None,
                "sampledAt": None,
                "sources": [],
            }
        dd_entry = self._dd_latest.get(provider)
        return merge_provider_signal(hn_sig, dd_entry)
