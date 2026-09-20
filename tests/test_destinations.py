"""Destination katalogi va connection shifrlash."""

from __future__ import annotations

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.core.config import DestinationConfig, PipelineConfig
from chumoli.core.destinations import (
    DEST_CONNECTION_SECRET_KEY,
    all_destinations,
    get_destination,
)
from chumoli.security.crypto import CredentialCipher
from chumoli.store.control_store import ControlStore


def test_catalog_has_mvp_destinations() -> None:
    keys = {d["key"] for d in all_destinations()}
    assert keys >= {"duckdb", "postgresql", "filesystem", "clickhouse"}
    pg = get_destination("postgresql")
    assert pg is not None
    assert pg.needs_connection is True
    duck = get_destination("duckdb")
    assert duck is not None
    assert duck.needs_connection is False


def test_destination_connection_encrypted_not_in_config_json(tmp_path) -> None:
    register_builtin_connectors()
    cipher = CredentialCipher(key_path=tmp_path / "key")
    store = ControlStore(db_path=tmp_path / "control.db", cipher=cipher)
    manifest = registry.get_manifest("rest_api")

    config = PipelineConfig(
        name="dest_sec",
        connector_key="rest_api",
        source_params={
            "base_url": "https://example.com",
            "endpoint": "/x",
            "auth_type": "none",
        },
        destination=DestinationConfig(
            connector="postgresql",
            connection="postgresql://u:secretpass@host/db",
            dataset_name="raw",
        ),
    )
    store.save(
        config,
        raw_secrets={"secret_value": "", DEST_CONNECTION_SECRET_KEY: "postgresql://u:secretpass@host/db"},
        manifest=manifest,
    )

    # Diskdagi config_json da parol bo'lmasligi kerak
    import json
    import sqlite3

    con = sqlite3.connect(tmp_path / "control.db")
    row = con.execute("SELECT config_json, secrets_json FROM pipelines WHERE name='dest_sec'").fetchone()
    con.close()
    config_json, secrets_json = row
    assert "secretpass" not in config_json
    assert "secretpass" not in secrets_json  # shifrlangan

    loaded = store.load("dest_sec")
    assert loaded is not None
    assert loaded.config.destination.connection == "postgresql://u:secretpass@host/db"
