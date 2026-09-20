"""B.2 — schema scan for sql_database (table names only)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from chumoli.connectors.sql_database.connector import inspect_sql_tables


def _make_sqlite(path: Path) -> str:
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE orders (id INTEGER, amount REAL)"))
        conn.execute(text("CREATE TABLE customers (id INTEGER, name TEXT)"))
        conn.execute(text("CREATE TABLE _skip_me (x INTEGER)"))  # still listed — we don't filter
    eng.dispose()
    return f"sqlite:///{path}"


def test_inspect_sql_tables_returns_real_names(tmp_path) -> None:
    url = _make_sqlite(tmp_path / "src.db")
    tables = inspect_sql_tables(url)
    assert "orders" in tables
    assert "customers" in tables
    assert tables == sorted(tables)


def test_inspect_sql_tables_empty_string_raises() -> None:
    with pytest.raises(ValueError, match="bo'sh"):
        inspect_sql_tables("")


def test_inspect_sql_tables_missing_file_raises(tmp_path) -> None:
    missing = tmp_path / "nope.db"
    with pytest.raises(ValueError):
        inspect_sql_tables(f"sqlite:///{missing}")
