"""Environment-driven configuration. Missing API keys are fine — the matching
provider is reported as `unknown` rather than crashing the probe loop.

Model names are discovered dynamically at startup (see probes.discover_models).
The *_MODEL / *_MODEL_MID values here are only fallbacks used when discovery
fails or no key is present."""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("watchtower.config")


def _origins() -> list[str]:
    raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


def _env_int(name: str, default: str) -> int:
    raw = os.getenv(name, default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        log.warning("Invalid integer for %s=%r, falling back to %s", name, raw, default)
        return int(default)


def _env_float(name: str, default: str) -> float:
    raw = os.getenv(name, default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        log.warning("Invalid float for %s=%r, falling back to %s", name, raw, default)
        return float(default)


# Probe cadence (seconds). Matches the frontend's 30s polling.
PROBE_INTERVAL = _env_int("PROBE_INTERVAL", "30")
# Points kept per probe target for the sparkline.
HISTORY_LEN = _env_int("HISTORY_LEN", "20")
# Per-request timeout for a single probe.
PROBE_TIMEOUT = _env_float("PROBE_TIMEOUT", "20")
# Per-check timeout for local diagnostics (DNS/TCP/key) — kept short so /diagnose
# stays snappy and a hung check degrades to "unknown" quickly.
DIAGNOSTIC_TIMEOUT = _env_float("DIAGNOSTIC_TIMEOUT", "5")

# --- Trend warning ("degrading" precursor) --------------------------------
# Pre-emptive signal: flag a still-healthy provider whose latency is steadily
# climbing, BEFORE it crosses into degraded/down. Thresholds are deliberately
# conservative so normal latency jitter doesn't trigger false warnings.
TREND_WINDOW = _env_int("TREND_WINDOW", "5")  # last N probes to inspect
# A "rising" trend needs ALL of: mostly-monotonic climb, a big relative rise,
# and a meaningful absolute rise — so jitter on a fast provider can't trip it.
TREND_ALLOWED_DIPS = _env_int("TREND_ALLOWED_DIPS", "1")  # non-increasing steps tolerated
TREND_MIN_RISE_RATIO = _env_float("TREND_MIN_RISE_RATIO", "0.5")  # >=50% over the window
TREND_MIN_RISE_MS = _env_int("TREND_MIN_RISE_MS", "200")  # and >=200ms absolute

# Disable OpenAPI/docs in production (set ENABLE_DOCS=1 for local dev).
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "").strip() in ("1", "true", "yes")

QA_QUESTION = "What is 2+2? Answer with just the number."
QA_EXPECTED = "4"

CORS_ORIGINS = _origins()
CORS_ALLOW_HEADERS = ["Content-Type", "Accept"]

# API keys (None when unset -> provider marked `unknown`).
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

# Fallback models (used only if dynamic discovery fails). flagship + mid tiers.
# "" / None for a mid tier -> that tier is simply not probed.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-1")
ANTHROPIC_MODEL_MID = os.getenv("ANTHROPIC_MODEL_MID", "claude-sonnet-4-5")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_MODEL_MID = os.getenv("OPENAI_MODEL_MID", "gpt-4o-mini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
GEMINI_MODEL_MID = os.getenv("GEMINI_MODEL_MID", "gemini-1.5-flash")

# --- Community signals (Reddit) --------------------------------------------
# Corroboration layer, NOT a dependency: if Reddit is unreachable the probe
# pipeline is unaffected and signals report "unavailable".
#
# Reddit's public JSON needs no auth but DOES require a unique User-Agent or it
# rate-limits hard (HTTP 429). Format: "platform:app-id:version (by /u/user)".
REDDIT_USER_AGENT = os.getenv(
    "REDDIT_USER_AGENT", "python:watchtower-ai:v1.0 (by /u/watchtower_ai)"
)
# How often to poll Reddit (seconds). Kept well above Reddit's rate-limit floor.
COMMUNITY_INTERVAL = _env_int("COMMUNITY_INTERVAL", "60")

# --- Official status pages (Statuspage JSON) -------------------------------
# Polls less often than probes — official pages update on minute-scale cadence.
OFFICIAL_STATUS_INTERVAL = _env_int("OFFICIAL_STATUS_INTERVAL", "120")
# Posts pulled per subreddit per poll.
COMMUNITY_POST_LIMIT = _env_int("COMMUNITY_POST_LIMIT", "25")
# Rolling complaint-rate samples kept per subreddit for the spike baseline.
COMMUNITY_BASELINE_LEN = _env_int("COMMUNITY_BASELINE_LEN", "20")
# Min samples before a baseline is trustworthy enough to flag a spike.
COMMUNITY_MIN_BASELINE = _env_int("COMMUNITY_MIN_BASELINE", "3")
# A "spike" needs the rate both meaningfully high in absolute terms ...
COMMUNITY_SPIKE_MIN_RATE = _env_float("COMMUNITY_SPIKE_MIN_RATE", "0.28")
# ... and clearly above its own rolling baseline (factor + absolute delta).
COMMUNITY_SPIKE_FACTOR = _env_float("COMMUNITY_SPIKE_FACTOR", "2.0")
COMMUNITY_SPIKE_DELTA = _env_float("COMMUNITY_SPIKE_DELTA", "0.12")
# "elevated" (noteworthy but not confirmed) sits between baseline and spike.
COMMUNITY_ELEVATED_DELTA = _env_float("COMMUNITY_ELEVATED_DELTA", "0.06")

# --- Sentry ----------------------------------------------------------------
# SENTRY_DSN unset -> Sentry is disabled (capture/spans become no-ops).
SENTRY_DSN = os.getenv("SENTRY_DSN")
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "watchtower")
SENTRY_TRACES_SAMPLE_RATE = _env_float("SENTRY_TRACES_SAMPLE_RATE", "1.0")
