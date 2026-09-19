"""
uzpipe.connectors.sql_database.connector
===========================================

dlt'ning tayyor `sql_database` source'i ustidagi yupqa adapterlar.

Strategiya (docs/strategy/uzpipe-connector-strategy.md):
  - Ichki dlt source bir xil: `sql_database`
  - Foydalanuvchi UI da alohida kartochkalar ko'radi:
      PostgreSQL, MySQL, SQL Database (generic)
  - Bu "sifat > son" va "user-facing names" qoidalariga mos.

NEGA UCHTA ALOHIDA MANIFEST, BITTA build MANTIG'I
----------------------------------------------------
PostgreSQL va MySQL uchun placeholder, help matni va label farq
qiladi — forma tajribasi yaxshilanadi. Lekin `build_dlt_source`
100% bir xil (SQLAlchemy connection string). Shuning uchun
umumiy `_build_sql_database_source` yordamchi funksiyasi bor;
har bir connector klassi faqat o'z `manifest`ini olib yuradi.

Generic `sql_database` SQLite / MSSQL / Oracle va testlar uchun
qoldirilgan — katalogni "to'ldirish" uchun emas, balki haqiqiy
ehtiyoj (masalan lokal SQLite dump) uchun.
"""

from __future__ import annotations

from typing import Any

from dlt.sources.sql_database import sql_database, sql_table

from uzpipe.core.manifest import ConnectorCategory, ConnectorManifest, FieldSpec, FieldType


def _sql_fields(
    *,
    connection_placeholder: str,
    connection_help: str,
) -> list[FieldSpec]:
    return [
        FieldSpec(
            key="connection_string",
            label="Connection string",
            type=FieldType.PASSWORD,
            required=True,
            secret=True,
            placeholder=connection_placeholder,
            help_text=connection_help,
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
    ]


def _preflight_sqlite(credentials: str) -> None:
    """Fail fast with a clear message before dlt/SQLAlchemy stack traces."""
    from pathlib import Path

    from sqlalchemy.engine.url import make_url

    from uzpipe.core.demo_data import friendly_db_error

    cred = (credentials or "").strip()
    if not cred.lower().startswith("sqlite"):
        return
    try:
        url = make_url(cred)
        db_path = url.database
    except Exception:
        return
    if not db_path or db_path == ":memory:":
        return
    path = Path(db_path)
    if not path.is_file():
        raise ValueError(
            friendly_db_error(Exception(f"unable to open database file: {path}"))
        )


def _build_sql_database_source(
    params: dict[str, Any], secrets: dict[str, str]
) -> Any:
    """Barcha SQL connectorlar uchun yagona dlt chaqiruvi.

    incremental faqat sql_table() darajasida mavjud — sql_database()
    uni qabul qilmaydi (dlt 1.30). cursor_column bo'sh bo'lsa oddiy
    sql_database; to'ldirilsa har jadval uchun alohida sql_table +
    incremental() yig'iladi.
    """
    table_names = [t.strip() for t in params["table_names"].split(",") if t.strip()]
    cursor_column = params.get("cursor_column") or None
    credentials = secrets["connection_string"]
    _preflight_sqlite(credentials)

    if not cursor_column:
        return sql_database(credentials=credentials, table_names=table_names)

    import dlt

    # Har bir jadvalga ALOHIDA incremental() obyekti — bitta obyektni
    # bir nechta resource orasida ulashish holatni chalkashtirishi mumkin.
    @dlt.source(name="sql_database")
    def _incremental_source() -> Any:
        return [
            sql_table(
                credentials=credentials,
                table=t,
                incremental=dlt.sources.incremental(cursor_column),
            )
            for t in table_names
        ]

    return _incremental_source()


# ---------------------------------------------------------------------------
# PostgreSQL — asosiy UZ/app DB kartochkasi
# ---------------------------------------------------------------------------

POSTGRESQL_MANIFEST = ConnectorManifest(
    key="postgresql",
    label="PostgreSQL",
    category=ConnectorCategory.UNIVERSAL,
    description="App DB yoki warehouse → DuckDB / boshqa destination",
    dlt_source_factory="uzpipe.connectors.sql_database.connector.PostgreSQLConnector",
    fields=_sql_fields(
        connection_placeholder="postgresql://user:pass@host:5432/dbname",
        connection_help=(
            "SQLAlchemy format. Parol connection string ichida — "
            "maxfiy saqlanadi (Fernet)."
        ),
    ),
)


class PostgreSQLConnector:
    """PostgreSQL uchun thin adapter (dlt sql_database)."""

    manifest = POSTGRESQL_MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        return _build_sql_database_source(params, secrets)


# ---------------------------------------------------------------------------
# MySQL / MariaDB
# ---------------------------------------------------------------------------

MYSQL_MANIFEST = ConnectorManifest(
    key="mysql",
    label="MySQL",
    category=ConnectorCategory.UNIVERSAL,
    description="MySQL yoki MariaDB (SQLAlchemy / pymysql)",
    dlt_source_factory="uzpipe.connectors.sql_database.connector.MySQLConnector",
    fields=_sql_fields(
        connection_placeholder="mysql+pymysql://user:pass@host:3306/dbname",
        connection_help=(
            "MySQL uchun odatda mysql+pymysql:// ... format ishlatiladi. "
            "Parol maxfiy saqlanadi."
        ),
    ),
)


class MySQLConnector:
    """MySQL / MariaDB uchun thin adapter (dlt sql_database)."""

    manifest = MYSQL_MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        return _build_sql_database_source(params, secrets)


# ---------------------------------------------------------------------------
# Generic SQL Database — SQLite, MSSQL, Oracle va testlar
# ---------------------------------------------------------------------------

SQL_DATABASE_MANIFEST = ConnectorManifest(
    key="sql_database",
    label="SQL Database",
    category=ConnectorCategory.UNIVERSAL,
    description="SQLite, MSSQL, Oracle va boshqa SQLAlchemy URL'lar",
    dlt_source_factory="uzpipe.connectors.sql_database.connector.SqlDatabaseConnector",
    fields=_sql_fields(
        connection_placeholder="sqlite:////home/user/data/orders.db",
        connection_help=(
            "SQLite: to'liq yo'l (sqlite:////abs/path.db). "
            "Relative path ishonchsiz. Yoki Settings → Namuna SQL. "
            "PostgreSQL/MySQL uchun alohida kartochkalarni afzal ko'ring."
        ),
    ),
)


class SqlDatabaseConnector:
    """Generic SQL adapter — testlar va kam uchraydigan dialectlar uchun."""

    manifest = SQL_DATABASE_MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        return _build_sql_database_source(params, secrets)


# Orqa-moslik: eski importlar MANIFEST ni kutishi mumkin
MANIFEST = SQL_DATABASE_MANIFEST


def inspect_sql_tables(connection_string: str) -> list[str]:
    """Live DB dan jadval nomlarini qaytaradi (SQLAlchemy inspect).

    Faqat table-level — column-level keyinroq (YAGNI).
    Ulanish xatosida ValueError (o'zbekcha) ko'tariladi.
    """
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.exc import SQLAlchemyError

    cred = (connection_string or "").strip()
    if not cred:
        raise ValueError("Connection string bo'sh")

    _preflight_sqlite(cred)

    try:
        engine = create_engine(cred)
        with engine.connect() as conn:
            insp = inspect(conn)
            tables = sorted(insp.get_table_names())
        engine.dispose()
    except SQLAlchemyError as e:
        raise ValueError(f"Ulanish yoki schema o'qish xatosi: {e}") from e
    except Exception as e:
        raise ValueError(f"Ulanish yoki schema o'qish xatosi: {e}") from e
    return tables
