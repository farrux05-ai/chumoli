"""uzpipe.store.control_store — pipeline configs + encrypted secrets + settings."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from uzpipe.core.config import PipelineConfig
from uzpipe.core.manifest import ConnectorManifest
from uzpipe.security.crypto import CredentialCipher

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipelines (
    name TEXT PRIMARY KEY,
    connector_key TEXT NOT NULL,
    config_json TEXT NOT NULL,
    secrets_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS saved_destinations (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    connector TEXT NOT NULL,
    connection_enc TEXT,
    dataset_name TEXT NOT NULL DEFAULT 'raw',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@dataclass
class StoredPipeline:
    config: PipelineConfig
    secrets: dict[str, str]


class ControlStore:
    def __init__(self, db_path: Path | None = None, cipher: CredentialCipher | None = None) -> None:
        self._db_path = db_path or self._default_db_path()
        self._cipher = cipher or CredentialCipher()
        self._init_schema()

    @staticmethod
    def _default_db_path() -> Path:
        from uzpipe.core.paths import ensure_runtime_dirs, uzpipe_home
        ensure_runtime_dirs()
        return uzpipe_home() / "uzpipe_control.db"

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def save(
        self,
        config: PipelineConfig,
        raw_secrets: dict[str, str],
        manifest: ConnectorManifest,
    ) -> None:
        from uzpipe.core.destinations import DEST_CONNECTION_SECRET_KEY

        secret_keys = set(manifest.secret_keys())
        leaked = secret_keys & set(config.source_params.keys())
        if leaked:
            raise ValueError(
                f"Maxfiy maydonlar source_params ichida topildi: {leaked}. "
                "Bu maydonlar faqat raw_secrets orqali uzatilishi kerak."
            )

        # Destination connection is also a secret
        extra_secret_keys = set(secret_keys)
        if DEST_CONNECTION_SECRET_KEY in raw_secrets:
            extra_secret_keys.add(DEST_CONNECTION_SECRET_KEY)

        missing = secret_keys - set(raw_secrets.keys())
        if missing:
            raise ValueError(f"Quyidagi maxfiy maydonlar yetishmayapti: {missing}")

        to_encrypt = {k: v for k, v in raw_secrets.items() if k in extra_secret_keys}
        encrypted_secrets = self._cipher.encrypt_dict(to_encrypt)

        storable = config.model_copy(deep=True)
        if storable.destination.connection:
            # never persist plaintext connection in config_json
            storable.destination.connection = None

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pipelines (name, connector_key, config_json, secrets_json)
                VALUES (:name, :connector_key, :config_json, :secrets_json)
                ON CONFLICT(name) DO UPDATE SET
                    connector_key = excluded.connector_key,
                    config_json = excluded.config_json,
                    secrets_json = excluded.secrets_json,
                    updated_at = datetime('now')
                """,
                {
                    "name": config.name,
                    "connector_key": config.connector_key,
                    "config_json": json.dumps(storable.to_storable_dict()),
                    "secrets_json": json.dumps(encrypted_secrets),
                },
            )

    def load(self, name: str) -> StoredPipeline | None:
        from uzpipe.core.destinations import DEST_CONNECTION_SECRET_KEY

        with self._connect() as conn:
            row = conn.execute(
                "SELECT config_json, secrets_json FROM pipelines WHERE name = ?",
                (name,),
            ).fetchone()

        if row is None:
            return None

        config = PipelineConfig.model_validate(json.loads(row["config_json"]))
        encrypted_secrets: dict[str, str] = json.loads(row["secrets_json"])
        secrets = self._cipher.decrypt_dict(encrypted_secrets)
        dest_conn = secrets.get(DEST_CONNECTION_SECRET_KEY)
        if dest_conn:
            config.destination.connection = dest_conn
        return StoredPipeline(config=config, secrets=secrets)

    def list_all(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, connector_key, config_json, created_at, updated_at "
                "FROM pipelines ORDER BY updated_at DESC"
            ).fetchall()
        return [
            {
                "name": r["name"],
                "connector_key": r["connector_key"],
                "config": json.loads(r["config_json"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def delete(self, name: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM pipelines WHERE name = ?", (name,))

    def get_setting(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return str(row["value"]) if row else None

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def get_secret_setting(self, key: str) -> str | None:
        raw = self.get_setting(key)
        if not raw:
            return None
        try:
            return self._cipher.decrypt(raw)
        except Exception:
            return raw

    def set_secret_setting(self, key: str, value: str) -> None:
        self.set_setting(key, self._cipher.encrypt(value))

    # ------------------------------------------------------------------
    # Saved destinations (reusable named configs — Fivetran-style)
    # ------------------------------------------------------------------

    def list_saved_destinations(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, label, connector, dataset_name, created_at, updated_at "
                "FROM saved_destinations ORDER BY label COLLATE NOCASE"
            ).fetchall()
        return [
            {
                "id": r["id"],
                "label": r["label"],
                "connector": r["connector"],
                "dataset_name": r["dataset_name"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def get_saved_destination(self, dest_id: str) -> dict[str, Any] | None:
        """Return full saved dest including decrypted connection (for pipeline create)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, label, connector, connection_enc, dataset_name, "
                "created_at, updated_at FROM saved_destinations WHERE id = ?",
                (dest_id,),
            ).fetchone()
        if row is None:
            return None
        connection: str | None = None
        if row["connection_enc"]:
            try:
                connection = self._cipher.decrypt(row["connection_enc"])
            except Exception:
                connection = None
        return {
            "id": row["id"],
            "label": row["label"],
            "connector": row["connector"],
            "connection": connection,
            "dataset_name": row["dataset_name"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def save_destination(
        self,
        *,
        label: str,
        connector: str,
        connection: str | None = None,
        dataset_name: str = "raw",
        dest_id: str | None = None,
    ) -> str:
        """Insert or update a named destination. Returns id."""
        import uuid

        label = (label or "").strip()
        if not label:
            raise ValueError("Destination label majburiy")
        connector = (connector or "").strip()
        if not connector:
            raise ValueError("Destination connector majburiy")

        dest_id = dest_id or str(uuid.uuid4())
        enc = self._cipher.encrypt(connection) if connection else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO saved_destinations
                    (id, label, connector, connection_enc, dataset_name)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    label = excluded.label,
                    connector = excluded.connector,
                    connection_enc = excluded.connection_enc,
                    dataset_name = excluded.dataset_name,
                    updated_at = datetime('now')
                """,
                (dest_id, label, connector, enc, dataset_name or "raw"),
            )
        return dest_id

    def delete_saved_destination(self, dest_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM saved_destinations WHERE id = ?", (dest_id,)
            )
            return cur.rowcount > 0
