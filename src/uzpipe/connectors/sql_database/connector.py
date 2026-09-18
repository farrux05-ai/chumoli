"""
uzpipe.connectors.sql_database.connector
===========================================

dlt'ning tayyor `sql_database` source'i ustidagi yupqa adapter.

NEGA `table_names` VERGUL BILAN AJRATILGAN BITTA MATN MAYDONI,
RO'YXAT (multi-select) EMAS
--------------------------------------------------------------------
Manifest tizimida `FieldType.SELECT` bor, lekin u FAQAT oldindan
ma'lum variantlar uchun ishlaydi (masalan auth turi). Jadval nomlari
esa foydalanuvchining o'z bazasiga bog'liq — ular oldindan noma'lum,
va ularni bilish uchun avval bazaga ulanish kerak bo'lardi (formaga
"live" so'rov). Bu MVP darajasida ortiqcha murakkablik: oddiy matn
maydoni ("orders, customers, payments") ancha sodda, va dlt buni
o'zi vergul bo'yicha bo'lib, har biri uchun alohida resource yaratadi.
Kelajakda, agar kerak bo'lsa, "ulanishni tekshirish va jadvallar
ro'yxatini ko'rsatish" alohida, ixtiyoriy UI qadamiga aylanishi
mumkin — bu ANIQ shu connector faylini o'zgartirishni talab qilmaydi,
chunki forma darajasidagi funksionallik.

NEGA INCREMENTAL SOZLAMASI (cursor_field) MANIFESTDA IXTIYORIY
--------------------------------------------------------------------
ROADMAP.md incremental yuklashni "Cursor column-based" deb belgilagan.
Bu yerda `cursor_column` maydoni required=False qilingan: agar
foydalanuvchi bo'sh qoldirsa, dlt to'liq (full refresh) rejimda
ishlaydi. Buni majburiy qilish "birinchi ulanish" tajribasini
og'irlashtirar edi — foydalanuvchi avval jadvalni ko'rishni, keyin
incremental sozlashni xohlashi mumkin.
"""

from __future__ import annotations

from typing import Any

from dlt.sources.sql_database import sql_database

from uzpipe.connectors.base import BaseUZConnector
from uzpipe.core.manifest import ConnectorCategory, ConnectorManifest, FieldSpec, FieldType

MANIFEST = ConnectorManifest(
    key="sql_database",
    label="SQL Database",
    category=ConnectorCategory.UNIVERSAL,
    description="PostgreSQL, MySQL, MSSQL, SQLite, Oracle (dlt built-in)",
    dlt_source_factory="uzpipe.connectors.sql_database.connector.SqlDatabaseConnector",
    fields=[
        FieldSpec(
            key="connection_string",
            label="Connection string",
            type=FieldType.PASSWORD,
            required=True,
            secret=True,
            placeholder="postgresql://user:pass@host:5432/db",
            help_text=(
                "Connection string maxfiy deb belgilangan, chunki odatda "
                "login/parol o'zida saqlaydi"
            ),
        ),
        FieldSpec(
            key="table_names",
            label="Jadval nomlari",
            type=FieldType.TEXT,
            required=True,
            placeholder="orders, customers",
            help_text="Vergul bilan ajrating, bir nechta jadval kiritish mumkin",
        ),
        FieldSpec(
            key="cursor_column",
            label="Incremental ustun (ixtiyoriy)",
            type=FieldType.TEXT,
            required=False,
            placeholder="updated_at",
            help_text="Bo'sh qoldirilsa, har safar to'liq yuklanadi",
        ),
    ],
)


class SqlDatabaseConnector:
    """`BaseUZConnector` protocol'iga mos, dlt'ning sql_database source'ini chaqiruvchi adapter."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        table_names = [t.strip() for t in params["table_names"].split(",") if t.strip()]
        cursor_column = params.get("cursor_column") or None

        kwargs: dict[str, Any] = {
            "credentials": secrets["connection_string"],
            "table_names": table_names,
        }
        if cursor_column:
            # dlt'ning incremental parametri table-level emas,
            # source-level bo'lgani uchun bu yerda barcha tanlangan
            # jadvallar BIR XIL cursor ustunini ishlatadi deb
            # taxmin qilinadi. Agar jadvallarning cursor ustunlari
            # farqli bo'lsa, foydalanuvchi hozircha ularni ALOHIDA
            # pipeline sifatida qo'shishi kerak — bu chegara ataylab
            # hujjatlashtirilgan, chunki "har jadval uchun alohida
            # cursor maydoni" formani sezilarli murakkablashtirar edi.
            import dlt

            kwargs["incremental"] = dlt.sources.incremental(cursor_column)

        return sql_database(**kwargs)
