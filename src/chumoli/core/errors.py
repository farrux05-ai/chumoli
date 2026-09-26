"""chumoli.core.errors
=====================

Error sanitization for run history, the dashboard and notifications.

Errors raised by dlt, SQLAlchemy and HTTP clients routinely embed
connection strings (with passwords), API tokens and Authorization
headers. Anything we persist to run history or render in the UI must be
redacted first — a failed run must never leak a credential.
"""

from __future__ import annotations

import re
from typing import Any

# Keep stored/displayed errors bounded so a pathological traceback cannot
# bloat the control DB or the dashboard payload.
DEFAULT_MAX_LEN = 2000

# scheme://user:password@host  →  scheme://user:***@host
# Greedy password group so a password containing '@' is fully redacted.
_URL_CREDS = re.compile(r"(?i)([a-z][a-z0-9+.\-]*://[^/\s@]*:)([^/\s]*)(@)")
# Bearer / Basic <credential>
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._\-+/=]{8,}")
# key=value / key: value for common secret keys (auth_type is NOT matched)
_KV_SECRET = re.compile(
    r"(?i)\b(password|passwd|pwd|token|api[_-]?key|apikey|secret|client[_-]?secret|"
    r"authorization|x-auth|auth(?!_))\b(\s*[=:]\s*)([^\s,;]+)"
)


def sanitize_error(value: Any, *, max_len: int = DEFAULT_MAX_LEN) -> str:
    """Redact credentials and bound the length of an error message.

    Safe to call on any exception or string; never raises.
    """
    try:
        text = str(value or "").strip()
    except Exception:
        return ""
    if not text:
        return ""
    text = _URL_CREDS.sub(r"\1***\3", text)
    text = _BEARER.sub(lambda m: f"{m.group(1)} ***", text)
    text = _KV_SECRET.sub(r"\1\2***", text)
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text


def friendly_error(exc: BaseException, *, max_len: int = 600) -> str:
    """Short, secret-free, user-facing message for a failed run."""
    try:
        from chumoli.core.demo_data import friendly_db_error

        msg = friendly_db_error(exc)
    except Exception:
        msg = str(exc)
    return sanitize_error(msg, max_len=max_len)
