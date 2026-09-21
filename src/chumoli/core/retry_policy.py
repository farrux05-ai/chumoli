"""
chumoli.core.retry_policy
==========================

Barcha HTTP connector'lar uchun yagona retry policy.

NIMA UCHUN ALOHIDA FAYL:
  click_uz, payme_uz, uzum_market, didox — to'rtalasi
  o'z retry loopini yozgan. Shu fayl barchasini almashtiradi.
  Connector muallifi faqat so'rov mantig'ini yozadi —
  qolganini tenacity + ushbu policy hal qiladi.

NIMA UCHUN exponential + jitter:
  Payme/Click serveriga 10 ta pipeline bir vaqtda urinsa
  va hammasi bir xil delay dan keyin qayta urinsa → thundering herd.
  wait_random_exponential(min=1, max=30) har birini tarqatadi.

dlt pipeline.run() ni o'ramaymiz — dlt o'zi extract/load retry qiladi.
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

log = structlog.get_logger("chumoli.retry")


def is_transient_http(exc: BaseException) -> bool:
    """429 va 5xx → retry. 4xx (401, 404) → darhol fail."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError))


def _log_retry(retry_state: RetryCallState) -> None:
    """tenacity before_sleep callback — har urinishni log qiladi."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    wait = None
    if retry_state.next_action is not None:
        wait = round(float(retry_state.next_action.sleep), 1)
    log.warning(
        "http_retry",
        attempt=retry_state.attempt_number,
        wait_seconds=wait,
        error=str(exc) if exc else None,
        # pipeline/run_id structlog contextvars dan avtomatik keladi
    )


# UZ payment / EDI API'lar uchun standart policy:
# 3 urinish, 1–30 soniya orasida exponential + jitter
uz_api_retry = retry(
    retry=retry_if_exception(is_transient_http),
    wait=wait_random_exponential(min=1, max=30),
    stop=stop_after_attempt(3),
    before_sleep=_log_retry,
    reraise=True,
)


def call_with_uz_retry(fn: Any, *args: Any, **kwargs: Any) -> Any:
    """Decorator o'rniga funksiya sifatida chaqirish (nested helper uchun)."""

    @uz_api_retry
    def _inner() -> Any:
        return fn(*args, **kwargs)

    return _inner()
