"""filesystem_s3 → DuckDB (lokal JSONL, tarmoq yo'q)."""

from __future__ import annotations

import json

import duckdb

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.core.config import DestinationConfig, PipelineConfig
from chumoli.core.pipeline_runner import _execute
from chumoli.security.crypto import CredentialCipher
from chumoli.store.control_store import ControlStore


def test_full_flow_filesystem_s3_jsonl_to_duckdb(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "home"))
    data_dir = tmp_path / "incoming"
    data_dir.mkdir()
    rows = [
        {"id": 1, "name": "Birinchi"},
        {"id": 2, "name": "Ikkinchi"},
    ]
    (data_dir / "items.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows),
        encoding="utf-8",
    )

    register_builtin_connectors()
    cipher = CredentialCipher(key_path=tmp_path / "key")
    store = ControlStore(db_path=tmp_path / "control.db", cipher=cipher)
    manifest = registry.get_manifest("filesystem_s3")

    form = {
        "path_or_url": str(data_dir),
        "file_format": "jsonl",
        "glob_pattern": "*.jsonl",
    }
    assert manifest.validate_values(form) == []

    duckdb_path = tmp_path / "warehouse.duckdb"
    config = PipelineConfig(
        name="e2e_fs_s3",
        connector_key="filesystem_s3",
        source_params=form,
        destination=DestinationConfig(
            connector="duckdb",
            connection=str(duckdb_path),
            dataset_name="raw",
        ),
    )
    store.save(
        config,
        raw_secrets={"aws_access_key_id": "", "aws_secret_access_key": ""},
        manifest=manifest,
    )
    stored = store.load("e2e_fs_s3")
    assert stored is not None

    result = _execute(stored, registry.get("filesystem_s3"))
    assert result.success, result.load_info
    assert result.new_rows >= 2

    con = duckdb.connect(str(duckdb_path))
    names = {
        t[0]
        for t in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw'"
        ).fetchall()
    }
    assert "files" in names
    got = con.execute("SELECT id, name FROM raw.files ORDER BY id").fetchall()
    con.close()
    assert got == [(1, "Birinchi"), (2, "Ikkinchi")]
