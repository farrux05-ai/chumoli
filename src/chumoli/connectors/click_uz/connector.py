"""
chumoli.connectors.click_uz
============================

Click.uz Merchant API v2 — thin adapter (BaseUZConnector).

Auth: SHA1 digest header — Auth: {service_id}:{sha1(ts+secret)}:{timestamp}

Fix'lar (v1):
  - primary_key: "payment_id" -> "click_trans_id"  (P0: merge broken edi)
  - date format: "2026-09-20" -> "2026-09-20 00:00:00"  (P1: API kutadi)
  - error check: Click error field tekshiriladi  (P1)
  - merchant_user_id olib tashlandi (P2: chalkash, service_id yetarli)
  - invoices olib tashlandi (P2: barcha merchant'larda ishlamaydi)
"""

from __future__ import annotations

import hashlib
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

CLICK_BASE_URL    = "https://api.click.uz/v2/merchant"
CLICK_PAGE_SIZE   = 100

MANIFEST = ConnectorManifest(
    key="click_uz",
    label="Click",
    category=ConnectorCategory.UZ_PAYMENT,
    description="Click Merchant API — to'lovlar",
    dlt_source_factory="chumoli.connectors.click_uz.connector.ClickConnector",
    fields=[
        FieldSpec(
            key="service_id",
            label="Service ID",
            type=FieldType.TEXT,
            required=True,
            placeholder="12345",
        ),
        FieldSpec(
            key="secret_key",
            label="Secret key",
            type=FieldType.PASSWORD,
            required=True,
            secret=True,
        ),
        # merchant_user_id OLIB TASHLANDI — service_id yetarli
        FieldSpec(
            key="from_days_ago",
            label="Necha kun oldin (default 1)",
            type=FieldType.NUMBER,
            required=False,
            default="1",
        ),
        # invoices OLIB TASHLANDI — barcha merchant'larda ishlamaydi
    ],
)


def _build_auth_header(
    service_id: str,
    secret_key: str,
    timestamp: str | None = None,
) -> str:
    """Auth: {service_id}:{sha1(ts+secret)}:{ts}"""
    ts = timestamp or str(int(time.time()))
    digest = hashlib.sha1(f"{ts}{secret_key}".encode()).hexdigest()
    return f"{service_id}:{digest}:{ts}"


@uz_api_retry
def _get(
    client: httpx.Client,
    path: str,
    service_id: str,
    secret_key: str,
    params: dict[str, Any] | None = None,
) -> Any:
    headers = {
        "Auth": _build_auth_header(service_id, secret_key)
    }
    resp = client.get(path, params=params, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    # FIX: Click error field tekshirish (eski kodda yo'q edi)
    if isinstance(data, dict) and data.get("error") not in (None, 0, ""):
        err_note = data.get("error_note") or data.get("error")
        raise ValueError(f"Click API xato [{data.get('error')}]: {err_note}")

    return data


def _extract_payments(data: Any) -> list:
    """Click response'dan payments ro'yxatini olish.
    
    Real Click response: {"error": 0, "payments": [...]}
    Fallback: nested dict'larni ham tekshiradi.
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # To'g'ridan to'g'ri top-level (ko'p hollarda)
        if "payments" in data and isinstance(data["payments"], list):
            return data["payments"]
        # Nested
        for nested_key in ("data", "result", "payload"):
            inner = data.get(nested_key)
            if isinstance(inner, dict) and "payments" in inner:
                v = inner["payments"]
                if isinstance(v, list):
                    return v
            if isinstance(inner, list):
                return inner
    return []


@dlt.resource(
    name="payments",
    write_disposition="merge",
    primary_key="click_trans_id",   # FIX: eski "payment_id" broken edi
)
def _payments(
    service_id: str,
    secret_key: str,
    from_date: str,
    to_date: str,
) -> Iterator[dict[str, Any]]:
    page = 1
    with httpx.Client(base_url=CLICK_BASE_URL, timeout=30.0) as client:
        while True:
            data = _get(
                client,
                "/payment/list",
                service_id,
                secret_key,
                params={
                    "service_id": service_id,
                    "date_from":  from_date,
                    "date_to":    to_date,
                    "page":       page,
                    "limit":      CLICK_PAGE_SIZE,
                },
            )
            items = _extract_payments(data)
            if not items:
                break
            yield from items
            if len(items) < CLICK_PAGE_SIZE:
                break
            page += 1


class ClickConnector:
    """Click.uz Merchant API — BaseUZConnector."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        service_id = str(params["service_id"])
        secret_key = secrets["secret_key"]

        days  = int(params.get("from_days_ago") or 1)
        today = date.today()

        # FIX: "2026-09-20" o'rniga "2026-09-20 00:00:00" format
        # Click API to'liq datetime string kutadi
        from_dt   = datetime.combine(today - timedelta(days=days), datetime.min.time())
        to_dt     = datetime.combine(today, datetime.max.time().replace(microsecond=0))
        from_date = from_dt.strftime("%Y-%m-%d %H:%M:%S")
        to_date   = to_dt.strftime("%Y-%m-%d %H:%M:%S")

        return _payments(
            service_id=service_id,
            secret_key=secret_key,
            from_date=from_date,
            to_date=to_date,
        )
