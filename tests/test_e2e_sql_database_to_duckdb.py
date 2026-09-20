"""
sql_database connectori uchun end-to-end test.

rest_api testidan farqli o'laroq, bu yerda MANBA ham SQLite (test
uchun eng oson sozlanadigan haqiqiy SQL baza), NATIJA esa DuckDB.
Bu `sql_database` connectorining bizning manifest/config/encryption
zanjirimiz orqali HAQIQIY ishlashini tasdiqlaydi — nafaqat import
qilinishini.
"""

from __future__ import annotations

import sqlite3

import duckdb
import pytest

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.core.config import DestinationConfig, PipelineConfig
from chumoli.core.pipeline_runner import _execute
from chumoli.security.crypto import CredentialCipher
from chumoli.store.control_store import ControlStore


@pytest.fixture
def source_sqlite_db(tmp_path):
    """Manba sifatida ishlatiladigan, oldindan ma'lumot bilan to'ldirilgan SQLite fayl."""
    db_path = tmp_path / "source.sqlite"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)")
    con.executemany(
        "INSERT INTO customers (id, name) VALUES (?, ?)",
        [(1, "Aziz"), (2, "Dilnoza")],
    )
    con.commit()
    con.close()
    return db_path


def test_full_flow_sql_database_to_duckdb(tmp_path, source_sqlite_db) -> None:
    register_builtin_connectors()
    cipher = CredentialCipher(key_path=tmp_path / "key")
    store = ControlStore(db_path=tmp_path / "control.db", cipher=cipher)
    manifest = registry.get_manifest("sql_database")

    form_values = {
        "table_names": "customers",
        "cursor_column": "",
    }
    # connection_string maxfiy bo'lgani uchun validate_values'ga
    # kiritilmaydi (u raw_secrets orqali alohida uzatiladi) — lekin
    # manifest baribir uni required deb biladi, shuning uchun bu yerda
    # to'liq forma (connection_string bilan) validatsiya qilinadi,
    # xuddi dashboard buni bitta forma sifatida ko'rsatgandek.
    full_form = {**form_values, "connection_string": f"sqlite:///{source_sqlite_db}"}
    errors = manifest.validate_values(full_form)
    assert errors == [], f"Kutilmagan validatsiya xatolari: {errors}"

    duckdb_path = tmp_path / "warehouse.duckdb"
    config = PipelineConfig(
        name="e2e_sql_pipeline",
        connector_key="sql_database",
        source_params={"table_names": "customers", "cursor_column": ""},
        destination=DestinationConfig(
            connector="duckdb",
            connection=str(duckdb_path),
            dataset_name="raw",
        ),
    )

    store.save(
        config,
        raw_secrets={"connection_string": f"sqlite:///{source_sqlite_db}"},
        manifest=manifest,
    )

    stored = store.load("e2e_sql_pipeline")
    assert stored is not None

    connector = registry.get("sql_database")
    result = _execute(stored, connector)

    assert result.success, f"Pipeline muvaffaqiyatsiz tugadi: {result.load_info}"

    con = duckdb.connect(str(duckdb_path))
    rows = con.execute("SELECT id, name FROM raw.customers ORDER BY id").fetchall()
    con.close()

    assert rows == [(1, "Aziz"), (2, "Dilnoza")]
