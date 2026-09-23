"""
chumoli.connectors.didox
=========================

Didox elektron hujjat tizimi (EDI).

Auth: POST /api/v1/auth/login -> {accessToken}
      Header: Authorization: Bearer {accessToken}

Resources: documents (faktura, shartnoma, dalolatnoma)

Pagination: page-based, 0-indexed
  Response: {content: [...], totalElements: N, totalPages: M, number: 0}

Token: ~1 soat expire. Har run boshida yangi token olinadi.
       1 soat ichida tamomlanadigan run'lar uchun yetarli.
       
Papka: src/chumoli/connectors/didox/
Fayllar:
  __init__.py  (bo'sh)
  connector.py (shu fayl)

Ro'yxatga olish:
  src/chumoli/connectors/__init__.py ga 2 qator qo'shish:
    from chumoli.connectors.didox.connector import DidoxConnector
    # builtins listiga: ("didox", DidoxConnector),
"""

from __future__ import annotations

import time
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

DIDOX_BASE_URL     = "https://api.didox.uz"
DIDOX_PAGE_SIZE    = 50
# Hujjat turlari (Didox API qiymatlari)
DOC_TYPE_MAP = {
    "INVOICE":  "faktura",
    "CONTRACT": "shartnoma",
    "ACT":      "dalolatnoma",
    "WAYBILL":  "yuk xati",
}


MANIFEST = ConnectorManifest(
    key="didox",
    label="Didox",
    category=ConnectorCategory.UZ_GOV,
    maturity="beta",
    description="Didox EHD — faktura/shartnoma (beta: real login bilan sinang)",
    dlt_source_factory="chumoli.connectors.didox.connector.DidoxConnector",
    fields=[
        FieldSpec(
            key="username",
            label="Login (INN yoki foydalanuvchi nomi)",
            type=FieldType.TEXT,
            required=True,
            placeholder="1234567890",
            help_text="Didox kabinetiga kirish uchun ishlatiladigan login",
        ),
        FieldSpec(
            key="password",
            label="Parol",
            type=FieldType.PASSWORD,
            required=True,
            secret=True,
        ),
        FieldSpec(
            key="doc_types",
            label="Hujjat turlari",
            type=FieldType.SELECT,
            required=True,
            default="INVOICE",
            options=[
                SelectOption(value="INVOICE",              label="Fakturalar"),
                SelectOption(value="CONTRACT",             label="Shartnomalar"),
                SelectOption(value="ACT",                  label="Dalolatnomalar"),
                SelectOption(
                    value="INVOICE,CONTRACT,ACT",
                    label="Faktura + Shartnoma + Dalolatnoma",
                ),
            ],
        ),
        FieldSpec(
            key="direction",
            label="Yo'nalish",
            type=FieldType.SELECT,
            required=False,
            default="all",
            options=[
                SelectOption(value="all",      label="Hammasi"),
                SelectOption(value="outgoing", label="Faqat yuborilganlar"),
                SelectOption(value="incoming", label="Faqat qabul qilinganlar"),
            ],
            help_text="Qaysi tomondan hujjatlarni olish",
        ),
        FieldSpec(
            key="from_days_ago",
            label="Necha kun oldin (default 7)",
            type=FieldType.NUMBER,
            required=False,
            default="7",
        ),
    ],
)


def _get_token(username: str, password: str) -> str:
    """Didox'dan access token olish.
    
    POST /api/v1/auth/login
    Body: {"username": ..., "password": ...}
    Response: {"accessToken": "...", "refreshToken": "..."}
    
    Token ~1 soat yashaydi. Har run boshida chaqiriladi.
    """
    url = f"{DIDOX_BASE_URL}/api/v1/auth/login"
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                url,
                json={"username": username, "password": password},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            token = data.get("accessToken") or data.get("access_token") or data.get("token")
            if not token:
                raise ValueError(
                    f"Didox login javobida token topilmadi. Javob kalitlari: {list(data.keys())}"
                )
            return str(token)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise ValueError("Didox login: login yoki parol noto'g'ri") from e
        raise ValueError(f"Didox login xatosi [{e.response.status_code}]: {e}") from e
    except httpx.ConnectError as e:
        raise ValueError(f"Didox serverga ulanib bo'lmadi: {e}") from e


def _get_page(
    client: httpx.Client,
    doc_type: str,
    direction: str,
    from_date: str,
    to_date: str,
    page: int,
) -> dict[str, Any]:
    """Bir sahifa hujjatlarni olish."""
    params: dict[str, Any] = {
        "type":     doc_type,
        "dateFrom": from_date,
        "dateTo":   to_date,
        "page":     page,
        "size":     DIDOX_PAGE_SIZE,
    }

    # Direction filter
    if direction == "outgoing":
        params["direction"] = "OUTGOING"
    elif direction == "incoming":
        params["direction"] = "INCOMING"
    # "all" = filter yo'q

    @uz_api_retry
    def _do() -> dict[str, Any]:
        resp = client.get("/api/v1/docs", params=params)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ValueError(
                    "Didox token muddati tugadi. Pipeline'ni qayta ishga tushiring."
                ) from e
            raise
        return resp.json()

    return _do()


def _extract_content(data: Any) -> list:
    """Didox page response'dan hujjatlar ro'yxatini olish.
    
    Kutilgan format: {"content": [...], "totalElements": N, "totalPages": M}
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Asosiy Spring page format
        content = data.get("content")
        if isinstance(content, list):
            return content
        # Fallback
        for key in ("items", "documents", "data", "records"):
            v = data.get(key)
            if isinstance(v, list):
                return v
    return []


def _total_pages(data: Any) -> int:
    """Jami sahifalar sonini olish."""
    if isinstance(data, dict):
        return int(data.get("totalPages") or 1)
    return 1


@dlt.resource(
    name="documents",
    write_disposition="merge",
    primary_key="id",   # Didox hujjat ID
)
def _documents(
    token: str,
    doc_types: list[str],
    direction: str,
    from_date: str,
    to_date: str,
) -> Iterator[dict[str, Any]]:
    """Barcha tanlangan hujjat turlarini yuklash."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    with httpx.Client(base_url=DIDOX_BASE_URL, headers=headers, timeout=30.0) as client:
        for doc_type in doc_types:
            page = 0
            doc_label = DOC_TYPE_MAP.get(doc_type, doc_type.lower())

            while True:
                data = _get_page(
                    client, doc_type, direction, from_date, to_date, page
                )
                items = _extract_content(data)

                if not items:
                    break

                # Har bir hujjatga tur va yo'nalish qo'shamiz
                for doc in items:
                    doc["_doc_type"]  = doc_type
                    doc["_doc_label"] = doc_label
                    yield doc

                total = _total_pages(data)
                page += 1
                if page >= total:
                    break


class DidoxConnector:
    """Didox EHD tizimi — BaseUZConnector."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        username  = str(params["username"])
        password  = secrets["password"]
        direction = str(params.get("direction") or "all")
        days      = int(params.get("from_days_ago") or 7)

        # Token olish (run boshida bir marta)
        token = _get_token(username, password)

        # Hujjat turlari
        raw_types = str(params.get("doc_types") or "INVOICE")
        doc_types = [t.strip().upper() for t in raw_types.split(",") if t.strip()]
        if not doc_types:
            doc_types = ["INVOICE"]

        # Sana oraliq
        today     = date.today()
        from_dt   = datetime.combine(today - timedelta(days=days), datetime.min.time())
        to_dt     = datetime.combine(today, datetime.max.time().replace(microsecond=0))
        from_date = from_dt.isoformat()
        to_date   = to_dt.isoformat()

        return _documents(
            token=token,
            doc_types=doc_types,
            direction=direction,
            from_date=from_date,
            to_date=to_date,
        )
