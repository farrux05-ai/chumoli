"""
uzpipe.security.api_key
========================

Shared-secret API key for /api/* routes (except /api/health).

Key resolution order:
1. UZPIPE_API_KEY environment variable
2. ~/.uzpipe/api.key (or $UZPIPE_HOME/api.key), mode 600
3. Auto-generate on first access, print once to stdout, persist
"""

from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path


def keys_match(provided: str, expected: str) -> bool:
    """Constant-time comparison for API keys (avoids timing side-channel).

    Plain `provided != expected` short-circuits on the first mismatching
    byte, which leaks how many leading characters were guessed correctly
    over repeated attempts. `hmac.compare_digest` runs in time
    independent of where the strings first differ.
    """
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def _default_key_path() -> Path:
    home = Path(os.environ.get("UZPIPE_HOME") or (Path.home() / ".uzpipe"))
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    return home / "api.key"


def load_or_create_api_key(key_path: Path | None = None) -> str:
    """Return the active API key, creating and printing it if needed."""
    env = os.environ.get("UZPIPE_API_KEY", "").strip()
    if env:
        return env

    path = key_path or _default_key_path()
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value

    value = secrets.token_urlsafe(32)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")
    path.chmod(0o600)
    print(
        f"[uzpipe] API key yaratildi va saqlandi: {path}\n"
        f"[uzpipe] UZPIPE_API_KEY={value}\n"
        f"[uzpipe] Dashboard so'rovlari uchun X-API-Key header kerak.",
        flush=True,
    )
    return value
