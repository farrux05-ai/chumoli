"""
uzpipe.connectors.uzum_market
===============================

Uzum Market Seller API.

Auth: Bearer token
Resources: orders (default), finance_report
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import dlt
import httpx

from uzpipe.core.manifest import (
    ConnectorCategory,
    ConnectorManifest,
    FieldSpec,
    FieldType,
    SelectOption,
)

UZUM_BASE_URL = "https://api-seller.uzum.uz/api"
UZUM_PAGE_SIZE = 100
UZUM_RETRY_DELAYS = [1.0, 3.0, 10.0]


MANIFEST = ConnectorManifest(
    key="uzum_market",
    label="Uzum Market",
    category=ConnectorCategory.UZ_PAYMENT,
    description="Uzum Seller API — buyurtmalar va moliyaviy hisobot",
    dlt_source_factory="uzpipe.connectors.uzum_market.connector.UzumMarketConnector",
    fields=[
        FieldSpec(
            key="api_key",
            label="API key (Bearer)",
            type=FieldType.PASSWORD,
            required=True,
            secret=True,
        ),
        FieldSpec(
            key="from_days_ago",
            label="Necha kun oldin (default 1)",
            type=FieldType.NUMBER,
            required=False,
            default="1",
        ),
        FieldSpec(
            key="resources",
            label="Resource'lar",
            type=FieldType.SELECT,
            required=True,
            default="orders",
            options=[
                SelectOption(value="orders", label="Orders"),
                SelectOption(value="finance_report", label="Finance report"),
                SelectOption(value="orders,finance_report", label="Orders + Finance"),
            ],
        ),
    ],
)


def _get(client: httpx.Client, path: str, params: dict[str, Any] | None = None) -> Any:
    last_exc: Exception | None = None
    for delay in UZUM_RETRY_DELAYS:
        try:
            resp = client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 or e.response.status_code >= 500:
                time.sleep(delay)
                last_exc = e
            else:
                raise
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            time.sleep(delay)
            last_exc = e
    raise RuntimeError("Uzum API failed after retries") from last_exc


def _extract_items(data: Any, *keys: str) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in keys:
            v = data.get(k)
            if isinstance(v, list):
                return v
        payload = data.get("payload")
        if isinstance(payload, dict):
            for k in keys:
                v = payload.get(k)
                if isinstance(v, list):
                    return v
        for nested in ("data", "items"):
            v = data.get(nested)
            if isinstance(v, list):
                return v
    return []


@dlt.resource(name="orders", write_disposition="merge", primary_key="id")
def _orders(api_key: str, from_date: str, to_date: str) -> Iterator[dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    offset = 0
    with httpx.Client(base_url=UZUM_BASE_URL, headers=headers, timeout=30.0) as client:
        while True:
            data = _get(
                client,
                "/v1/order/list",
                {
                    "dateFrom": from_date,
                    "dateTo": to_date,
                    "size": UZUM_PAGE_SIZE,
                    "offset": offset,
                },
            )
            items = _extract_items(data, "orders")
            if not items:
                break
            yield from items
            if len(items) < UZUM_PAGE_SIZE:
                break
            offset += UZUM_PAGE_SIZE


@dlt.resource(name="finance_report", write_disposition="merge", primary_key="id")
def _finance(api_key: str, from_date: str, to_date: str) -> Iterator[dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    offset = 0
    with httpx.Client(base_url=UZUM_BASE_URL, headers=headers, timeout=30.0) as client:
        while True:
            data = _get(
                client,
                "/v1/finance/report",
                {
                    "dateFrom": from_date,
                    "dateTo": to_date,
                    "size": UZUM_PAGE_SIZE,
                    "offset": offset,
                },
            )
            items = _extract_items(data, "items")
            if not items:
                break
            yield from items
            if len(items) < UZUM_PAGE_SIZE:
                break
            offset += UZUM_PAGE_SIZE


@dlt.source(name="uzum_market")
def _uzum_source(
    api_key: str, from_date: str, to_date: str, resources: list[str]
) -> Any:
    out = []
    if "orders" in resources:
        out.append(_orders(api_key, from_date, to_date))
    if "finance_report" in resources:
        out.append(_finance(api_key, from_date, to_date))
    return out


class UzumMarketConnector:
    """Uzum Market Seller — BaseUZConnector."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        api_key = secrets["api_key"]
        days = int(params.get("from_days_ago") or 1)
        today = date.today()
        from_date = (today - timedelta(days=days)).isoformat()
        to_date = today.isoformat()

        raw = params.get("resources") or "orders"
        resources = [r.strip() for r in str(raw).split(",") if r.strip()]

        return _uzum_source(api_key, from_date, to_date, resources)
