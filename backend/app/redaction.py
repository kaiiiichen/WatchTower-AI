"""Secret redaction for logs and Sentry payloads.

Gemini authenticates via a `?key=...` query param (unlike Anthropic/OpenAI,
which use headers). That means the API key can leak anywhere a URL is rendered:
httpx's INFO request logs, our own exception logging, and Sentry HTTP spans.
`redact()` scrubs `key=`/`api_key=` query values out of any string; `scrub()`
walks a nested Sentry event/transaction and redacts every string it contains."""
from __future__ import annotations

import re

REDACTED = "REDACTED"

# Match a `key=` / `api_key=` query param and keep the name so we only drop the
# value (`key=REDACTED`). The lookbehind anchors on a param-name boundary — start
# of string, `?`, `&`, or whitespace/quote — NOT just `?`/`&`: Sentry's httpx
# integration stores the query string standalone (`key=...&pageSize=1`, no leading
# `?`), and the negative lookbehind avoids clobbering words like `monkey=`. The
# value runs until the next separator so a trailing `&pageSize=1000` is preserved.
_KEY_QUERY = re.compile(r"(?i)(?<![\w-])(api[_-]?key|key)=[^&\s\"'#]+")


def redact(text: str) -> str:
    """Replace `key=<secret>` query values with `key=REDACTED` in any string."""
    if not isinstance(text, str):
        return text
    return _KEY_QUERY.sub(lambda m: m.group(1) + "=" + REDACTED, text)


def scrub(obj):
    """Recursively redact every string inside a dict/list (e.g. a Sentry event).

    Walking the whole structure is deliberate: Sentry's httpx integration can put
    the request URL in a span's `description`, `data["url"]`, `data["http.url"]`,
    a breadcrumb, or `request.url` — scrubbing all strings means a new SDK version
    can't reintroduce the leak through a field we forgot to special-case."""
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(scrub(v) for v in obj)
    return obj
