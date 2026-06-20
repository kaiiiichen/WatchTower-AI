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

QA_QUESTION = "What is 2+2? Answer with just the number."
QA_EXPECTED = "4"

CORS_ORIGINS = _origins()

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
