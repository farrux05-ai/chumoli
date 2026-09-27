"""Facebook / Meta Ads connector — manifest + helpers (tarmoq yo'q)."""

from __future__ import annotations

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.connectors.facebook_ads.connector import (
    RESOURCE_PATHS,
    FacebookAdsConnector,
    normalize_account_id,
    parse_resources,
)


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
