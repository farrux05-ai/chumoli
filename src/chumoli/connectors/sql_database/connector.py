"""
chumoli.connectors.sql_database.connector
===========================================

dlt'ning tayyor `sql_database` source'i ustidagi yupqa adapterlar.

Strategiya (docs/strategy/chumoli-connector-strategy.md):
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

import json
from typing import Any

from chumoli.core.manifest import ConnectorCategory, ConnectorManifest, FieldSpec, FieldType


# System schemas to skip when scanning (Postgres / MySQL / generic)
_SKIP_SCHEMAS = frozenset(
    {
        "information_schema",
        "pg_catalog",
        "pg_toast",
        "pg_temp_1",
        "pg_toast_temp_1",
        "mysql",
        "performance_schema",
        "sys",
        "sysdiag",
    }
)


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
        # Global fallback (eski UI / CLI). UI endi table_cursors JSON ni afzal ko'radi.
        FieldSpec(
            key="cursor_column",
            label="Vaqt / cursor ustun (ixtiyoriy, barcha jadvallar)",
            type=FieldType.TEXT,
            required=False,
            placeholder="updated_at yoki created_at",
            help_text=(
                "Agar table_cursors bo'sh bo'lsa, barcha jadvallarga shu ustun qo'llanadi. "
                "Bo'sh = har safar to'liq jadval (yoki table_cursors dagi sozlama)."
            ),
        ),
        FieldSpec(
            key="cursor_initial_value",
            label="Qachondan boshlab (ixtiyoriy, global)",
            type=FieldType.TEXT,
            required=False,
            placeholder="2016-05-01 yoki 2016-05-01T00:00:00",
            help_text=(
                "Global boshlang'ich qiymat. table_cursors da alohida berilgan "
                "jadval uchun o'z initial qiymati ustunlik qiladi."
            ),
        ),
        # Per-table cursor map: {"orders":{"column":"updated_at","initial":"2020-01-01"},...}
        # UI JSON string sifatida yuboradi; required emas.
        FieldSpec(
            key="table_cursors",
            label="Jadval cursor sozlamalari (JSON)",
            type=FieldType.TEXT,
            required=False,
            placeholder='{"orders":{"column":"updated_at","initial":"2020-01-01"}}',
            help_text="Har bir jadval uchun alohida cursor ustun va boshlang'ich qiymat",
        ),
    ]


def _preflight_sqlite(credentials: str) -> None:
    """Fail fast with a clear message before dlt/SQLAlchemy stack traces."""
    from pathlib import Path

    from sqlalchemy.engine.url import make_url

    from chumoli.core.demo_data import friendly_db_error

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


def _parse_table_ref(name: str) -> tuple[str | None, str]:
    """'schema.table' → (schema, table); 'table' → (None, table)."""
    name = (name or "").strip()
    if not name:
        return None, ""
    if "." in name:
        schema, table = name.split(".", 1)
        schema, table = schema.strip(), table.strip()
        if schema and table:
            return schema, table
    return None, name


def _parse_table_cursors(raw: Any) -> dict[str, dict[str, Any]]:
    """Parse table_cursors from JSON string or dict."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {str(k): (v if isinstance(v, dict) else {}) for k, v in raw.items()}
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            data = json.loads(s)
        except json.JSONDecodeError:
            return {}
        if isinstance(data, dict):
            return {str(k): (v if isinstance(v, dict) else {}) for k, v in data.items()}
    return {}


def _build_sql_database_source(
    params: dict[str, Any], secrets: dict[str, str]
) -> Any:
    """Barcha SQL connectorlar uchun yagona dlt chaqiruvi.

    incremental faqat sql_table() darajasida mavjud — sql_database()
    uni qabul qilmaydi (dlt 1.30).

    Cursor ustuvorligi (har jadval uchun):
      1) table_cursors[table].column
      2) global cursor_column
      3) yo'q → full load
    """
    table_names = [t.strip() for t in str(params.get("table_names") or "").split(",") if t.strip()]
    if not table_names:
        raise ValueError("Kamida bitta jadval tanlang (table_names)")

    global_cursor = (params.get("cursor_column") or "").strip() or None
    from chumoli.core.cursor_utils import parse_cursor_value

    global_initial = parse_cursor_value(params.get("cursor_initial_value"))
    per_table = _parse_table_cursors(params.get("table_cursors"))
    credentials = secrets["connection_string"]
    _preflight_sqlite(credentials)

    # Resolve per-table cursor plan
    plan: list[tuple[str, str | None, str | None, Any]] = []
    # (table_ref, schema, table, cursor_col, initial)
    needs_cursor_check: list[tuple[str, str]] = []  # (table_ref, cursor_col)

    for tref in table_names:
        schema, table = _parse_table_ref(tref)
        cfg = per_table.get(tref) or per_table.get(table) or {}
        col = (cfg.get("column") or cfg.get("cursor_column") or "").strip() or global_cursor
        init_raw = cfg.get("initial") if "initial" in cfg else cfg.get("cursor_initial_value")
        if init_raw is None or init_raw == "":
            init_val = global_initial if col == global_cursor else None
        else:
            init_val = parse_cursor_value(init_raw)
        if col:
            needs_cursor_check.append((tref, col))
        plan.append((tref, schema, table, col, init_val))

    from dlt.sources.sql_database import sql_database, sql_table

    if not any(p[3] for p in plan):
        # No incremental anywhere — plain sql_database
        # For schema-qualified names, use per-table sql_table without incremental
        if any(p[1] for p in plan):
            import dlt

            @dlt.source(name="sql_database")
            def _plain_schema_source() -> Any:
                resources = []
                for tref, schema, table, _col, _init in plan:
                    kwargs: dict[str, Any] = {
                        "credentials": credentials,
                        "table": table,
                    }
                    if schema:
                        kwargs["schema"] = schema
                    resources.append(sql_table(**kwargs))
                return resources

            return _plain_schema_source()
        return sql_database(credentials=credentials, table_names=table_names)

    from chumoli.core.sql_cursor_check import assert_cursor_columns_exist

    # Group by cursor column for validation (same col on multiple tables OK)
    by_col: dict[str, list[str]] = {}
    for tref, col in needs_cursor_check:
        by_col.setdefault(col, []).append(tref)
    for col, tables in by_col.items():
        # assert accepts bare or schema.table — pass as-is
        assert_cursor_columns_exist(credentials, tables, col)

    import dlt
    from dlt.sources.sql_database import sql_table

    @dlt.source(name="sql_database")
    def _incremental_source() -> Any:
        resources = []
        for tref, schema, table, col, init_val in plan:
            kwargs: dict[str, Any] = {
                "credentials": credentials,
                "table": table,
            }
            if schema:
                kwargs["schema"] = schema
            if col:
                inc_kwargs: dict[str, Any] = {}
                if init_val is not None:
                    inc_kwargs["initial_value"] = init_val
                kwargs["incremental"] = dlt.sources.incremental(col, **inc_kwargs)
            resources.append(sql_table(**kwargs))
        return resources

    return _incremental_source()


# ---------------------------------------------------------------------------
# PostgreSQL — asosiy UZ/app DB kartochkasi
# ---------------------------------------------------------------------------

POSTGRESQL_MANIFEST = ConnectorManifest(
    key="postgresql",
    label="PostgreSQL",
    category=ConnectorCategory.UNIVERSAL,
    description="App DB yoki warehouse → DuckDB / boshqa destination",
    dlt_source_factory="chumoli.connectors.sql_database.connector.PostgreSQLConnector",
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
    dlt_source_factory="chumoli.connectors.sql_database.connector.MySQLConnector",
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
    dlt_source_factory="chumoli.connectors.sql_database.connector.SqlDatabaseConnector",
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
    """Live DB dan barcha schema'lardagi jadval nomlarini qaytaradi.

    - SQLite: oddiy table nomlari
    - PostgreSQL / MySQL: default schema uchun `table`, boshqalar uchun
      `schema.table`. System schema'lar o'tkazib yuboriladi.
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
            dialect = (engine.dialect.name or "").lower()
            tables: list[str] = []

            if dialect == "sqlite":
                tables = sorted(insp.get_table_names())
            else:
                try:
                    schemas = list(insp.get_schema_names())
                except Exception:
                    schemas = []

                default_schema = None
                try:
                    default_schema = insp.default_schema_name
                except Exception:
                    default_schema = None
                if not default_schema:
                    if dialect in ("postgresql", "postgres"):
                        default_schema = "public"
                    elif dialect in ("mysql", "mariadb"):
                        # MySQL: database name is the schema
                        try:
                            from sqlalchemy.engine.url import make_url

                            default_schema = make_url(cred).database
                        except Exception:
                            default_schema = None

                if not schemas:
                    # Fallback: only current schema
                    tables = sorted(insp.get_table_names())
                else:
                    seen: set[str] = set()
                    for schema in sorted(schemas):
                        if not schema or schema.lower() in _SKIP_SCHEMAS:
                            continue
                        # Skip temp schemas
                        if schema.lower().startswith("pg_temp") or schema.lower().startswith(
                            "pg_toast_temp"
                        ):
                            continue
                        try:
                            names = insp.get_table_names(schema=schema)
                        except Exception:
                            continue
                        for t in names:
                            if schema == default_schema or not default_schema:
                                label = t
                            else:
                                label = f"{schema}.{t}"
                            if label not in seen:
                                seen.add(label)
                                tables.append(label)
                    tables = sorted(tables)

        engine.dispose()
    except SQLAlchemyError as e:
        raise ValueError(f"Ulanish yoki schema o'qish xatosi: {e}") from e
    except Exception as e:
        raise ValueError(f"Ulanish yoki schema o'qish xatosi: {e}") from e
    return tables
