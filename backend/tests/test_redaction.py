"""Tests for secret redaction — the Gemini `?key=...` leak guard.

Gemini authenticates via a query param, so its key can leak into httpx request
logs, our own exception logs, and Sentry HTTP spans. These lock in that every
exit path strips it. Search target from the incident: the live key starts "AQ".
"""
import logging

from app import monitoring
from app.redaction import REDACTED, redact, scrub

# A realistic Gemini key prefix (the value that kept showing up in logs).
_KEY = "AQ.Ab8RfakeSecret_value-123"


def test_redact_strips_key_query_param():
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={_KEY}&pageSize=1000"
    out = redact(url)
    assert "AQ" not in out
    assert "key=REDACTED" in out
    assert "pageSize=1000" in out  # trailing param preserved


def test_redact_handles_api_key_and_case_and_path_suffix():
    assert redact(f"x?api_key={_KEY}") == "x?api_key=REDACTED"
    assert redact(f"x?KEY={_KEY}") == "x?KEY=REDACTED"
    # key as a later param, value ending at a quote
    assert "AQ" not in redact(f'GET "https://h/m:generateContent?key={_KEY}"')


def test_redact_standalone_query_string():
    # Sentry's httpx integration stores the query WITHOUT a leading `?`
    # (span data `http.query`). This must still be redacted.
    assert redact(f"key={_KEY}&pageSize=1") == "key=REDACTED&pageSize=1"


def test_redact_does_not_clobber_lookalike_words():
    assert redact("monkey=banana") == "monkey=banana"
    assert redact("turkey=3") == "turkey=3"


def test_redact_leaves_clean_strings_untouched():
    assert redact("no secrets here") == "no secrets here"
    assert redact("https://api.anthropic.com/v1/messages") == (
        "https://api.anthropic.com/v1/messages"
    )


def test_scrub_walks_nested_sentry_event():
    event = {
        "spans": [
            {
                "description": f"GET https://g?key={_KEY}",
                "data": {"url": f"https://g?key={_KEY}", "http.method": "GET"},
            }
        ],
        "breadcrumbs": {"values": [{"data": {"url": f"https://g?key={_KEY}"}}]},
        "request": {"url": f"https://g?key={_KEY}"},
    }
    scrubbed = scrub(event)
    assert REDACTED in scrubbed["spans"][0]["description"]
    assert scrubbed["spans"][0]["data"]["http.method"] == "GET"  # untouched
    # Exhaustive: no key value survives anywhere in the structure.
    assert "AQ" not in repr(scrubbed)


def test_sentry_hooks_redact():
    leaky = {"spans": [{"description": f"GET https://g?key={_KEY}"}]}
    assert "AQ" not in repr(monitoring._before_send(dict(leaky), None))
    assert "AQ" not in repr(monitoring._before_send_transaction(dict(leaky), None))


def test_httpx_logger_is_silenced_after_app_import():
    import app.main  # noqa: F401  -- import configures logging as a side effect

    assert logging.getLogger("httpx").level >= logging.WARNING
    assert logging.getLogger("httpcore").level >= logging.WARNING
