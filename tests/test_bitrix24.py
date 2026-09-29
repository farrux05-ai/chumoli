"""Bitrix24 connector — manifest + helpers (tarmoq yo'q)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.connectors.bitrix24.connector import (
    BITRIX_PAGE_SIZE,
    _paginate,
    extract_items,
    is_webhook_url,
    method_url,
    normalize_webhook_url,
    parse_resources,
    since_date,
)


def test_bitrix24_registered() -> None:
    register_builtin_connectors()
    m = registry.get_manifest("bitrix24")
    assert m.label == "Bitrix24"
    assert m.category.value == "uz_erp"
    assert "webhook_url" in m.secret_keys()
    keys = {f.key for f in m.fields}
    assert {"webhook_url", "resources", "from_days_ago"} <= keys


def test_normalize_webhook_strips_method() -> None:
    url = "https://shop.bitrix24.uz/rest/1/abc123/crm.deal.list.json"
    base = normalize_webhook_url(url)
    assert base == "https://shop.bitrix24.uz/rest/1/abc123/"
    assert is_webhook_url(base)


def test_normalize_portal_and_trailing_slash() -> None:
    base = normalize_webhook_url("https://shop.bitrix24.ru")
    assert base == "https://shop.bitrix24.ru/"
    assert not is_webhook_url(base)


def test_normalize_rejects_junk() -> None:
    with pytest.raises(ValueError):
        normalize_webhook_url("not-a-url")


def test_method_url() -> None:
    assert (
        method_url("https://x.bitrix24.uz/rest/1/tok/", "crm.deal.list")
        == "https://x.bitrix24.uz/rest/1/tok/crm.deal.list.json"
    )


def test_extract_items_crm_and_tasks() -> None:
    crm = extract_items({"result": [{"ID": "1"}, {"ID": "2"}]}, None)
    assert [x["ID"] for x in crm] == ["1", "2"]
    tasks = extract_items({"result": {"tasks": [{"id": "9"}]}}, "tasks")
    assert tasks[0]["id"] == "9"


def test_parse_resources_and_since() -> None:
    assert parse_resources("deals") == ["deals"]
    assert "tasks" in parse_resources("all")
    s = since_date(3)
    assert len(s) == 10 and s[4] == "-"


def test_manifest_validate() -> None:
    register_builtin_connectors()
    m = registry.get_manifest("bitrix24")
    errors = m.validate_values(
        {
            "webhook_url": "https://a.bitrix24.uz/rest/1/tok/",
            "resources": "deals",
        }
    )
    assert errors == []


def test_build_dlt_source_no_network() -> None:
    register_builtin_connectors()
    src = registry.get("bitrix24").build_dlt_source(
        {"resources": "deals", "from_days_ago": "1"},
        {"webhook_url": "https://shop.bitrix24.uz/rest/1/xxxxx/"},
    )
    assert src is not None



def test_portal_without_oauth_raises() -> None:
    register_builtin_connectors()
    with pytest.raises(ValueError, match="OAuth"):
        registry.get("bitrix24").build_dlt_source(
            {"resources": "leads"},
            {"webhook_url": "https://shop.bitrix24.uz"},
        )


class _FakePostClient:
    """`_paginate` uchun minimal client o'rnini bosuvchi (tarmoqsiz)."""

    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self.pages = pages
        self.calls = 0

    def post(self, url: str, json: dict[str, Any]) -> httpx.Response:
        page = self.pages[min(self.calls, len(self.pages) - 1)]
        self.calls += 1
        request = httpx.Request("POST", url, json=json)
        return httpx.Response(200, json=page, request=request)


_URL = "https://shop.bitrix24.uz/rest/1/tok/crm.deal.list.json"


def test_paginate_follows_next() -> None:
    items = [{"ID": str(i)} for i in range(BITRIX_PAGE_SIZE)]
    client = _FakePostClient(
        [{"result": items, "next": BITRIX_PAGE_SIZE}, {"result": [{"ID": "last"}]}]
    )
    rows = list(_paginate(client, _URL, {}, None))
    assert len(rows) == BITRIX_PAGE_SIZE + 1
    assert client.calls == 2


def test_paginate_stops_when_next_does_not_advance() -> None:
    """`next: 0` da start yana 0 bo'lib, ilgari cheksiz loop bo'lardi."""
    items = [{"ID": str(i)} for i in range(BITRIX_PAGE_SIZE)]
    client = _FakePostClient([{"result": items, "next": 0}])
    rows = list(_paginate(client, _URL, {}, None))
    assert len(rows) == BITRIX_PAGE_SIZE
    assert client.calls == 1
