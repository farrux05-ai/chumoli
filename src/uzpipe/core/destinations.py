"""
uzpipe.core.destinations
==========================

dlt built-in destinationlarning UI/API katalogi.

NEGA FAQAT SHU TO'RTALIK (BigQuery/Snowflake yo'q)
----------------------------------------------------
Strategiya: sifat > son, UZ bozorida haqiqiy ehtiyoj.
  - DuckDB — local MVP / dev (default)
  - PostgreSQL — app DB / warehouse (eng ko'p so'raladi)
  - Filesystem — local path, S3, GCS (CSV/Parquet dump)
  - ClickHouse — UZ data engineer stackida tez-tez uchraydi

Boshqa dlt destinationlar (BigQuery, Snowflake, …) keyinroq
mijoz so'raganda qo'shiladi — katalog to'ldirish uchun emas.

`key` qiymatlari dlt.destinations modulidagi nomlar bilan
bir xil — pipeline_runner qo'shimcha mapping qilmaydi.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DestinationSpec(BaseModel):
    key: str
    label: str
    description: str = ""
    needs_connection: bool = False
    connection_placeholder: str = ""
    connection_help: str = ""
    connection_label: str = "Connection / path"


# Maxfiy destination connection uchun secrets_json ichidagi kalit.
# Manifestdagi field emas — ControlStore barcha raw_secrets ni
# shifrlaydi, shu kalit ham shu yerda yashirinadi.
DEST_CONNECTION_SECRET_KEY = "_destination_connection"


DESTINATION_CATALOG: list[DestinationSpec] = [
    DestinationSpec(
        key="duckdb",
        label="DuckDB",
        description="Local analytical DB — MVP default",
        needs_connection=False,
        connection_placeholder="(bo'sh = $UZPIPE_HOME/data/<pipeline>.duckdb)",
        connection_help="Ixtiyoriy. Bo'sh qoldirilsa fayl $UZPIPE_HOME/data/<pipeline_nomi>.duckdb ga yoziladi (loyiha papkasiga emas).",
        connection_label="Fayl yo'li (ixtiyoriy)",
    ),
    DestinationSpec(
        key="postgresql",
        label="PostgreSQL",
        description="Remote Postgres warehouse / app DB",
        needs_connection=True,
        connection_placeholder="postgresql://user:pass@host:5432/dbname",
        connection_help="SQLAlchemy connection string. Parol maxfiy saqlanadi.",
        connection_label="Connection string",
    ),
    DestinationSpec(
        key="filesystem",
        label="Filesystem / S3",
        description="Local papka yoki s3:// / gs:// / az://",
        needs_connection=True,
        connection_placeholder="/tmp/uzpipe_data yoki s3://bucket/prefix",
        connection_help="Local path yoki cloud bucket URL (dlt filesystem).",
        connection_label="Path / bucket URL",
    ),
    DestinationSpec(
        key="clickhouse",
        label="ClickHouse",
        description="OLAP — UZ data stackida keng tarqalgan",
        needs_connection=True,
        connection_placeholder="clickhouse://user:pass@host:8443/default",
        connection_help="ClickHouse HTTP/native URL. Parol maxfiy saqlanadi.",
        connection_label="Connection string",
    ),
]


def all_destinations() -> list[dict[str, Any]]:
    return [d.model_dump() for d in DESTINATION_CATALOG]


def get_destination(key: str) -> DestinationSpec | None:
    for d in DESTINATION_CATALOG:
        if d.key == key:
            return d
    return None


def known_destination_keys() -> set[str]:
    return {d.key for d in DESTINATION_CATALOG}
