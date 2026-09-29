"""MoySklad connector — manifest + helpers (tarmoq yo'q)."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.connectors.moysklad.connector import (
    _client,
    RESOURCE_PATHS,
    TZ_MOYSKLAD,
    _attach_href,
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


def test_updated_filter_uses_moskva_time() -> None:
    """MoySklad sanalarni MSK (UTC+3) da kutadi — Tashkent emas.

    Toshkent va Moskva sanasi faqat kunning ~2 soatida farq qiladi, shuning
    uchun doimiyni ham bevosita tekshiramiz — aks holda regressiya
    (Asia/Tashkent) aksariyat paytda ushlanmay qolardi.
    """
    assert TZ_MOYSKLAD.key == "Europe/Moscow"
    days = 5
    expected = datetime.now(ZoneInfo("Europe/Moscow")).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=days)
    assert updated_filter(days) == f"updated>={expected.strftime('%Y-%m-%d %H:%M:%S')}"


def test_stock_row_key_strips_query_string() -> None:
    """report/stock/all satri: havola `meta.href` da (query parametrlari bilan)."""
    href = "https://api.moysklad.ru/api/remap/1.2/entity/product/77e0?expand=supplier"
    row = _attach_href({"meta": {"href": href}, "stock": 3.0})
    assert row["_href"] == "https://api.moysklad.ru/api/remap/1.2/entity/product/77e0"


def test_row_key_falls_back_to_nested_product() -> None:
    assert _attach_href({"product": {"id": "abc"}})["_href"] == "abc"

    nested = {"product": {"meta": {"href": "https://ms/entity/product/x?expand=y"}}}
    assert _attach_href(nested)["_href"] == "https://ms/entity/product/x"

    assert "_href" not in _attach_href({"stock": 1.0})


def test_client_accept_charset() -> None:
    """MoySklad requires Accept application/json;charset=utf-8 (error 1062)."""
    with _client("https://api.moysklad.ru/api/remap/1.2", "tok") as c:
        assert c.headers["Accept"] == "application/json;charset=utf-8"
        assert c.headers["Accept-Encoding"] == "gzip"
