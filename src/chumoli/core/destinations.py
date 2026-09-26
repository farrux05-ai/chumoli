"""
chumoli.core.destinations
==========================

dlt built-in destinationlarning UI/API katalogi.

NEGA FAQAT SHU TO'RTALIK (BigQuery/Snowflake yo'q)
----------------------------------------------------
Strategiya: sifat > son, UZ bozorida haqiqiy ehtiyoj.
  - DuckDB — local MVP / dev (default)
  - PostgreSQL — app DB / warehouse (eng ko'p so'raladi)
  - Filesystem — faqat lokal papka (CSV/Parquet) — foydalanuvchi ko'radigan joy
  - S3 / object storage — s3:// gs:// az:// (alohida katalog)
  - ClickHouse — UZ data engineer stackida tez-tez uchraydi
    (ixtiyoriy extra: pip install "dlt[clickhouse]")

Boshqa dlt destinationlar (BigQuery, Snowflake, …) keyinroq
mijoz so'raganda qo'shiladi — katalog to'ldirish uchun emas.

`key` — UI/katalog nomi. dlt moduli bilan farq qilsa
(masalan postgresql → postgres) pipeline_runner._DLT_DEST_ALIASES
orqali map qilinadi. Catalog key o'zgarmaydi (saqlangan pipeline'lar
va testlar uchun barqaror).

`filesystem` va `s3` ikkalasi ham dlt.destinations.filesystem ga map
qilinadi; farq — UI va default path / credentials.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import BaseModel


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

# Catalog keys that use dlt.destinations.filesystem under the hood.
FILESYSTEM_DEST_KEYS = frozenset({"filesystem", "s3"})


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
    attr = {
        "postgresql": "postgres",
        "s3": "filesystem",  # object storage uses same dlt destination
    }.get(key, key)
    if key in ("duckdb", "filesystem", "postgresql", "s3"):
        # Core MVP destinations — always listed; runtime will surface real errors
        return True
    return _probe_dlt_destination(attr)


DESTINATION_CATALOG: list[DestinationSpec] = [
    DestinationSpec(
        key="duckdb",
        label="DuckDB",
        description="Local analytical DB — MVP default",
        needs_connection=False,
        connection_placeholder="(bo'sh = ~/chumoli-data/<pipeline>.duckdb)",
        connection_help="Ixtiyoriy. Bo'sh qoldirilsa fayl ~/chumoli-data/<pipeline_nomi>.duckdb ga yoziladi.",
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
        label="Lokal fayl (CSV / Parquet)",
        description="Lokal papka — «Tanlash» bilan ochiladi yoki bo'sh = standart exports.",
        needs_connection=False,
        connection_placeholder="Bo'sh = ~/chumoli-data/exports/<pipeline>/",
        connection_help="«Tanlash» tugmasi kompyuterdan papka ochadi. Bo'sh qoldirsangiz standart papka ishlatiladi.",
        connection_label="Lokal papka",
    ),
    DestinationSpec(
        key="s3",
        label="S3 / Object storage",
        description="s3:// gs:// az:// — bulutli object storage (CSV/Parquet)",
        needs_connection=True,
        connection_placeholder="s3://bucket/prefix  yoki  gs://bucket/prefix",
        connection_help=(
            "Majburiy. s3://, gs://, gcs://, az://, abfss:// yoki hf://. "
            "Credentials muhit o'zgaruvchilari yoki AWS/GCP default chain orqali."
        ),
        connection_label="Bucket URL",
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


def is_filesystem_like(key: str) -> bool:
    """True for local filesystem or object-storage (s3) catalog keys."""
    return key in FILESYSTEM_DEST_KEYS
