"""
uzpipe.core.notify
====================

Optional Telegram notifications after pipeline runs.
Failures here must never fail the pipeline itself.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger("uzpipe.notify")

TELEGRAM_BOT_TOKEN_KEY = "telegram_bot_token"


def send_telegram(chat_id: str, bot_token: str, text: str) -> None:
    """POST sendMessage. Raises on HTTP errors (caller should catch)."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(url, json={"chat_id": chat_id, "text": text})
        resp.raise_for_status()


def format_run_message(
    *,
    pipeline_name: str,
    success: bool,
    quality_passed: bool,
    row_counts: dict[str, int],
    quality_details: list[dict[str, Any]] | None = None,
    error: str | None = None,
    duration_seconds: float | None = None,
) -> str:
    status = "OK" if success and quality_passed else ("QUALITY" if success else "FAIL")
    lines = [
        f"UzPipe: {pipeline_name}",
        f"Holat: {status}",
    ]
    if row_counts:
        rows = ", ".join(f"{k}={v}" for k, v in row_counts.items())
        lines.append(f"Qatorlar: {rows}")
    if duration_seconds is not None:
        lines.append(f"Vaqt: {duration_seconds:.1f}s")
    if error:
        lines.append(f"Xato: {error[:300]}")
    if quality_details:
        fails = [d for d in quality_details if not d.get("passed", True)]
        if fails:
            lines.append(f"Quality: {fails[0].get('detail', 'fail')}")
    return "\n".join(lines)


def maybe_notify_run(
    *,
    store: Any,
    notify_cfg: Any,
    pipeline_name: str,
    success: bool,
    quality_passed: bool,
    row_counts: dict[str, int],
    quality_details: list[dict[str, Any]] | None = None,
    error: str | None = None,
    duration_seconds: float | None = None,
) -> None:
    """Best-effort notify based on NotifyConfig + global bot token."""
    try:
        want = (success and quality_passed and getattr(notify_cfg, "on_success", False)) or (
            (not success or not quality_passed) and getattr(notify_cfg, "on_failure", True)
        )
        if not want:
            return
        chat_id = getattr(notify_cfg, "telegram_chat_id", None)
        if not chat_id:
            return
        token = None
        if store is not None:
            getter = getattr(store, "get_secret_setting", None)
            if callable(getter):
                token = getter(TELEGRAM_BOT_TOKEN_KEY)
            if not token:
                token = store.get_setting(TELEGRAM_BOT_TOKEN_KEY)
        if not token:
            log.debug("telegram_bot_token not set; skip notify")
            return
        text = format_run_message(
            pipeline_name=pipeline_name,
            success=success,
            quality_passed=quality_passed,
            row_counts=row_counts,
            quality_details=quality_details,
            error=error,
            duration_seconds=duration_seconds,
        )
        send_telegram(str(chat_id), token, text)
    except Exception:
        log.exception("telegram_notify_failed pipeline=%s", pipeline_name)
