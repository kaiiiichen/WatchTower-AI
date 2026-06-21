"""Shared constants and helpers for community corroboration sources.

HN (community.py) stays untouched; additional sources import from here."""
from __future__ import annotations

from .community import PROVIDER_QUERIES

# Provider display names tracked by the community layer.
COMMUNITY_PROVIDERS: tuple[str, ...] = tuple(PROVIDER_QUERIES.keys())

# Search aliases per provider — reused by web corroboration sources.
PROVIDER_ALIASES: dict[str, tuple[str, ...]] = {
    name: queries for name, queries in PROVIDER_QUERIES.items()
}

# Probe statuses that trigger cost-aware corroboration fetches.
FAULTING_PROBE_STATUSES: frozenset[str] = frozenset({"degraded", "down"})


def faulting_providers(providers: list[dict]) -> set[str]:
    """Return provider names whose CURRENT probe status is degraded or down."""
    return {
        p["name"]
        for p in providers
        if p.get("name") in COMMUNITY_PROVIDERS
        and p.get("status") in FAULTING_PROBE_STATUSES
    }


def merge_source_label(hn_source: str, *, dd_spike: bool) -> str:
    """Extend the top-level `source` label when Downdetector corroborates."""
    if dd_spike:
        if hn_source and hn_source != "hackernews":
            return f"{hn_source},Downdetector"
        return "hackernews,Downdetector"
    return hn_source or "hackernews"


def merged_community_status(hn_status: str, *, dd_spike: bool) -> str:
    """Per-provider status: spike if ANY source spikes."""
    if hn_status == "spike" or dd_spike:
        return "spike"
    return hn_status


def build_hn_source_entry(hn_sig: dict) -> dict:
    """HN entry inside the per-provider `sources` list."""
    return {
        "source": "hackernews",
        "status": hn_sig.get("status", "unavailable"),
        "searchQuery": hn_sig.get("searchQuery"),
        "complaintRate": hn_sig.get("complaintRate", 0.0),
        "baseline": hn_sig.get("baseline", 0.0),
        "postCount": hn_sig.get("postCount", 0),
        "matchedPosts": hn_sig.get("matchedPosts", 0),
        "spike": hn_sig.get("status") == "spike",
    }


def merge_provider_signal(hn_sig: dict, dd_entry: dict | None) -> dict:
    """Merge HN top-level fields with optional Downdetector `sources` entry."""
    dd_spike = bool(dd_entry and dd_entry.get("spike"))
    sources: list[dict] = [build_hn_source_entry(hn_sig)]
    if dd_entry is not None:
        sources.append(dd_entry)

    merged = dict(hn_sig)
    merged["source"] = merge_source_label(hn_sig.get("source", "hackernews"), dd_spike=dd_spike)
    merged["status"] = merged_community_status(hn_sig.get("status", "unavailable"), dd_spike=dd_spike)
    merged["sources"] = sources
    return merged
