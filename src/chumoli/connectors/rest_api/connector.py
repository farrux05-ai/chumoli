"""
chumoli.connectors.rest_api.connector
=======================================

dlt'ning tayyor `rest_api_source` ustidagi eng yupqa adapter.

NEGA BU CONNECTOR BIRINCHI YOZILDI (Payme'dan oldin)
--------------------------------------------------------
ARCHITECTURE_DECISION.md 5-bandida aytilganidek: "fundament ular
ustida sinaladi". `rest_api` va `sql_database` — dlt'ning eng
universal, eng ko'p sinalgan source'lari. Agar manifest tizimi,
config qatlami va credential encryption AYNAN shular ustida to'g'ri
ishlamasa, Payme yoki Click kabi custom auth sxemali (HMAC, JSON-RPC)
connectorlarda muammoni topish ancha qiyinlashadi. Bu connector —
butun fundamentni tekshiruvchi "smoke test" vazifasini ham bajaradi.

NEGA BU YERDA PAGINATION/AUTH MANTIG'I DEYARLI YO'Q
--------------------------------------------------------
`build_dlt_source` funksiyasining tanasi atigi bir necha qatordan
iborat — bu KAMChILIK EMAS, bu ATAYLAB. dlt'ning `rest_api_source`
o'zi pagination turlarini va auth turlarini ICHKARIDA hal qiladi.
Chumoli'ning vazifasi — foydalanuvchidan formadagi oddiy qiymatlarni
olib, dlt kutgan konfiguratsiya shakliga aylantirish.

Handoff (REST integration) dan kelgan himoya qoidalari
--------------------------------------------------------
1. Bo'sh header nomi → Python `ValueError: Invalid header name b''`
2. Endpoint ichidagi `?page=1` + dlt paginator → `?page=1&page=1` (400)
3. Auto-pagination (TMDB 500+ sahifa) → UI timeout
Default: single_page (yoki max_pages bilan chegaralangan page_number).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlparse

from chumoli.core.manifest import (
    ConnectorCategory,
    ConnectorManifest,
    FieldSpec,
    FieldType,
    SelectOption,
)

MANIFEST = ConnectorManifest(
    key="rest_api",
    label="REST API",
    category=ConnectorCategory.UNIVERSAL,
    description="Har qanday HTTP REST API'dan ma'lumot olish (dlt built-in)",
    dlt_source_factory="chumoli.connectors.rest_api.connector.RestApiConnector",
    fields=[
        FieldSpec(
            key="base_url",
            label="Asosiy URL",
            type=FieldType.TEXT,
            required=True,
            placeholder="https://api.example.com",
            help_text="API ning bosh manzili. Endpoint alohida qo'shiladi.",
        ),
        FieldSpec(
            key="endpoint",
            label="Endpoint (yo'l)",
            type=FieldType.TEXT,
            required=True,
            placeholder="/posts",
            help_text=(
                "Asosiy URL ga qo'shiladigan yo'l — masalan /posts yoki /api/v1/orders. "
                "? belgisidan keyingi query parametrlarni yozmang."
            ),
        ),
        FieldSpec(
            key="auth_type",
            label="Kirish turi",
            type=FieldType.SELECT,
            required=True,
            default="none",
            options=[
                SelectOption(value="none", label="Ochiq API — token kerak emas"),
                SelectOption(value="api_key", label="API kalit (header yoki URL)"),
                SelectOption(value="bearer", label="Bearer token"),
                SelectOption(value="basic", label="Login + parol (Basic)"),
            ],
        ),
        FieldSpec(
            key="auth_key_name",
            label="Kalit nomi",
            type=FieldType.TEXT,
            required=False,
            default="X-API-Key",
            help_text=(
                "API kalit qanday nomlanadi? "
                "Header: X-API-Key, Authorization; "
                "URL: api_key, token, appid (NASA, TMDB)"
            ),
        ),
        FieldSpec(
            key="auth_location",
            label="Kalit qayerga qo'yiladi",
            type=FieldType.SELECT,
            required=False,
            default="header",
            options=[
                SelectOption(value="header", label="Header (standart, xavfsizroq)"),
                SelectOption(value="query", label="URL ichida (?api_key=…)"),
            ],
            help_text="Ko'p API'lar header ishlatadi. NASA, OpenWeather URL ishlatadi.",
        ),
        FieldSpec(
            key="secret_value",
            label="Token / API kalit / Parol",
            type=FieldType.PASSWORD,
            required=False,
            secret=True,
            help_text=(
                "Ochiq API (token kerak emas) bo'lsa bo'sh qoldiring. "
                "Basic kirish uchun: login:parol formatida."
            ),
        ),
        FieldSpec(
            key="max_pages",
            label="Sahifalar chegarasi",
            type=FieldType.NUMBER,
            required=False,
            default="1",
            help_text=(
                "1 = faqat birinchi sahifa (sinov uchun). "
                "Ko'proq ma'lumot kerak bo'lsa oshiring — masalan 10 yoki 50. "
                "Cheksiz qoldirsangiz juda uzoq ishlashi mumkin."
            ),
        ),
    ],
)


def _clean_endpoint(raw: str) -> tuple[str, dict[str, str]]:
    """Endpoint path dan query string ni ajratadi.

    Foydalanuvchi `/movie/popular?page=1` yozsa, dlt o'z paginatorini
    yana `page` qo'shib `?page=1&page=1` qiladi — shuning uchun path
    toza bo'lishi kerak. Query parametrlar alohida `params` ga o'tadi
    (pagination paramlarini keyinroq max_pages boshqaradi).
    """
    text = (raw or "").strip()
    if not text:
        return "/", {}

    # Absolute URL berilgan bo'lsa — faqat path+query ni olamiz
    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        path = parsed.path or "/"
        query = dict(parse_qsl(parsed.query, keep_blank_values=False))
        return path or "/", query

    if "?" in text:
        path, _, q = text.partition("?")
        path = path.strip() or "/"
        if not path.startswith("/"):
            path = "/" + path
        query = dict(parse_qsl(q, keep_blank_values=False))
        return path, query

    path = text if text.startswith("/") else f"/{text}"
    return path, {}


def _parse_max_pages(raw: Any) -> int:
    """Default 1; invalid/empty → 1; kamida 1."""
    if raw is None or raw == "":
        return 1
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return 1
    return max(1, n)


def _build_auth_config(
    auth_type: str,
    secret_value: str | None,
    auth_key_name: str | None,
    auth_location: str | None,
) -> dict[str, Any] | None:
    """dlt rest_api auth config. Bo'sh header nomini hech qachon yubormaydi."""
    if not secret_value:
        return None

    if auth_type == "api_key":
        name = (auth_key_name or "").strip()
        if not name:
            raise ValueError(
                "API key autentifikatsiyasi uchun 'Header/parametr nomi' majburiy "
                "(masalan X-API-Key yoki api_key). Bo'sh nom HTTP xatosiga olib keladi."
            )
        location = (auth_location or "header").strip().lower()
        if location not in ("header", "query"):
            location = "header"
        return {
            "type": "api_key",
            "name": name,
            "api_key": secret_value,
            "location": location,
        }

    if auth_type == "bearer":
        return {"type": "bearer", "token": secret_value}

    if auth_type == "basic":
        # Basic: "login:parol" bitta secret_value da
        login, _, password = secret_value.partition(":")
        return {"type": "http_basic", "username": login, "password": password}

    return None


def _build_paginator(max_pages: int) -> Any:
    """1 sahifa → single_page; ko'p → page_number + maximum_page."""
    if max_pages <= 1:
        return "single_page"
    return {
        "type": "page_number",
        "page_param": "page",
        "total_path": None,
        "maximum_page": max_pages,
        "stop_after_empty_page": True,
    }


def build_rest_api_config(
    params: dict[str, Any], secrets: dict[str, str]
) -> dict[str, Any]:
    """Test qilinadigan sof config builder (dlt chaqirmasdan)."""
    path, path_query = _clean_endpoint(str(params.get("endpoint") or "/"))
    max_pages = _parse_max_pages(params.get("max_pages"))
    auth_config = _build_auth_config(
        auth_type=str(params.get("auth_type") or "none"),
        secret_value=secrets.get("secret_value") or None,
        auth_key_name=params.get("auth_key_name"),
        auth_location=params.get("auth_location"),
    )

    # Pathdagi query dan pagination kalitlarini olib tashlash —
    # aks holda paginator bilan to'qnashadi (?page=1&page=1)
    endpoint_params = {
        k: v
        for k, v in path_query.items()
        if k.lower() not in ("page", "offset", "cursor", "next")
    }

    resource_name = path.strip("/").replace("/", "_") or "data"
    endpoint_cfg: dict[str, Any] = {
        "path": path,
        "paginator": _build_paginator(max_pages),
    }
    if endpoint_params:
        endpoint_cfg["params"] = endpoint_params

    client: dict[str, Any] = {"base_url": params["base_url"]}
    if auth_config:
        client["auth"] = auth_config

    return {
        "client": client,
        "resources": [
            {
                "name": resource_name,
                "endpoint": endpoint_cfg,
            }
        ],
    }


class RestApiConnector:
    """`BaseUZConnector` protocol'iga mos, dlt'ning rest_api_source'ini chaqiruvchi adapter."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        from dlt.sources.rest_api import rest_api_source

        config = build_rest_api_config(params, secrets)
        return rest_api_source(config)
