"""
chumoli.connectors.payme_uz
============================

Payme (Paycom) merchant — JSON-RPC 2.0.

Auth: X-Auth: base64(merchant_id:api_key)
Method: receipts.get_all (kunlik bo'laklar, offset pagination)

Fix'lar (v1):
  - Timezone: UTC o'rniga Asia/Tashkent da kun boshini hisoblash
  - Retry: [2.0, 5.0, 15.0] — biroz kuchliroq
"""

from __future__ import annotations

import base64
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo
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

PAYME_API_URL     = "https://checkout.paycom.uz/api"
PAYME_SANDBOX_URL = "https://checkout.test.paycom.uz/api"
PAYME_PAGE_SIZE   = 50
PAYME_RETRY_DELAYS = [2.0, 5.0, 15.0]   # FIX: eski [1.0, 2.0, 5.0] dan kuchliroq

TZ_TASHKENT = ZoneInfo("Asia/Tashkent")


MANIFEST = ConnectorManifest(
    key="payme_uz",
    label="Payme",
    category=ConnectorCategory.UZ_PAYMENT,
    description="Payme merchant — cheklar (receipts.get_all)",
    dlt_source_factory="chumoli.connectors.payme_uz.connector.PaymeConnector",
    fields=[
        FieldSpec(
            key="merchant_id",
            label="Merchant ID",
            type=FieldType.TEXT,
            required=True,
            placeholder="64f...",
        ),
        FieldSpec(
            key="api_key",
            label="API kalit",
            type=FieldType.PASSWORD,
            required=True,
            secret=True,
        ),
        FieldSpec(
            key="sandbox",
            label="Muhit",
            type=FieldType.SELECT,
            required=True,
            default="false",
            options=[
                SelectOption(value="false", label="Production"),
                SelectOption(value="true",  label="Sandbox (test)"),
            ],
        ),
        FieldSpec(
            key="from_days_ago",
            label="Necha kun oldin (default 1)",
            type=FieldType.NUMBER,
            required=False,
            default="1",
        ),
        FieldSpec(
            key="state",
            label="Holat filtri (ixtiyoriy)",
            type=FieldType.SELECT,
            required=False,
            default="",
            options=[
                SelectOption(value="",  label="Hammasi"),
                SelectOption(value="1", label="Yaratilgan"),
                SelectOption(value="2", label="To'lovda"),
                SelectOption(value="4", label="To'langan"),
                SelectOption(value="-1", label="Bekor qilingan"),
            ],
            help_text="Bo'sh = barcha holatlar",
        ),
    ],
)


def _auth_header(merchant_id: str, api_key: str) -> str:
    return base64.b64encode(f"{merchant_id}:{api_key}".encode()).decode()


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _from_ms(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def _jsonrpc(
    client: httpx.Client,
    url: str,
    method: str,
    params: dict[str, Any],
    auth_header: str,
    req_id: int = 1,
) -> dict[str, Any]:
    last_exc: Exception | None = None
    for delay in PAYME_RETRY_DELAYS:
        try:
            resp = client.post(
                url,
                json={"id": req_id, "method": method, "params": params},
                headers={
                    "X-Auth": auth_header,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                err = data["error"]
                raise ValueError(
                    f"Payme API [{err.get('code', '?')}]: {err.get('message', 'unknown')}"
                )
            return data.get("result") or {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429,) or e.response.status_code >= 500:
                time.sleep(delay)
                last_exc = e
            else:
                raise
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            time.sleep(delay)
            last_exc = e
    raise RuntimeError("Payme API failed after retries") from last_exc


def _fetch_day(
    client: httpx.Client,
    url: str,
    auth_header: str,
    day_start: datetime,
    day_end: datetime,
    state_filter: int | None,
) -> Iterator[dict[str, Any]]:
    offset = 0
    req_id = 1
    while True:
        result = _jsonrpc(
            client, url, "receipts.get_all",
            {
                "from":   _to_ms(day_start),
                "to":     _to_ms(day_end),
                "count":  PAYME_PAGE_SIZE,
                "offset": offset,
            },
            auth_header,
            req_id,
        )
        req_id += 1
        receipts = result.get("receipts") or []
        if not receipts:
            break
        for receipt in receipts:
            if state_filter is not None and receipt.get("state") != state_filter:
                continue
            # ISO timestamp'lar qo'shimcha field sifatida
            for field, key in (
                ("create_time", "_create_time_iso"),
                ("pay_time",    "_pay_time_iso"),
                ("cancel_time", "_cancel_time_iso"),
            ):
                ms = receipt.get(field)
                receipt[key] = _from_ms(ms).isoformat() if ms else None
            yield receipt
        if len(receipts) < PAYME_PAGE_SIZE:
            break
        offset += PAYME_PAGE_SIZE


@dlt.resource(name="receipts", write_disposition="merge", primary_key="_id")
def _receipts(
    merchant_id: str,
    api_key: str,
    from_date: datetime,
    to_date: datetime,
    state_filter: int | None,
    sandbox: bool,
) -> Iterator[dict[str, Any]]:
    url  = PAYME_SANDBOX_URL if sandbox else PAYME_API_URL
    auth = _auth_header(merchant_id, api_key)
    with httpx.Client(timeout=30.0) as client:
        current = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = to_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        while current <= end:
            day_end = min(
                current.replace(hour=23, minute=59, second=59, microsecond=999999),
                end,
            )
            yield from _fetch_day(client, url, auth, current, day_end, state_filter)
            current += timedelta(days=1)


class PaymeConnector:
    """Payme merchant — BaseUZConnector."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        merchant_id = str(params["merchant_id"])
        api_key     = secrets["api_key"]
        sandbox     = str(params.get("sandbox") or "false").lower() in ("1", "true", "yes")

        days = int(params.get("from_days_ago") or 1)

        # FIX: Toshkent vaqtida kun boshi hisoblash (eski kod UTC ishlatardi)
        now_tashkent    = datetime.now(TZ_TASHKENT)
        today_start_local = now_tashkent.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        from_date = (today_start_local - timedelta(days=days)).astimezone(UTC)
        to_date   = (today_start_local - timedelta(seconds=1)).astimezone(UTC)

        state_raw    = params.get("state")
        state_filter: int | None = None
        if state_raw not in (None, ""):
            state_filter = int(state_raw)

        return _receipts(
            merchant_id=merchant_id,
            api_key=api_key,
            from_date=from_date,
            to_date=to_date,
            state_filter=state_filter,
            sandbox=sandbox,
        )
