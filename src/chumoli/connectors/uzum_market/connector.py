"""
chumoli.connectors.uzum_market
===============================

Uzum Market Seller API.

Auth: Authorization: Bearer {token}

Fix'lar (v1):
  - primary_key: "id" -> "orderId"  (P0: merge broken edi)
  - Pagination: offset -> page-based (0-indexed)  (P1)
  - Date format: "2026-09-20" -> "2026-09-20T00:00:00"  (P1)
  - finance_report olib tashlandi (endpoint noaniq)  (P1)
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any

import dlt
import httpx

from chumoli.core.retry_policy import uz_api_retry
from chumoli.core.manifest import (
    ConnectorCategory,
    ConnectorManifest,
    FieldSpec,
    FieldType,
    SelectOption,
)

UZUM_BASE_URL     = "https://api-seller.uzum.uz/api"
UZUM_PAGE_SIZE    = 100

MANIFEST = ConnectorManifest(
    key="uzum_market",
    label="Uzum Market",
    category=ConnectorCategory.UZ_PAYMENT,
    maturity="beta",
    description="Uzum Seller API — buyurtmalar (beta)",
    dlt_source_factory="chumoli.connectors.uzum_market.connector.UzumMarketConnector",
    fields=[
        FieldSpec(
            key="api_key",
            label="API kalit (Bearer)",
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
        # finance_report OLIB TASHLANDI — endpoint noaniq
        # Faqat orders barqaror ishlaydi
    ],
)


@uz_api_retry
def _get(client: httpx.Client, path: str, params: dict[str, Any] | None = None) -> Any:
    resp = client.get(path, params=params)
    resp.raise_for_status()
    return resp.json()


def _extract_orders(data: Any) -> list:
    """Uzum response: {"payload": {"orders": [...], "totalCount": N}}"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Uzum asosiy format
        payload = data.get("payload")
        if isinstance(payload, dict):
            orders = payload.get("orders") or payload.get("items") or payload.get("content")
            if isinstance(orders, list):
                return orders
        # Fallback
        for key in ("orders", "items", "content", "data"):
            v = data.get(key)
            if isinstance(v, list):
                return v
    return []


@dlt.resource(
    name="orders",
    write_disposition="merge",
    primary_key="orderId",   # FIX: eski "id" broken edi
)
def _orders(
    api_key: str,
    from_date: str,
    to_date: str,
) -> Iterator[dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    # FIX: offset emas page-based pagination (0-indexed)
    page = 0
    with httpx.Client(base_url=UZUM_BASE_URL, headers=headers, timeout=30.0) as client:
        while True:
            data = _get(
                client,
                "/v1/order/list",
                {
                    "dateFrom": from_date,
                    "dateTo":   to_date,
                    "size":     UZUM_PAGE_SIZE,
                    "page":     page,           # FIX: offset -> page
                },
            )
            items = _extract_orders(data)
            if not items:
                break
            yield from items
            if len(items) < UZUM_PAGE_SIZE:
                break
            page += 1   # FIX: offset += PAGE_SIZE o'rniga page += 1


class UzumMarketConnector:
    """Uzum Market Seller — BaseUZConnector."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        api_key = secrets["api_key"]
        days    = int(params.get("from_days_ago") or 1)
        today   = date.today()

        # FIX: "2026-09-20" -> "2026-09-20T00:00:00" (Uzum ISO format kutadi)
        from_dt   = datetime.combine(today - timedelta(days=days), datetime.min.time())
        to_dt     = datetime.combine(today, datetime.max.time().replace(microsecond=0))
        from_date = from_dt.isoformat()
        to_date   = to_dt.isoformat()

        return _orders(
            api_key=api_key,
            from_date=from_date,
            to_date=to_date,
        )
