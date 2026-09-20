"""B.1 — reusable named destinations (encrypted connection)."""

from __future__ import annotations

import sqlite3

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.core.config import DestinationConfig, PipelineConfig
from chumoli.core.destinations import DEST_CONNECTION_SECRET_KEY
from chumoli.security.crypto import CredentialCipher
from chumoli.store.control_store import ControlStore


def test_saved_destination_round_trip_encrypted(tmp_path) -> None:
    cipher = CredentialCipher(key_path=tmp_path / "k")
    store = ControlStore(db_path=tmp_path / "c.db", cipher=cipher)

    dest_id = store.save_destination(
        label="Prod PG",
        connector="postgresql",
        connection="postgresql://u:secretpass@db:5432/app",
        dataset_name="warehouse",
    )
    assert dest_id

    listed = store.list_saved_destinations()
    assert len(listed) == 1
    assert listed[0]["label"] == "Prod PG"
    assert listed[0]["connector"] == "postgresql"
    assert "connection" not in listed[0]  # list never exposes secret

    full = store.get_saved_destination(dest_id)
    assert full is not None
    assert full["connection"] == "postgresql://u:secretpass@db:5432/app"
    assert full["dataset_name"] == "warehouse"

    # raw SQLite must not contain plaintext password
    con = sqlite3.connect(tmp_path / "c.db")
    row = con.execute(
        "SELECT connection_enc FROM saved_destinations WHERE id=?", (dest_id,)
    ).fetchone()
    con.close()
    assert row is not None
    assert "secretpass" not in (row[0] or "")


def test_delete_saved_destination(tmp_path) -> None:
    cipher = CredentialCipher(key_path=tmp_path / "k")
    store = ControlStore(db_path=tmp_path / "c.db", cipher=cipher)
    dest_id = store.save_destination(
        label="Tmp",
        connector="duckdb",
        connection=None,
        dataset_name="raw",
    )
    assert store.delete_saved_destination(dest_id) is True
    assert store.get_saved_destination(dest_id) is None
    assert store.delete_saved_destination(dest_id) is False


def test_pipeline_uses_saved_destination(tmp_path) -> None:
    register_builtin_connectors()
    cipher = CredentialCipher(key_path=tmp_path / "k")
    store = ControlStore(db_path=tmp_path / "c.db", cipher=cipher)
    dest_id = store.save_destination(
        label="Local Duck",
        connector="duckdb",
        connection=str(tmp_path / "from_saved.duckdb"),
        dataset_name="ds1",
    )
    saved = store.get_saved_destination(dest_id)
    assert saved is not None

    manifest = registry.get_manifest("synthetic_volume")
    config = PipelineConfig(
        name="from_saved",
        connector_key="synthetic_volume",
        source_params={"row_count": "2", "batch_label": "x"},
        destination=DestinationConfig(
            connector=saved["connector"],
            connection=saved["connection"],
            dataset_name=saved["dataset_name"],
        ),
    )
    store.save(
        config,
        raw_secrets={DEST_CONNECTION_SECRET_KEY: saved["connection"]},
        manifest=manifest,
    )
    loaded = store.load("from_saved")
    assert loaded is not None
    assert loaded.config.destination.connection == str(tmp_path / "from_saved.duckdb")
    assert loaded.config.destination.dataset_name == "ds1"
