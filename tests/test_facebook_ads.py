"""Facebook / Meta Ads connector — manifest + helpers (tarmoq yo'q)."""

from __future__ import annotations

import httpx
import pytest

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.connectors.facebook_ads.connector import (
    GRAPH_BASE,
    RESOURCE_PATHS,
    FacebookAdsConnector,
    _get_json,
    _paginate,
    normalize_account_id,
    parse_resources,
)
from chumoli.core.retry_policy import is_transient_http


def test_facebook_ads_registered() -> None:
    register_builtin_connectors()
    m = registry.get_manifest("facebook_ads")
    assert m.label == "Meta Ads (Facebook)"
    assert m.category.value == "universal"
    assert m.maturity.value == "beta" or str(m.maturity) == "beta"
    assert m.secret_keys() == ["access_token"]
    keys = {f.key for f in m.fields}
    assert {"account_id", "access_token", "resources", "api_version"} <= keys


def test_normalize_account_id() -> None:
    assert normalize_account_id("1234567890") == "act_1234567890"
    assert normalize_account_id("act_1234567890") == "act_1234567890"
    assert normalize_account_id("ACT_99") == "ACT_99"
    try:
        normalize_account_id("")
        raise AssertionError("should fail")
    except ValueError:
        pass


def test_parse_resources() -> None:
    assert parse_resources("all") == list(RESOURCE_PATHS)
    assert parse_resources("campaigns") == ["campaigns"]
    assert parse_resources("adsets") == ["adsets"]
    try:
        parse_resources("insights")
        raise AssertionError("should fail")
    except ValueError:
        pass


def test_build_dlt_source_shape() -> None:
    conn = FacebookAdsConnector()
    src = conn.build_dlt_source(
        params={"account_id": "act_1", "resources": "campaigns", "api_version": "v19.0"},
        secrets={"access_token": "tok"},
    )
    # dlt source returns list of resources or a source object
    assert src is not None


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url=GRAPH_BASE)


def test_429_raises_retryable_error() -> None:
    """Meta rate-limit (429) JSON xatosi retry qilinadigan xato bo'lishi kerak.

    Ilgari bu yerda ValueError ko'tarilib, `uz_api_retry` uni transient deb
    hisoblamay, 429 hech qachon qayta urinilmasdi.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, json={"error": {"code": 17, "message": "User request limit reached"}}
        )

    with pytest.raises(httpx.HTTPStatusError) as err:
        _get_json(_mock_client(handler), "act_1/campaigns", {})
    assert is_transient_http(err.value)
    assert "17" in str(err.value)


def test_html_5xx_is_retryable() -> None:
    """JSON bo'lmagan 5xx javob ham retry qilinishi kerak."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="<html>Bad Gateway</html>")

    with pytest.raises(httpx.HTTPStatusError) as err:
        _get_json(_mock_client(handler), "act_1/campaigns", {})
    assert is_transient_http(err.value)


def test_400_is_not_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": {"code": 100, "message": "Invalid parameter"}}
        )

    with pytest.raises(ValueError) as err:
        _get_json(_mock_client(handler), "act_1/campaigns", {})
    assert not is_transient_http(err.value)
    assert "Invalid parameter" in str(err.value)


def test_paginate_stops_on_repeated_cursor() -> None:
    """Kursor takrorlansa — cheksiz loop bo'lmasligi kerak."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            200,
            json={
                "data": [{"id": "1"}],
                "paging": {"cursors": {"after": "SAME"}, "next": "https://graph/next"},
            },
        )

    rows = list(_paginate(_mock_client(handler), "act_1/campaigns", "id", "tok"))
    assert calls["n"] == 2
    assert [r["id"] for r in rows] == ["1", "1"]
