"""REST API connector config guards (handoff: empty header, path query, max_pages)."""

from __future__ import annotations

import pytest

from uzpipe.connectors.rest_api.connector import (
    _build_auth_config,
    _clean_endpoint,
    _parse_max_pages,
    build_rest_api_config,
)


def test_clean_endpoint_strips_query() -> None:
    path, q = _clean_endpoint("/movie/popular?page=1&language=en")
    assert path == "/movie/popular"
    assert q["page"] == "1"
    assert q["language"] == "en"


def test_clean_endpoint_plain() -> None:
    path, q = _clean_endpoint("users")
    assert path == "/users"
    assert q == {}


def test_parse_max_pages_default() -> None:
    assert _parse_max_pages(None) == 1
    assert _parse_max_pages("") == 1
    assert _parse_max_pages("0") == 1
    assert _parse_max_pages(5) == 5


def test_api_key_empty_name_raises() -> None:
    with pytest.raises(ValueError, match="Header/parametr nomi"):
        _build_auth_config("api_key", "SECRET", "", "header")
    with pytest.raises(ValueError, match="Header/parametr nomi"):
        _build_auth_config("api_key", "SECRET", "   ", "header")


def test_api_key_query_location() -> None:
    cfg = _build_auth_config("api_key", "DEMO_KEY", "api_key", "query")
    assert cfg == {
        "type": "api_key",
        "name": "api_key",
        "api_key": "DEMO_KEY",
        "location": "query",
    }


def test_bearer_ignores_key_name() -> None:
    cfg = _build_auth_config("bearer", "tok", "", "header")
    assert cfg == {"type": "bearer", "token": "tok"}


def test_build_config_single_page_default() -> None:
    cfg = build_rest_api_config(
        {
            "base_url": "https://api.example.com",
            "endpoint": "/data?page=1",
            "auth_type": "none",
        },
        {},
    )
    endpoint = cfg["resources"][0]["endpoint"]
    assert endpoint["path"] == "/data"
    assert endpoint["paginator"] == "single_page"
    # page stripped from params to avoid collision
    assert "page" not in (endpoint.get("params") or {})


def test_build_config_max_pages_paginator() -> None:
    cfg = build_rest_api_config(
        {
            "base_url": "https://api.example.com",
            "endpoint": "/items",
            "auth_type": "none",
            "max_pages": 3,
        },
        {},
    )
    paginator = cfg["resources"][0]["endpoint"]["paginator"]
    assert paginator["type"] == "page_number"
    assert paginator["maximum_page"] == 3


def test_build_config_api_key_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="Header/parametr nomi"):
        build_rest_api_config(
            {
                "base_url": "https://api.example.com",
                "endpoint": "/v1",
                "auth_type": "api_key",
                "auth_key_name": "",
            },
            {"secret_value": "TOKEN"},
        )
