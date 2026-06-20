"""Offline tests for dynamic model discovery + tier selection.

No network: pure selection rules plus httpx.MockTransport for the list/probe
HTTP paths. Run with `PYTHONPATH=. .venv/bin/python tests/test_discovery.py`
(or pytest)."""
import asyncio
from unittest.mock import patch

import httpx

from app import config, probes

ANTHROPIC_IDS = [
    "claude-3-haiku-20240307",
    "claude-3-opus-20240229",
    "claude-3-5-sonnet-20240620",
    "claude-3-5-sonnet-20241022",
    "claude-3-7-sonnet-20250219",
    "claude-opus-4-20250514",
    "claude-opus-4-1-20250805",
    "claude-sonnet-4-20250514",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
]


def test_anthropic_selection():
    sel = probes._select_anthropic(ANTHROPIC_IDS)
    assert sel == {
        "flagship": "claude-opus-4-1-20250805",
        "mid": "claude-sonnet-4-5-20250929",
    }, sel


def test_version_key_ordering():
    vk = probes._version_key
    assert vk("claude-opus-4-1-20250805") > vk("claude-opus-4-20250514")
    assert vk("claude-opus-4-20250514") > vk("claude-3-opus-20240229")
    assert vk("claude-sonnet-4-5-20250929") > vk("claude-3-7-sonnet-20250219")


def test_openai_selection():
    models = [
        "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4.1", "gpt-4.1-mini",
        "gpt-5", "gpt-5-mini", "gpt-5-pro", "gpt-3.5-turbo", "o1", "o3-mini",
        "chatgpt-4o-latest", "gpt-4o-audio-preview", "gpt-4o-realtime-preview",
        "text-embedding-3-large", "dall-e-3", "tts-1",
    ]
    sel = probes._select_openai(models)
    # gpt-5-pro is responses-only -> excluded; flagship is plain gpt-5.
    assert sel == {"flagship": "gpt-5", "mid": "gpt-5-mini"}, sel


def test_openai_mini_fallback():
    sel = probes._select_openai(["gpt-4o", "gpt-4-turbo", "gpt-4.1-mini"])
    assert sel["mid"] == "gpt-4.1-mini", sel


def test_gemini_selection():
    models = [
        "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.5-flash-8b",
        "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.5-pro",
        "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-pro-vision",
        # non-gemini entry that only supports other APIs -> must be ignored
        "deep-research-pro-preview-12-2025",
    ]
    sel = probes._select_gemini(models)
    assert sel == {"flagship": "gemini-2.5-pro", "mid": "gemini-2.5-flash"}, sel


def test_gemini_lite_excluded():
    sel = probes._select_gemini(["gemini-2.0-flash-lite", "gemini-1.5-flash"])
    assert sel["mid"] == "gemini-1.5-flash", sel


def _run_async(coro):
    return asyncio.run(coro)


def test_discover_live_then_fallback():
    async def main():
        with patch.object(config, "ANTHROPIC_API_KEY", "test-key"):
            claude = next(p for p in probes.PROVIDERS if p["id"] == "claude")

            ok = httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(200, json={"data": [{"id": i} for i in ANTHROPIC_IDS]})
                )
            )
            assert await probes.discover_models(ok, claude) == {
                "flagship": "claude-opus-4-1-20250805",
                "mid": "claude-sonnet-4-5-20250929",
            }
            await ok.aclose()

            bad = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(401, json={})))
            assert await probes.discover_models(bad, claude) == {
                "flagship": config.ANTHROPIC_MODEL,
                "mid": config.ANTHROPIC_MODEL_MID,
            }
            await bad.aclose()

    _run_async(main())


def test_list_gemini_strips_prefix_and_filters():
    async def main():
        with patch.object(config, "GEMINI_API_KEY", "k"):
            c = httpx.AsyncClient(
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(200, json={"models": [
                        {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
                        {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                        {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
                    ]})
                )
            )
            assert await probes._list_gemini(c) == ["gemini-2.5-pro", "gemini-2.5-flash"]
            await c.aclose()

    _run_async(main())


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n{len(tests)} tests passed")
