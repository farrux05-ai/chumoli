"""
chumoli.core.destinations
==========================

dlt built-in destinationlarning UI/API katalogi.

NEGA FAQAT SHU TO'RTALIK (BigQuery/Snowflake yo'q)
----------------------------------------------------
Strategiya: sifat > son, UZ bozorida haqiqiy ehtiyoj.
  - DuckDB — local MVP / dev (default)
  - PostgreSQL — app DB / warehouse (eng ko'p so'raladi)
  - Filesystem — local path, S3, GCS (CSV/Parquet dump)
  - ClickHouse — UZ data engineer stackida tez-tez uchraydi
    (ixtiyoriy extra: pip install "dlt[clickhouse]")

Boshqa dlt destinationlar (BigQuery, Snowflake, …) keyinroq
mijoz so'raganda qo'shiladi — katalog to'ldirish uchun emas.

`key` — UI/katalog nomi. dlt moduli bilan farq qilsa
(masalan postgresql → postgres) pipeline_runner._DLT_DEST_ALIASES
orqali map qilinadi. Catalog key o'zgarmaydi (saqlangan pipeline'lar
va testlar uchun barqaror).
"""

from __future__ import annotations

from functools import lru_cache
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
    # Optional dlt extra, e.g. "clickhouse" → pip install "dlt[clickhouse]"
    dlt_extra: str | None = None
    available: bool = True


# Maxfiy destination connection uchun secrets_json ichidagi kalit.
# Manifestdagi field emas — ControlStore barcha raw_secrets ni
# shifrlaydi, shu kalit ham shu yerda yashirinadi.
DEST_CONNECTION_SECRET_KEY = "_destination_connection"


def _probe_dlt_destination(attr: str) -> bool:
    """Return True if dlt.destinations.<attr> is importable without extra install error."""
    try:
        import dlt

        getattr(dlt.destinations, attr)
        return True
    except Exception:
        return False


@lru_cache(maxsize=8)
def is_destination_available(key: str) -> bool:
    """Whether the dlt backend for this catalog key is installed."""
    # Catalog key → attribute on dlt.destinations
    attr = {"postgresql": "postgres"}.get(key, key)
    if key in ("duckdb", "filesystem", "postgresql"):
        # Core MVP destinations — always listed; runtime will surface real errors
        return True
    return _probe_dlt_destination(attr)


DESTINATION_CATALOG: list[DestinationSpec] = [
    DestinationSpec(
        key="duckdb",
        label="DuckDB",
        description="Local analytical DB — MVP default",
        needs_connection=False,
        connection_placeholder="(bo'sh = $CHUMOLI_HOME/data/<pipeline>.duckdb)",
        connection_help="Ixtiyoriy. Bo'sh qoldirilsa fayl $CHUMOLI_HOME/data/<pipeline_nomi>.duckdb ga yoziladi (loyiha papkasiga emas).",
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
        label="Fayl (CSV / Parquet)",
        description="Lokal papka yoki s3:// — CSV (Excel) yoki Parquet",
        needs_connection=False,
        connection_placeholder="Bo'sh = ~/.chumoli/exports/<pipeline>/  yoki  s3://bucket/prefix",
        connection_help="Ixtiyoriy. Bo'sh qoldirilsa $CHUMOLI_HOME/exports/<pipeline>/ ga yoziladi. S3/GCS ham mumkin.",
        connection_label="Papka yoki bucket URL",
    ),
    DestinationSpec(
        key="clickhouse",
        label="ClickHouse",
        description="OLAP — UZ data stackida keng tarqalgan",
        needs_connection=True,
        connection_placeholder="clickhouse://user:pass@host:8443/default",
        connection_help="ClickHouse HTTP/native URL. Parol maxfiy saqlanadi. Kerak: pip install \"dlt[clickhouse]\"",
        connection_label="Connection string",
        dlt_extra="clickhouse",
    ),
]


def all_destinations() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for d in DESTINATION_CATALOG:
        item = d.model_dump()
        avail = is_destination_available(d.key)
        item["available"] = avail
        if d.dlt_extra and not avail:
            item["description"] = (
                f"{d.description} — o'rnatilmagan (pip install \"dlt[{d.dlt_extra}]\")"
            )
        out.append(item)
    return out


def get_destination(key: str) -> DestinationSpec | None:
    for d in DESTINATION_CATALOG:
        if d.key == key:
            return d
    return None


def known_destination_keys() -> set[str]:
    return {d.key for d in DESTINATION_CATALOG}
