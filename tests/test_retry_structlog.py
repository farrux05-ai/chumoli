"""tenacity uz_api_retry + structlog setup smoke tests."""

from __future__ import annotations

import httpx
import pytest
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_none

from chumoli.core.logging_setup import configure_logging, get_logger
from chumoli.core.retry_policy import is_transient_http


def test_is_transient_http() -> None:
    req = httpx.Request("GET", "https://example.com")
    assert is_transient_http(httpx.ConnectError("x", request=req))
    assert is_transient_http(
        httpx.HTTPStatusError(
            "429", request=req, response=httpx.Response(429, request=req)
        )
    )
    assert is_transient_http(
        httpx.HTTPStatusError(
            "503", request=req, response=httpx.Response(503, request=req)
        )
    )
    assert not is_transient_http(
        httpx.HTTPStatusError(
            "400", request=req, response=httpx.Response(400, request=req)
        )
    )
    assert not is_transient_http(ValueError("app"))


def _fast_retry():
    return retry(
        retry=retry_if_exception(is_transient_http),
        wait=wait_none(),
        stop=stop_after_attempt(3),
        reraise=True,
    )


def test_uz_api_retry_on_503() -> None:
    state = {"n": 0}
    req = httpx.Request("GET", "https://example.com")

    @_fast_retry()
    def flaky() -> str:
        state["n"] += 1
        if state["n"] < 2:
            raise httpx.HTTPStatusError(
                "503",
                request=req,
                response=httpx.Response(503, request=req),
            )
        return "ok"

    assert flaky() == "ok"
    assert state["n"] == 2


def test_no_retry_on_400() -> None:
    req = httpx.Request("GET", "https://example.com")

    @_fast_retry()
    def bad() -> None:
        raise httpx.HTTPStatusError(
            "400", request=req, response=httpx.Response(400, request=req)
        )

    with pytest.raises(httpx.HTTPStatusError):
        bad()


def test_configure_logging_console() -> None:
    configure_logging()
    log = get_logger("chumoli.test")
    log.info("test_event", pipeline="demo")
