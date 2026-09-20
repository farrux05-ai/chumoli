"""Validate SQL cursor columns before building incremental sources."""

from __future__ import annotations

from typing import Any


def _split_table_ref(name: str) -> tuple[str | None, str]:
    name = (name or "").strip()
    if "." in name:
        schema, table = name.split(".", 1)
        schema, table = schema.strip(), table.strip()
        if schema and table:
            return schema, table
    return None, name


def assert_cursor_columns_exist(
    credentials: str, table_names: list[str], cursor_column: str
) -> None:
    """Fail fast if cursor_column missing on any selected table.

    table_names may be bare (`orders`) or schema-qualified (`sales.orders`).
    Uses SQLAlchemy when available; for sqlite:// falls back to stdlib.
    """
    cred = (credentials or "").strip()
    if cred.startswith("sqlite:///"):
        _assert_sqlite(cred, table_names, cursor_column)
        return
    try:
        from sqlalchemy import create_engine, inspect
        from sqlalchemy.exc import SQLAlchemyError
    except ImportError as e:
        raise ValueError(
            "SQLAlchemy kerak (cursor ustunni tekshirish uchun). pip install sqlalchemy"
        ) from e

    engine = create_engine(cred)
    try:
        insp = inspect(engine)
        missing: list[str] = []
        for table_ref in table_names:
            schema, table = _split_table_ref(table_ref)
            try:
                if schema:
                    cols = {c["name"] for c in insp.get_columns(table, schema=schema)}
                else:
                    cols = {c["name"] for c in insp.get_columns(table)}
            except Exception:
                continue
            if cursor_column not in cols:
                missing.append(table_ref)
        if missing:
            raise ValueError(
                f"cursor_column '{cursor_column}' quyidagi jadvallarda topilmadi: "
                f"{', '.join(missing)}. Bo'sh qoldiring yoki to'g'ri ustun kiriting."
            )
    except ValueError:
        raise
    except SQLAlchemyError as e:
        raise ValueError(f"Ustunlarni tekshirishda xato: {e}") from e
    finally:
        engine.dispose()


def _assert_sqlite(
    credentials: str, table_names: list[str], cursor_column: str
) -> None:
    import sqlite3
    from pathlib import Path

    # sqlite:////abs/path or sqlite:///rel
    path = credentials.replace("sqlite:///", "", 1)
    if path.startswith("/") and credentials.startswith("sqlite:////"):
        path = "/" + path.lstrip("/")
    while credentials.startswith("sqlite:////"):
        path = credentials[len("sqlite:///") :]  # keeps one /
        break
    else:
        path = credentials[len("sqlite:///") :]

    db_path = Path(path)
    if not db_path.is_file():
        return  # let later stages fail with clear message

    conn = sqlite3.connect(str(db_path))
    try:
        missing: list[str] = []
        for table_ref in table_names:
            _schema, table = _split_table_ref(table_ref)
            cur = conn.execute(f'PRAGMA table_info("{table}")')
            cols = {row[1] for row in cur.fetchall()}
            if not cols:
                continue
            if cursor_column not in cols:
                missing.append(table_ref)
        if missing:
            raise ValueError(
                f"cursor_column '{cursor_column}' quyidagi jadvallarda topilmadi: "
                f"{', '.join(missing)}. Bo'sh qoldiring yoki to'g'ri ustun kiriting."
            )
    finally:
        conn.close()
