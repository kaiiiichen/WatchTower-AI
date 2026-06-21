"""Tests for the VU-dataset detection lead-time backtest.

These PIN the exact numbers the user reviewed and approved — if the computation
or dataset ever drifts, this fails loudly (the whole demo's credibility rests on
these being real and stable)."""
from app import backtest
from app.models import BacktestReport


def _report():
    backtest.build_report.cache_clear()
    return backtest.build_report()


def test_coverage_matches_approved():
    cov = _report()["coverage"]
    assert cov["all"] == {"scope": "all", "total": 542, "noInvestigating": 161, "pct": 29.7}
    assert cov["anthropic"]["pct"] == 31.9
    assert cov["openai"]["pct"] == 29.0


def test_latency_all_investigating_to_resolved():
    s = _report()["latency"]["all"]["investigatingToResolved"]
    assert s["n"] == 381
    assert s["medianMin"] == 73.0
    assert s["meanMin"] == 163.8  # long-tail-skewed
    assert s["maxMin"] == 4907.0


def test_latency_anthropic_and_identified():
    lat = _report()["latency"]
    assert lat["anthropic"]["investigatingToResolved"]["medianMin"] == 55.5
    assert lat["anthropic"]["investigatingToResolved"]["n"] == 96
    assert lat["all"]["investigatingToIdentified"]["n"] == 126
    assert lat["all"]["investigatingToIdentified"]["medianMin"] == 27.5


def test_histogram_counts_sum_to_N():
    hist = _report()["resolvedHistogram"]
    assert sum(b["count"] for b in hist) == 381


def test_b_cases_are_real_and_artifact_excluded():
    cases = _report()["caseTimelines"]
    # Exactly the two clean Anthropic cases; the +1140m openai date-artifact dropped.
    assert len(cases) == 2
    assert all(c["provider"] == "anthropic" for c in cases)
    assert all(0 < c["ackGapMin"] <= 120 for c in cases)
    assert all(c["impactStartEstimated"] is True for c in cases)
    primary = cases[0]  # smallest gap first
    assert primary["ackGapMin"] == 23.0
    assert "API" in primary["title"]
    assert primary["impactWindowText"].startswith("15:38")


def test_no_openai_artifact_leaks_in():
    # The +1140m openai case must never appear (it's a date-inference artifact).
    assert not any(c["ackGapMin"] > 120 for c in _report()["caseTimelines"])


def test_report_validates_against_model():
    BacktestReport(**_report())  # raises if the shape drifts
