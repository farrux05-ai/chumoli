"""
chumoli.connectors.moysklad
=============================

MoySklad JSON API 1.2 (remap).

Rasmiy: https://dev.moysklad.ru/doc/api/remap/1.2/
GitHub: https://github.com/moysklad/api-remap-1.2-doc

Auth:
  Bearer token  — Authorization: Bearer <token>
  Basic         — token maydoniga login:parol (API token olish:
                  POST /api/remap/1.2/security/token)

Majburiy header: Accept-Encoding: gzip (boshqa encoding → 415)

Pagination: limit (max 1000) + offset. Ro'yxat javobi: {meta, rows}.

Resurslar (entity, stock — report):
  customerorder, demand, invoiceout, product, retaildemand, stock
"""

from __future__ import annotations

import base64
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import dlt
import httpx

from chumoli import __version__
from chumoli.core.manifest import (
    ConnectorCategory,
    ConnectorManifest,
    FieldSpec,
    FieldType,
    SelectOption,
)
from chumoli.core.retry_policy import uz_api_retry

MOYSKLAD_BASE_URL = "https://api.moysklad.ru/api/remap/1.2"
MOYSKLAD_PAGE_SIZE = 1000
TZ_TASHKENT = ZoneInfo("Asia/Tashkent")

# entity path relative to base; stock is a report endpoint
RESOURCE_PATHS: dict[str, str] = {
    "customerorder": "entity/customerorder",
    "demand": "entity/demand",
    "invoiceout": "entity/invoiceout",
    "product": "entity/product",
    "retaildemand": "entity/retaildemand",
    "stock": "report/stock/all",
}

RESOURCE_PRIMARY_KEY: dict[str, str] = {
    "stock": "_href",
}


MANIFEST = ConnectorManifest(
    key="moysklad",
    label="MoySklad",
    category=ConnectorCategory.UZ_ERP,
    description="MoySklad JSON API 1.2 — buyurtma, jo'natma, mahsulot, qoldiq",
    dlt_source_factory="chumoli.connectors.moysklad.connector.MoySkladConnector",
    fields=[
        FieldSpec(
            key="token",
            label="Token yoki login:parol",
            type=FieldType.PASSWORD,
            required=True,
            secret=True,
            help_text=(
                "Bearer token (tavsiya). Yoki Basic: login:parol. "
                "Token: POST /api/remap/1.2/security/token"
            ),
        ),
        FieldSpec(
            key="resources",
            label="Resurs",
            type=FieldType.SELECT,
            required=True,
            default="all",
            options=[
                SelectOption(value="all", label="Hammasi"),
                SelectOption(value="customerorder", label="Buyurtmalar (customerorder)"),
                SelectOption(value="demand", label="Jo'natmalar (demand)"),
                SelectOption(value="invoiceout", label="Hisob-faktura (invoiceout)"),
                SelectOption(value="product", label="Mahsulotlar (product)"),
                SelectOption(value="retaildemand", label="Chakana savdo (retaildemand)"),
                SelectOption(value="stock", label="Qoldiq (stock)"),
            ],
        ),
        FieldSpec(
            key="from_days_ago",
            label="Necha kun oldin (default 7)",
            type=FieldType.NUMBER,
            required=False,
            default="7",
            help_text="updated>= filtri. Qoldiq (stock) — joriy snapshot, sana qo'llanilmaydi.",
        ),
    ],
)


def auth_header(token: str) -> str:
    """Bearer yoki Basic. login:parol → Basic (MoySklad rasmiy ikkala usulni qo'llab-quvvatlaydi)."""
    raw = (token or "").strip()
    if not raw:
        raise ValueError("MoySklad token bo'sh")
    if raw.lower().startswith("basic "):
        return raw
    if raw.lower().startswith("bearer "):
        return "Bearer " + raw.split(None, 1)[1]
    if ":" in raw:
        encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
        return f"Basic {encoded}"
    return f"Bearer {raw}"


def parse_resources(raw: str | None) -> list[str]:
    value = (raw or "all").strip().lower()
    if value == "all":
        return list(RESOURCE_PATHS)
    if value not in RESOURCE_PATHS:
        raise ValueError(f"Noma'lum MoySklad resursi: {raw}")
    return [value]


def updated_filter(from_days_ago: int) -> str:
    """MoySklad filter: updated>=YYYY-MM-DD HH:MM:SS (Toshkent)."""
    days = max(0, int(from_days_ago))
    start = datetime.now(TZ_TASHKENT).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=days)
    return f"updated>={start.strftime('%Y-%m-%d %H:%M:%S')}"


def _attach_href(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("meta")
    if isinstance(meta, dict) and meta.get("href"):
        row["_href"] = meta["href"]
    return row


@uz_api_retry
def _get_json(
    client: httpx.Client,
    path: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    resp = client.get(path, params=params)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("error"):
        err = data[0]
        raise ValueError(
            f"MoySklad API [{err.get('code', '?')}]: {err.get('error') or err.get('error_message')}"
        )
    if not isinstance(data, dict):
        raise ValueError("MoySklad kutilmagan javob (object emas)")
    return data


def _paginate(
    client: httpx.Client,
    path: str,
    extra_params: dict[str, Any] | None,
) -> Iterator[dict[str, Any]]:
    offset = 0
    while True:
        params: dict[str, Any] = {
            "limit": MOYSKLAD_PAGE_SIZE,
            "offset": offset,
        }
        if extra_params:
            params.update(extra_params)
        data = _get_json(client, path, params)
        rows = data.get("rows")
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            if isinstance(row, dict):
                yield _attach_href(row)
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        size = meta.get("size")
        offset += len(rows)
        if size is not None and offset >= int(size):
            break
        if len(rows) < MOYSKLAD_PAGE_SIZE:
            break


def _client(base_url: str, token: str) -> httpx.Client:
    # Accept-Encoding FAQAT gzip — deflate/br 415 qaytaradi (rasmiy cheklov).
    return httpx.Client(
        base_url=base_url.rstrip("/") + "/",
        headers={
            "Authorization": auth_header(token),
            "Accept-Encoding": "gzip",
            "Accept": "application/json",
            "User-Agent": f"Chumoli/{__version__} (+https://github.com/farrux05-ai/chumoli)",
        },
        timeout=60.0,
    )


def _make_resource(
    name: str,
    path: str,
    token: str,
    base_url: str,
    extra_params: dict[str, Any] | None,
):
    pk = RESOURCE_PRIMARY_KEY.get(name, "id")

    @dlt.resource(name=name, write_disposition="merge", primary_key=pk)
    def _resource() -> Iterator[dict[str, Any]]:
        with _client(base_url, token) as client:
            yield from _paginate(client, path, extra_params)

    return _resource


@dlt.source(name="moysklad")
def moysklad_source(
    token: str,
    resources: list[str],
    from_days_ago: int,
    base_url: str = MOYSKLAD_BASE_URL,
) -> Any:
    filt = updated_filter(from_days_ago)
    out = []
    for name in resources:
        path = RESOURCE_PATHS[name]
        extra = None if name == "stock" else {"filter": filt}
        out.append(_make_resource(name, path, token, base_url, extra))
    return out


class MoySkladConnector:
    """MoySklad remap 1.2 — BaseUZConnector."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        token = secrets.get("token") or ""
        resources = parse_resources(str(params.get("resources") or "all"))
        days = int(params.get("from_days_ago") or 7)
        base_url = str(params.get("base_url") or MOYSKLAD_BASE_URL).rstrip("/")
        return moysklad_source(
            token=token,
            resources=resources,
            from_days_ago=days,
            base_url=base_url,
        )
