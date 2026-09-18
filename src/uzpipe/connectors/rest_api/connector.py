"""
uzpipe.connectors.rest_api.connector
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
o'zi pagination turlarini (page_number, offset, cursor — ROADMAP.md da
tasdiqlangan) va auth turlarini (api_key, bearer, basic) ICHKARIDA hal
qiladi. UzPipe'ning vazifasi — foydalanuvchidan formadagi oddiy
qiymatlarni olib, dlt kutgan konfiguratsiya shakliga aylantirish,
pagination algoritmini qayta yozish emas. Bu "dlt ustiga qo'shamiz,
dlt'ni qayta yozmaymiz" tamoyilining aynan shu connector darajasidagi
ko'rinishi.
"""

from __future__ import annotations

from typing import Any

from dlt.sources.rest_api import rest_api_source

from uzpipe.connectors.base import BaseUZConnector
from uzpipe.core.manifest import (
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
    dlt_source_factory="uzpipe.connectors.rest_api.connector.RestApiConnector",
    fields=[
        FieldSpec(
            key="base_url",
            label="Base URL",
            type=FieldType.TEXT,
            required=True,
            placeholder="https://api.example.com",
        ),
        FieldSpec(
            key="endpoint",
            label="Endpoint",
            type=FieldType.TEXT,
            required=True,
            placeholder="/data",
            help_text="Base URL'ga qo'shiladigan yo'l, masalan /users",
        ),
        FieldSpec(
            key="auth_type",
            label="Autentifikatsiya turi",
            type=FieldType.SELECT,
            required=True,
            default="none",
            options=[
                SelectOption(value="none", label="Yo'q"),
                SelectOption(value="api_key", label="API key"),
                SelectOption(value="bearer", label="Bearer token"),
                SelectOption(value="basic", label="Login/parol (Basic)"),
            ],
        ),
        # Diqqat: quyidagi ikkita maydon HAR DOIM ko'rsatiladi, lekin
        # forma darajasida auth_type=none bo'lsa yashiriladi (bu UI
        # mantig'i, manifestda emas — manifest faqat "bu maydon
        # mavjud, secret" deb e'lon qiladi, "qachon ko'rsatish"ni
        # dashboard hal qiladi).
        FieldSpec(
            key="auth_key_name",
            label="Header/parametr nomi",
            type=FieldType.TEXT,
            required=False,
            default="Authorization",
            help_text="Faqat 'API key' turi uchun, masalan X-API-Key",
        ),
        FieldSpec(
            key="secret_value",
            label="API key / token / parol",
            type=FieldType.PASSWORD,
            required=False,
            secret=True,
            help_text="auth_type 'Yo'q' bo'lsa bo'sh qoldiring",
        ),
    ],
)


class RestApiConnector:
    """`BaseUZConnector` protocol'iga mos, dlt'ning rest_api_source'ini chaqiruvchi adapter."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        auth_type = params.get("auth_type", "none")
        auth_config: dict[str, Any] | None = None

        secret_value = secrets.get("secret_value")

        if auth_type == "api_key" and secret_value:
            auth_config = {
                "type": "api_key",
                "name": params.get("auth_key_name", "Authorization"),
                "api_key": secret_value,
                "location": "header",
            }
        elif auth_type == "bearer" and secret_value:
            auth_config = {"type": "bearer", "token": secret_value}
        elif auth_type == "basic" and secret_value:
            # Basic auth uchun "login:parol" formatida kutamiz —
            # bu formani ikkita alohida maydonga bo'lish o'rniga
            # bitta secret_value'ga sig'diradi. Bu ATAYLAB shunday:
            # manifestga har bir auth turi uchun alohida maydon
            # qo'shish (api_key_field, bearer_field, basic_user_field,
            # basic_pass_field...) forma murakkabligini oshiradi.
            # Amalda REST API connector'ini Basic auth bilan ishlatish
            # kam uchraydigan holat (UZ connectorlar bunga tayanmaydi),
            # shuning uchun bu yerda soddalik murakkablikdan ustun
            # qo'yildi.
            login, _, password = secret_value.partition(":")
            auth_config = {"type": "http_basic", "username": login, "password": password}

        source_config: dict[str, Any] = {
            "client": {
                "base_url": params["base_url"],
                **({"auth": auth_config} if auth_config else {}),
            },
            "resources": [
                {
                    "name": params["endpoint"].strip("/").replace("/", "_") or "data",
                    "endpoint": {"path": params["endpoint"]},
                }
            ],
        }

        return rest_api_source(source_config)
