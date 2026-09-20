"""
chumoli.connectors.click_uz
============================

Click.uz Merchant API v2 — thin adapter (BaseUZConnector).

Auth: SHA1 digest header  Auth: {id}:{digest}:{timestamp}
      digest = sha1(timestamp + secret_key)

Resources: payments (default), invoices
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import dlt
import httpx

from chumoli.core.manifest import (
    ConnectorCategory,
    ConnectorManifest,
    FieldSpec,
    FieldType,
    SelectOption,
)

CLICK_BASE_URL = "https://api.click.uz/v2/merchant"
CLICK_PAGE_SIZE = 100
CLICK_RETRY_DELAYS = [1.0, 3.0, 10.0]


MANIFEST = ConnectorManifest(
    key="click_uz",
    label="Click",
    category=ConnectorCategory.UZ_PAYMENT,
    description="Click Merchant API — to'lovlar va invoice'lar",
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
        FieldSpec(
            key="merchant_user_id",
            label="Merchant user ID (ixtiyoriy)",
            type=FieldType.TEXT,
            required=False,
            help_text="Bo'sh qoldirilsa service_id ishlatiladi",
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
            default="payments",
            options=[
                SelectOption(value="payments", label="Payments"),
                SelectOption(value="invoices", label="Invoices"),
                SelectOption(value="payments,invoices", label="Payments + Invoices"),
            ],
        ),
    ],
)


def _build_auth_header(
    service_id: str,
    secret_key: str,
    timestamp: str | None = None,
    merchant_user_id: str | None = None,
) -> str:
    ts = timestamp or str(int(time.time()))
    digest = hashlib.sha1(f"{ts}{secret_key}".encode()).hexdigest()
    user = merchant_user_id or service_id
    return f"{user}:{digest}:{ts}"


def _get(
    client: httpx.Client,
    path: str,
    service_id: str,
    secret_key: str,
    merchant_user_id: str | None,
    params: dict[str, Any] | None = None,
) -> Any:
    last_exc: Exception | None = None
    for delay in CLICK_RETRY_DELAYS:
        try:
            headers = {
                "Auth": _build_auth_header(
                    service_id, secret_key, merchant_user_id=merchant_user_id
                )
            }
            resp = client.get(path, params=params, headers=headers)
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
    raise RuntimeError("Click API failed after retries") from last_exc


def _extract_items(data: Any, *keys: str) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in keys:
            v = data.get(k)
            if isinstance(v, list):
                return v
        for nested in ("data", "result", "payload"):
            inner = data.get(nested)
            if isinstance(inner, list):
                return inner
            if isinstance(inner, dict):
                for k in keys:
                    v = inner.get(k)
                    if isinstance(v, list):
                        return v
    return []


@dlt.resource(name="payments", write_disposition="merge", primary_key="payment_id")
def _payments(
    service_id: str,
    secret_key: str,
    merchant_user_id: str | None,
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
                merchant_user_id,
                params={
                    "service_id": service_id,
                    "date_from": from_date,
                    "date_to": to_date,
                    "page": page,
                    "limit": CLICK_PAGE_SIZE,
                },
            )
            items = _extract_items(data, "payments", "payment_list")
            if not items:
                break
            yield from items
            if len(items) < CLICK_PAGE_SIZE:
                break
            page += 1


@dlt.resource(name="invoices", write_disposition="merge", primary_key="invoice_id")
def _invoices(
    service_id: str,
    secret_key: str,
    merchant_user_id: str | None,
    from_date: str,
    to_date: str,
) -> Iterator[dict[str, Any]]:
    page = 1
    with httpx.Client(base_url=CLICK_BASE_URL, timeout=30.0) as client:
        while True:
            data = _get(
                client,
                "/invoice/list",
                service_id,
                secret_key,
                merchant_user_id,
                params={
                    "service_id": service_id,
                    "date_from": from_date,
                    "date_to": to_date,
                    "page": page,
                    "limit": CLICK_PAGE_SIZE,
                },
            )
            items = _extract_items(data, "invoices", "invoice_list")
            if not items:
                break
            yield from items
            if len(items) < CLICK_PAGE_SIZE:
                break
            page += 1


@dlt.source(name="click_uz")
def _click_source(
    service_id: str,
    secret_key: str,
    merchant_user_id: str | None,
    from_date: str,
    to_date: str,
    resources: list[str],
) -> Any:
    out = []
    if "payments" in resources:
        out.append(
            _payments(service_id, secret_key, merchant_user_id, from_date, to_date)
        )
    if "invoices" in resources:
        out.append(
            _invoices(service_id, secret_key, merchant_user_id, from_date, to_date)
        )
    return out


class ClickConnector:
    """Click.uz Merchant API — BaseUZConnector."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        service_id = str(params["service_id"])
        secret_key = secrets["secret_key"]
        merchant_user_id = params.get("merchant_user_id") or None
        if merchant_user_id:
            merchant_user_id = str(merchant_user_id)

        days = int(params.get("from_days_ago") or 1)
        today = date.today()
        from_date = (today - timedelta(days=days)).isoformat()
        to_date = today.isoformat()

        raw = params.get("resources") or "payments"
        resources = [r.strip() for r in str(raw).split(",") if r.strip()]

        return _click_source(
            service_id=service_id,
            secret_key=secret_key,
            merchant_user_id=merchant_user_id,
            from_date=from_date,
            to_date=to_date,
            resources=resources,
        )
