"""Downdetector community corroboration via Browserbase browser sessions.

Uses Playwright over CDP to a remote Browserbase browser (Cloudflare + JS).
CORROBORATION ONLY — disabled by default; never blocks the probe pipeline."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
from typing import Any

import httpx

from . import config
from .redaction import redact

log = logging.getLogger("watchtower.community.downdetector")

_COMMENT_TRUNC = 240
_COMMENT_SECTION_MAX = 12_000
_TIME_RE = re.compile(
    r"^(just now|\d+\s+minutes?\s+ago|\d+\s+hours?\s+ago|\d+\s+days?\s+ago)$",
    re.IGNORECASE,
)
_TIME_IN_TEXT_RE = re.compile(
    r"\b(just now|\d+\s+minutes?\s+ago|\d+\s+hours?\s+ago)\b",
    re.IGNORECASE,
)
_HEADLINE_RE = re.compile(r"user reports show[^\n.]{0,200}", re.IGNORECASE)

_EXTRACT_COMMENT_SECTION_JS = """
() => {
  const selectors = [
    '#comments',
    '[id*="comment" i]',
    'section[class*="comment" i]',
    'div[class*="comment" i]',
    '[data-testid*="comment" i]',
  ];
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    const text = (el && el.innerText) ? el.innerText.trim() : '';
    if (text.length > 80) return text.slice(0, 12000);
  }
  const body = (document.body && document.body.innerText) || '';
  const markers = [
    'What are you seeing?',
    'Most reported problems',
    'I have a problem with',
    'Reports',
  ];
  for (const marker of markers) {
    const idx = body.indexOf(marker);
    if (idx >= 0) return body.slice(idx, idx + 12000).trim();
  }
  return body.slice(0, 12000).trim();
}
"""


def enabled() -> bool:
    return config.DOWNDETECTOR_ENABLED and bool(config.BROWSERBASE_API_KEY)


def slug_for(provider: str) -> str | None:
    return config.DOWNDETECTOR_SLUGS.get(provider)


def _relative_hours(age: str) -> float | None:
    """Hours ago, or None if older than the recent window / unparseable."""
    low = age.strip().lower()
    if low == "just now":
        return 0.0
    m = re.match(r"(\d+)\s+minute", low)
    if m:
        return int(m.group(1)) / 60.0
    m = re.match(r"(\d+)\s+hour", low)
    if m:
        return float(int(m.group(1)))
    if re.match(r"\d+\s+day", low):
        return None
    return None


def _extract_headline(body_text: str) -> str:
    m = _HEADLINE_RE.search(body_text)
    return m.group(0).strip() if m else ""


def headline_indicates_problem(headline: str) -> bool:
    if not headline:
        return False
    return "no current problems" not in headline.lower()


def filter_recent_comments(
    comments: list[dict],
    *,
    recent_hours: int,
) -> list[dict]:
    kept: list[dict] = []
    for c in comments:
        hours = _relative_hours(c.get("age", ""))
        if hours is None or hours >= recent_hours:
            continue
        kept.append(c)
    return kept


def count_recent_timestamps(text: str, *, recent_hours: int) -> int:
    """Count recent (<recent_hours) time markers in raw comment-section text."""
    if not text:
        return 0
    count = 0
    for match in _TIME_IN_TEXT_RE.finditer(text):
        hours = _relative_hours(match.group(1))
        if hours is not None and hours < recent_hours:
            count += 1
    return count


def compute_spike(
    *,
    headline_problem: bool,
    recent_count: int,
    problems_found: bool = False,
) -> bool:
    return (
        headline_problem
        or recent_count >= config.DOWNDETECTOR_MIN_COMMENTS
        or problems_found
    )


def _analysis_prompt(comment_section: str) -> str:
    clipped = comment_section[:_COMMENT_SECTION_MAX]
    return (
        "You are parsing Downdetector user report comments for a service outage monitor.\n"
        "Below is raw text from the rendered comment section of a Downdetector status page.\n"
        "Reply with JSON only — no markdown, no extra text:\n"
        '{"problems_found": <true|false>, "summary": "<one or two sentences>", '
        '"comments": [{"age": "<relative time as shown>", "body": "<user complaint text>"}]}\n\n'
        "Rules for problems_found and summary:\n"
        "- Set problems_found to true ONLY if the comments describe a concrete CURRENT "
        "service problem (outage, errors, login failure, API down, etc.).\n"
        "- Do NOT set true for generic chatter, jokes, unrelated complaints, or "
        "vague frustration without a specific current failure.\n"
        "- If there is no clear current problem pattern, set problems_found to false "
        "and summary to a brief neutral description.\n"
        "- Do not speculate beyond the comment text.\n\n"
        "Rules for comments array (at most 3 entries):\n"
        "- Each \"body\" MUST be the user's actual complaint text — NOT their username, "
        "NOT their location, NOT boilerplate like \"I have a problem with …\".\n"
        "- \"age\" must be the relative timestamp exactly as shown (e.g. \"3 hours ago\").\n"
        "- Skip entries with no real complaint body; never use a username as the body.\n\n"
        "Raw comment section:\n"
        + clipped
    )


def _parse_summary_response(text: str) -> dict | None:
    """Parse LLM JSON into {problems_found, summary, comments?}. None on parse failure."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    summary = redact(str(data.get("summary", "")).strip())
    if not summary:
        return None

    display_comments: list[dict] = []
    for item in (data.get("comments") or [])[:3]:
        if not isinstance(item, dict):
            continue
        body = redact(str(item.get("body", "")).strip())
        age = str(item.get("age", "")).strip()
        if not body or len(body) < 8:
            continue
        display_comments.append(
            {"text": body[:_COMMENT_TRUNC], "age": age},
        )

    return {
        "problems_found": bool(data.get("problems_found")),
        "summary": summary,
        "comments": display_comments,
    }


async def _llm_summary_text(client: httpx.AsyncClient, prompt: str) -> str | None:
    model = config.DOWNDETECTOR_SUMMARY_MODEL
    try:
        if model.startswith("claude") and config.ANTHROPIC_API_KEY:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": config.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 480,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=20.0,
            )
            if not r.is_success:
                log.warning("downdetector summary anthropic HTTP %s", r.status_code)
                return None
            blocks = r.json().get("content") or []
            return next((b.get("text", "") for b in blocks if b.get("type") == "text"), "") or None

        if model.startswith("gpt") and config.OPENAI_API_KEY:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 480,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=20.0,
            )
            if not r.is_success:
                log.warning("downdetector summary openai HTTP %s", r.status_code)
                return None
            choice = (r.json().get("choices") or [{}])[0]
            return (choice.get("message") or {}).get("content") or None

        if model.startswith("gemini") and config.GEMINI_API_KEY:
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": config.GEMINI_API_KEY},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": 480},
                },
                timeout=20.0,
            )
            if not r.is_success:
                log.warning("downdetector summary gemini HTTP %s", r.status_code)
                return None
            parts = (
                (r.json().get("candidates") or [{}])[0]
                .get("content", {})
                .get("parts")
                or []
            )
            return parts[0].get("text") if parts else None

        log.debug("downdetector summary skipped — no matching model key for %s", model)
        return None
    except Exception as exc:
        log.warning("downdetector summary failed: %s", exc)
        return None


async def _analyze_comment_section(
    client: httpx.AsyncClient,
    comment_section: str,
) -> dict | None:
    """Return {problems_found, summary, comments} or None if the LLM call/parse fails."""
    section = comment_section.strip()
    if not section:
        return None
    raw = await _llm_summary_text(client, _analysis_prompt(section))
    if not raw:
        return None
    return _parse_summary_response(raw)


async def _wait_for_content(page: Any, timeout_ms: int) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        body = (await page.evaluate("() => document.body.innerText")).lower()
        if "user reports" in body and "performing security verification" not in body:
            return True
        await asyncio.sleep(0.5)
    return False


async def _create_browserbase_session(client: httpx.AsyncClient) -> dict | None:
    try:
        r = await client.post(
            config.BROWSERBASE_SESSIONS_URL,
            headers={
                "X-BB-API-Key": config.BROWSERBASE_API_KEY,
                "Content-Type": "application/json",
            },
            json={"proxies": True},
            timeout=30.0,
        )
        if not r.is_success:
            log.warning("browserbase session create HTTP %s", r.status_code)
            return None
        data = r.json()
        if not data.get("connectUrl"):
            log.warning("browserbase session missing connectUrl")
            return None
        return data
    except Exception as exc:
        log.warning("browserbase session create failed: %s", exc)
        return None


async def _release_browserbase_session(client: httpx.AsyncClient, session_id: str) -> None:
    if not session_id:
        return
    try:
        url = f"{config.BROWSERBASE_SESSIONS_URL.rstrip('/')}/{session_id}"
        r = await client.request(
            "DELETE",
            url,
            headers={"X-BB-API-Key": config.BROWSERBASE_API_KEY},
            timeout=15.0,
        )
        if r.status_code >= 400:
            log.warning("browserbase session release HTTP %s", r.status_code)
    except Exception as exc:
        log.warning("browserbase session release failed: %s", exc)


def _format_display_comments(comments: list[dict]) -> list[dict]:
    """Normalize LLM-parsed comments for the API payload."""
    display: list[dict] = []
    for c in comments[:3]:
        text = redact(c.get("text", ""))[:_COMMENT_TRUNC]
        if not text:
            continue
        display.append({"text": text, "age": c.get("age", "")})
    return display


def _vlog(verbose: bool, msg: str, *args: object) -> None:
    if verbose:
        log.info("[smoke] " + msg, *args)


def _browserbase_session_urls(session: dict) -> dict[str, str]:
    """Best-effort live-view / replay links from a Browserbase session payload."""
    session_id = session.get("id") or ""
    urls: dict[str, str] = {}
    if session_id:
        urls["dashboard"] = f"https://www.browserbase.com/sessions/{session_id}"
    for key in ("debuggerUrl", "debuggerFullscreenUrl", "replayUrl", "liveViewUrl"):
        val = session.get(key)
        if val:
            urls[key] = str(val)
    return urls


async def _fetch_provider_signal(
    http_client: httpx.AsyncClient,
    provider: str,
    *,
    verbose: bool = False,
) -> tuple[dict | None, dict | None]:
    """Core Downdetector scrape. Returns (signal, session_payload) for smoke tests."""
    slug = slug_for(provider)
    if not slug:
        _vlog(verbose, "no Downdetector slug for provider %r", provider)
        return None, None

    _vlog(verbose, "creating Browserbase session for %s (slug=%s)", provider, slug)
    session = await _create_browserbase_session(http_client)
    if not session:
        _vlog(verbose, "session create failed")
        return None, None

    session_id = session.get("id", "")
    _vlog(verbose, "session created: id=%s urls=%s", session_id, _browserbase_session_urls(session))

    connect_url = session["connectUrl"]
    page_url = f"https://downdetector.com/status/{slug}/"
    comments_url = f"{page_url}#comments"

    browser = None
    page = None
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            _vlog(verbose, "connecting Playwright over CDP")
            browser = await pw.chromium.connect_over_cdp(connect_url)
            _vlog(verbose, "connected to remote browser")
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()

            _vlog(verbose, "navigating to %s", page_url)
            await page.goto(page_url, wait_until="domcontentloaded", timeout=config.DOWNDETECTOR_WAIT_TIMEOUT_MS)

            _vlog(verbose, "waiting for Downdetector content (Cloudflare / JS)")
            if not await _wait_for_content(page, config.DOWNDETECTOR_WAIT_TIMEOUT_MS):
                _vlog(verbose, "content wait timed out after %sms", config.DOWNDETECTOR_WAIT_TIMEOUT_MS)
                log.info("downdetector %s: content wait timed out", provider)
                return None, session

            _vlog(verbose, "page ready — extracting headline and comment section")
            body_text = await page.evaluate("() => document.body.innerText")
            headline = _extract_headline(body_text)
            headline_problem = headline_indicates_problem(headline)

            comment_section = await page.evaluate(_EXTRACT_COMMENT_SECTION_JS)
            comment_section = (comment_section or "").strip()
            recent_count = count_recent_timestamps(
                comment_section,
                recent_hours=config.DOWNDETECTOR_RECENT_HOURS,
            )
            analysis: dict | None = None
            problems_found = False
            display_comments: list[dict] = []
            if comment_section:
                _vlog(
                    verbose,
                    "requesting LLM analysis for comment section (%s chars, ~%s recent)",
                    len(comment_section),
                    recent_count,
                )
                analysis = await _analyze_comment_section(http_client, comment_section)
                if analysis:
                    problems_found = analysis["problems_found"]
                    display_comments = _format_display_comments(analysis.get("comments") or [])
                _vlog(
                    verbose,
                    "analysis %s problems_found=%s display_comments=%s",
                    "ok" if analysis else "skipped/failed",
                    problems_found,
                    len(display_comments),
                )
            else:
                _vlog(verbose, "empty comment section — skipping analysis")

            dd_spike = compute_spike(
                headline_problem=headline_problem,
                recent_count=recent_count,
                problems_found=problems_found,
            )
            _vlog(
                verbose,
                "extracted headline_problem=%s recent_count=%s section_chars=%s "
                "problems_found=%s spike=%s",
                headline_problem,
                recent_count,
                len(comment_section),
                problems_found,
                dd_spike,
            )

            signal = {
                "source": "Downdetector",
                "count": recent_count,
                "spike": dd_spike,
                "headline": redact(headline),
                "problems_found": problems_found,
                "summary": analysis.get("summary") if analysis else None,
                "comments": display_comments,
                "url": comments_url,
            }
            _vlog(verbose, "fetch complete")
            return signal, session
    except Exception as exc:
        log.warning("downdetector fetch %s failed: %s", provider, exc)
        _vlog(verbose, "fetch failed: %s", exc)
        return None, session
    finally:
        if page is not None:
            with contextlib.suppress(Exception):
                await page.close()
        if browser is not None:
            with contextlib.suppress(Exception):
                await browser.close()
        _vlog(verbose, "releasing Browserbase session %s", session_id)
        await _release_browserbase_session(http_client, session_id)


async def fetch_provider_signal(
    http_client: httpx.AsyncClient,
    provider: str,
) -> dict | None:
    """Scrape Downdetector for one provider. None = no contribution this cycle."""
    if not enabled():
        return None
    signal, _ = await _fetch_provider_signal(http_client, provider, verbose=False)
    return signal


def _smoke_prereqs_ok() -> str | None:
    """Return an error message if smoke-test prerequisites are missing."""
    if not config.DOWNDETECTOR_ENABLED:
        return "DOWNDETECTOR_ENABLED is not set — enable it in .env for this smoke test."
    if not config.BROWSERBASE_API_KEY:
        return "BROWSERBASE_API_KEY is not set — add it to .env for this smoke test."
    return None


def _print_smoke_result(provider: str, session: dict | None, signal: dict | None) -> None:
    print(f"\n=== Downdetector smoke test: {provider} ===\n")
    if session:
        print(f"Browserbase session id: {session.get('id', '(unknown)')}")
        for label, url in _browserbase_session_urls(session).items():
            print(f"  {label}: {url}")
    else:
        print("Browserbase session: (not created)")

    if signal is None:
        print("\nResult: no data extracted (timeout, parse failure, or error).")
        return

    print(f"\nDowndetector URL: {signal.get('url')}")
    print(f"Headline: {signal.get('headline') or '(none)'}")
    print(f"Headline indicates problem: {headline_indicates_problem(signal.get('headline') or '')}")
    print(f"Recent comment count (<{config.DOWNDETECTOR_RECENT_HOURS}h): {signal.get('count')}")
    print(f"Spike: {signal.get('spike')}")
    print(f"AI problems_found: {signal.get('problems_found')}")

    summary = signal.get("summary")
    print(f"\nAI summary (of Downdetector user comments): {summary or '(none)'}")

    comments = signal.get("comments") or []
    print(f"\nSample comments (up to {len(comments)}):")
    if not comments:
        print("  (none)")
    for i, c in enumerate(comments, 1):
        print(f"  {i}. [{c.get('age', '?')}] {c.get('text', '')}")


async def _run_smoke_test(provider: str) -> int:
    import sys

    err = _smoke_prereqs_ok()
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    if provider not in config.DOWNDETECTOR_SLUGS:
        known = ", ".join(sorted(config.DOWNDETECTOR_SLUGS))
        print(
            f"ERROR: unknown provider {provider!r}. Choose one of: {known}",
            file=sys.stderr,
        )
        return 1

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    async with httpx.AsyncClient(timeout=60.0) as client:
        signal, session = await _fetch_provider_signal(client, provider, verbose=True)

    _print_smoke_result(provider, session, signal)
    return 0 if signal is not None else 2


def _smoke_main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="One-shot live smoke test for Downdetector via Browserbase (debug only).",
    )
    parser.add_argument(
        "--provider",
        required=True,
        choices=sorted(config.DOWNDETECTOR_SLUGS.keys()),
        help="Provider to scrape (e.g. GPT)",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_run_smoke_test(args.provider))


if __name__ == "__main__":
    raise SystemExit(_smoke_main())

