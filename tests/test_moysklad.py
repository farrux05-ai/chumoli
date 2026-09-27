"""MoySklad connector — manifest + helpers (tarmoq yo'q)."""

from __future__ import annotations

import base64

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.connectors.moysklad.connector import (
    RESOURCE_PATHS,
    auth_header,
    parse_resources,
    updated_filter,
)


def test_moysklad_registered() -> None:
    register_builtin_connectors()
    m = registry.get_manifest("moysklad")
    assert m.label == "MoySklad"
    assert m.category.value == "uz_erp"
    assert m.secret_keys() == ["token"]
    keys = {f.key for f in m.fields}
    assert {"token", "resources", "from_days_ago"} <= keys


def test_auth_header_bearer_and_basic() -> None:
    assert auth_header("abc.def") == "Bearer abc.def"
    assert auth_header("Bearer tok") == "Bearer tok"
    basic = auth_header("user@shop:secret")
    expected = base64.b64encode(b"user@shop:secret").decode()
    assert basic == f"Basic {expected}"


def test_parse_resources() -> None:
    assert parse_resources("all") == list(RESOURCE_PATHS)
    assert parse_resources("product") == ["product"]
    try:
        parse_resources("unknown")
        raise AssertionError("should fail")
    except ValueError:
        pass


def test_updated_filter_shape() -> None:
    filt = updated_filter(7)
    assert filt.startswith("updated>=")
    assert len(filt) > len("updated>=2020-01-01 00:00:00") - 5


def test_manifest_validate() -> None:
    register_builtin_connectors()
    m = registry.get_manifest("moysklad")
    errors = m.validate_values(
        {"token": "t", "resources": "customerorder", "from_days_ago": "7"}
    )
    assert errors == []


def test_build_dlt_source_no_network() -> None:
    register_builtin_connectors()
    src = registry.get("moysklad").build_dlt_source(
        {"resources": "product", "from_days_ago": "1"},
        {"token": "tok"},
    )
    assert src is not None
