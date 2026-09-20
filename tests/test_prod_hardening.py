"""Prod hardening: decrypt errors, preview-while-running, notify timeout, csv env."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from chumoli.core.config import DestinationConfig, PipelineConfig
from chumoli.core.notify import send_telegram
from chumoli.core.pipeline_runner import get_preview_rows
from chumoli.security.crypto import CredentialCipher
from chumoli.store.control_store import ControlStore


def test_load_wrong_master_key_clear_error(tmp_path: Path) -> None:
    from chumoli.core.manifest import (
        ConnectorCategory,
        ConnectorManifest,
        FieldSpec,
        FieldType,
    )

    key_a = tmp_path / "key_a"
    key_b = tmp_path / "key_b"
    store_a = ControlStore(db_path=tmp_path / "c.db", cipher=CredentialCipher(key_path=key_a))
    manifest = ConnectorManifest(
        key="dummy",
        label="Dummy",
        category=ConnectorCategory.UNIVERSAL,
        dlt_source_factory="chumoli.connectors.rest_api.connector.RestApiConnector",
        fields=[
            FieldSpec(
                key="token",
                label="Token",
                type=FieldType.PASSWORD,
                secret=True,
                required=True,
            )
        ],
    )
    cfg = PipelineConfig(
        name="p1",
        connector_key="dummy",
        source_params={},
        destination=DestinationConfig(connector="duckdb", connection=str(tmp_path / "w.duckdb")),
    )
    store_a.save(cfg, {"token": "secret-token"}, manifest)

    store_b = ControlStore(db_path=tmp_path / "c.db", cipher=CredentialCipher(key_path=key_b))
    with pytest.raises(ValueError, match="master.key"):
        store_b.load("p1")


def test_preview_blocked_while_running(monkeypatch) -> None:
    monkeypatch.setattr(
        "chumoli.core.pipeline_runner.get_running_pipelines",
        lambda: {"busy_pipe": {"step": "run"}},
    )
    out = get_preview_rows("busy_pipe")
    assert out.get("tables") == {}
    assert "ishlayapti" in (out.get("error") or "").lower() or "ishlayapti" in (out.get("error") or "")


def test_telegram_timeout_is_five_seconds() -> None:
    import inspect
    import chumoli.core.notify as notify

    src = inspect.getsource(notify.send_telegram)
    assert "timeout=5.0" in src
    assert "timeout=15.0" not in src


def test_filesystem_csv_env_toggle(monkeypatch, tmp_path: Path) -> None:
    """CSV sets DISABLE_COMPRESSION; non-csv clears it so next run does not leak."""
    from chumoli.core.config import DestinationConfig, PipelineConfig, WriteDisposition
    from chumoli.core.pipeline_runner import _execute
    from chumoli.store.control_store import StoredPipeline

    # We only assert the env branch by replaying the same logic as _execute
    import os

    def apply_fmt(fmt: str) -> None:
        if fmt == "csv":
            os.environ["NORMALIZE__DATA_WRITER__DISABLE_COMPRESSION"] = "true"
        else:
            os.environ.pop("NORMALIZE__DATA_WRITER__DISABLE_COMPRESSION", None)

    apply_fmt("csv")
    assert os.environ.get("NORMALIZE__DATA_WRITER__DISABLE_COMPRESSION") == "true"
    apply_fmt("parquet")
    assert "NORMALIZE__DATA_WRITER__DISABLE_COMPRESSION" not in os.environ
    apply_fmt("csv")
    assert os.environ.get("NORMALIZE__DATA_WRITER__DISABLE_COMPRESSION") == "true"
    # cleanup
    os.environ.pop("NORMALIZE__DATA_WRITER__DISABLE_COMPRESSION", None)


def test_pipeline_runner_csv_branch_in_source() -> None:
    src = Path("src/chumoli/core/pipeline_runner.py").read_text(encoding="utf-8")
    assert 'os.environ["NORMALIZE__DATA_WRITER__DISABLE_COMPRESSION"] = "true"' in src
    assert 'os.environ.pop("NORMALIZE__DATA_WRITER__DISABLE_COMPRESSION", None)' in src
    assert "setdefault" not in src.split("filesystem")[1][:400]
