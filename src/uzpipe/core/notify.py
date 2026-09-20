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


def send_telegram(
    chat_id: str, bot_token: str, text: str, *, parse_mode: str | None = "HTML"
) -> None:
    """POST sendMessage. Raises on HTTP errors (caller should catch)."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()


def _esc(s: str) -> str:
    """Minimal HTML escape for Telegram parse_mode=HTML."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _fmt_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    if seconds < 60:
        return f"{seconds:.1f} s"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m} min {s:.0f} s"


def _fmt_int(n: int) -> str:
    return f"{n:,}".replace(",", " ")


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
    """Human-readable Telegram body (HTML)."""
    if success and quality_passed:
        icon, holat = "✅", "Muvaffaqiyatli"
    elif success and not quality_passed:
        icon, holat = "⚠️", "Quality tekshiruvi o'tmadi"
    else:
        icon, holat = "❌", "Xato"

    name = _esc(pipeline_name)
    lines: list[str] = [
        f"{icon} <b>Chumoli</b> · <code>{name}</code>",
        "",
        f"<b>Holat:</b> {holat}",
    ]

    total = sum(row_counts.values()) if row_counts else 0
    if row_counts:
        lines.append(f"<b>Jami:</b> {_fmt_int(total)} qator")
        items = sorted(row_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        for table, count in items:
            lines.append(f"  · <code>{_esc(table)}</code> — {_fmt_int(count)}")
    elif success:
        lines.append("<b>Jami:</b> 0 qator")

    if duration_seconds is not None:
        lines.append(f"<b>Vaqt:</b> {_fmt_duration(float(duration_seconds))}")

    if error:
        lines.append("")
        lines.append(f"<b>Xato:</b> {_esc(error[:400])}")

    if quality_details:
        fails = [d for d in quality_details if not d.get("passed", True)]
        if fails:
            detail = fails[0].get("detail") or fails[0].get("check") or "fail"
            lines.append(f"<b>Quality:</b> {_esc(str(detail)[:200])}")

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
