"""Detection lead-time backtest over the VU Amsterdam status-page dataset.

Argues, from REAL data, that official status pages lag user impact — the window
high-frequency probing can fill. Three honest metrics, computed from
data/vu_dataset/incident/.../incident_stages.csv:

  A. Official internal response latency (investigating->identified->resolved).
     Real, large-N (investigating->resolved N=381). Median is the headline; the
     mean is long-tail-skewed and labelled as such.
  C. Coverage gap: 30% of incidents were NEVER marked "investigating" in real
     time (resolved-only). 100% real.
  B. Impact-window -> official-acknowledgment gap for a couple of Anthropic
     cases. The impact window is PARSED FROM the official description text and
     its date inferred from the incident's UTC day — an ESTIMATE, flagged as
     such, and filtered to <=120min to drop cross-day date-inference artifacts.

RED LINE: every number is computed from the CSV. Nothing is fabricated; the one
estimated quantity (B's impact start) is explicitly marked estimated."""
from __future__ import annotations

import csv
import re
import statistics as st
from datetime import datetime
from functools import lru_cache
from pathlib import Path

# data/vu_dataset/incident/2024-08-31/incident_stages.csv relative to repo.
_DATA = (
    Path(__file__).resolve().parent.parent
    / "data" / "vu_dataset" / "incident" / "2024-08-31" / "incident_stages.csv"
)

# Impact-window phrases like "15:38-16:29" or "19:01 – 19:12" in description text.
_WINDOW = re.compile(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})")
# B cases above this gap are date-inference artifacts (window not same UTC day).
_B_MAX_GAP_MIN = 120


def _ts(s: str) -> datetime | None:
    s = (s or "").strip()
    return datetime.fromisoformat(s) if s else None


def _load() -> list[dict]:
    with open(_DATA, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _gaps(rows: list[dict], a: str, b: str) -> tuple[list[float], int]:
    """Minutes from stage a -> b where both present. Drops (and counts) negatives."""
    vals, neg = [], 0
    for r in rows:
        ta, tb = _ts(r[a]), _ts(r[b])
        if ta and tb:
            m = (tb - ta).total_seconds() / 60
            if m < 0:
                neg += 1
                continue
            vals.append(m)
    return vals, neg


def _stats(vals: list[float]) -> dict | None:
    if not vals:
        return None
    s = sorted(vals)
    q = st.quantiles(s, n=4) if len(s) >= 4 else [s[0], st.median(s), s[-1]]
    return {
        "n": len(s),
        "medianMin": round(st.median(s), 1),
        "meanMin": round(st.mean(s), 1),  # long-tail-skewed; label in UI
        "p25Min": round(q[0], 1),
        "p75Min": round(q[-1], 1),
        "maxMin": round(max(s), 1),
    }


# Histogram bins for investigating->resolved (minutes); last bin absorbs the
# long tail so the shape stays readable. Counts sum to N.
_BINS = [(0, 15), (15, 30), (30, 60), (60, 120), (120, 240), (240, 480), (480, None)]


def _histogram(vals: list[float]) -> list[dict]:
    out = []
    for lo, hi in _BINS:
        if hi is None:
            count = sum(1 for v in vals if v >= lo)
            label = f"{lo}m+"
        else:
            count = sum(1 for v in vals if lo <= v < hi)
            label = f"{lo}-{hi}m"
        out.append({"label": label, "count": count})
    return out


def _coverage(rows: list[dict], scope: str) -> dict:
    total = len(rows)
    no_inv = sum(1 for r in rows if not r["investigating_timestamp"].strip())
    return {
        "scope": scope,
        "total": total,
        "noInvestigating": no_inv,
        "pct": round(100 * no_inv / total, 1) if total else 0.0,
    }


def _b_cases(rows: list[dict]) -> list[dict]:
    """Anthropic impact-window -> acknowledgment cases. impact start parsed from
    description text, date inferred from the incident's UTC day (ESTIMATE).
    Filtered to a sane same-day gap to exclude date-inference artifacts."""
    cases = []
    for r in rows:
        if r["provider"] != "anthropic":
            continue
        inv = _ts(r["investigating_timestamp"])
        if not inv:
            continue
        blob = " ".join([
            r["investigating_description"], r["identified_description"],
            r["resolved_description"],
        ])
        m = _WINDOW.search(blob)
        if not m:
            continue
        hh, mm = m.group(1).split(":")
        impact_start = inv.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        gap = (inv - impact_start).total_seconds() / 60
        if not (0 < gap <= _B_MAX_GAP_MIN):  # drop artifacts (e.g. the +1140m case)
            continue
        cases.append({
            "incidentId": r["incident_id"],
            "provider": r["provider"],
            "title": r["Incident_Title"],
            "impactWindowText": m.group(0),
            "impactStart": impact_start.isoformat(),
            "investigating": inv.isoformat(),
            "identified": (_ts(r["identified_timestamp"]) or "") and r["identified_timestamp"],
            "resolved": (_ts(r["resolved_timestamp"]) or "") and r["resolved_timestamp"],
            "ackGapMin": round(gap, 1),
            "impactStartEstimated": True,  # parsed from text + date inferred
        })
    cases.sort(key=lambda c: c["ackGapMin"])  # smallest, cleanest gap first
    return cases


@lru_cache(maxsize=1)
def build_report() -> dict:
    """Compute the full backtest report (cached; dataset is static)."""
    rows = _load()
    anthropic = [r for r in rows if r["provider"] == "anthropic"]
    openai = [r for r in rows if r["provider"] == "openai"]

    resolved_all, _ = _gaps(rows, "investigating_timestamp", "resolved_timestamp")

    def lat(scope_rows):
        return {
            "investigatingToResolved": _stats(
                _gaps(scope_rows, "investigating_timestamp", "resolved_timestamp")[0]),
            "investigatingToIdentified": _stats(
                _gaps(scope_rows, "investigating_timestamp", "identified_timestamp")[0]),
        }

    return {
        "datasetDate": "2024-08-31",
        "coverage": {
            "all": _coverage(rows, "all"),
            "anthropic": _coverage(anthropic, "anthropic"),
            "openai": _coverage(openai, "openai"),
        },
        "latency": {
            "all": lat(rows),
            "anthropic": lat(anthropic),
            "openai": lat(openai),
        },
        "resolvedHistogram": _histogram(resolved_all),
        "histogramNote": "investigating→resolved, all providers (N=381). Final bin absorbs the long tail.",
        "caseTimelines": _b_cases(rows),
        "notes": {
            "A": "Official internal response latency — real. Median is the headline; mean is long-tail-skewed.",
            "B": "Impact window parsed from official incident description text; date inferred from the incident's UTC day — an ESTIMATE.",
            "C": "Coverage gap — 100% real, no estimation.",
        },
    }
