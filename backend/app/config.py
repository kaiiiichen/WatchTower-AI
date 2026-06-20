"""Environment-driven configuration. Missing API keys are fine — the matching
provider is reported as `unknown` rather than crashing the probe loop.

Model names are discovered dynamically at startup (see probes.discover_models).
The *_MODEL / *_MODEL_MID values here are only fallbacks used when discovery
fails or no key is present."""
import os

from dotenv import load_dotenv

load_dotenv()


def _origins() -> list[str]:
    raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


# Probe cadence (seconds). Matches the frontend's 30s polling.
PROBE_INTERVAL = int(os.getenv("PROBE_INTERVAL", "30"))
# Points kept per probe target for the sparkline.
HISTORY_LEN = int(os.getenv("HISTORY_LEN", "20"))
# Per-request timeout for a single probe.
PROBE_TIMEOUT = float(os.getenv("PROBE_TIMEOUT", "20"))

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
