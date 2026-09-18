"""
CLI testlari.

Typer'ning `CliRunner` orqali HAQIQIY buyruqlarni ishga tushiradi
(subprocess emas, lekin to'liq argument-parsing va chop etish yo'li
sinaladi). ControlStore/CredentialCipher `monkeypatch` orqali tmp_path
ga yo'naltiriladi — bu haqiqiy foydalanuvchi ~/.uzpipe papkasiga
tegmasligini ta'minlaydi.
"""

from __future__ import annotations

from typer.testing import CliRunner

from uzpipe.cli import app
from uzpipe.core.config import DestinationConfig, PipelineConfig
from uzpipe.security.crypto import CredentialCipher
from uzpipe.store.control_store import ControlStore

runner = CliRunner()


def _patch_store(monkeypatch, tmp_path) -> ControlStore:
    """CLI ichida yaratiladigan ControlStore() tmp_path'ga yo'nalishi uchun.

    cli.py ichida `ControlStore()` argumentsiz chaqiriladi (bu ataylab
    shunday — CLI foydalanuvchisi uchun `~/.uzpipe/` sukut bo'yicha
    ishlashi kerak). Test uchun buni tmp_path'ga almashtiramiz.
    """
    cipher = CredentialCipher(key_path=tmp_path / "key")
    store = ControlStore(db_path=tmp_path / "control.db", cipher=cipher)
    monkeypatch.setattr("uzpipe.cli.ControlStore", lambda: store)
    return store


def test_list_shows_empty_message_when_no_pipelines(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)
    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "hech qanday pipeline saqlanmagan" in result.output


def test_list_shows_saved_pipeline(monkeypatch, tmp_path) -> None:
    store = _patch_store(monkeypatch, tmp_path)

    from uzpipe.connectors import register_builtin_connectors
    from uzpipe.connectors.base import registry

    register_builtin_connectors()
    manifest = registry.get_manifest("rest_api")
    config = PipelineConfig(
        name="mening_pipelinem",
        connector_key="rest_api",
        source_params={"base_url": "https://x.com", "endpoint": "/d", "auth_type": "none"},
        destination=DestinationConfig(connector="duckdb", connection=str(tmp_path / "w.duckdb")),
    )
    store.save(config, raw_secrets={"secret_value": ""}, manifest=manifest)

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "mening_pipelinem" in result.output
    assert "rest_api" in result.output


def test_run_missing_pipeline_exits_with_error(monkeypatch, tmp_path) -> None:
    _patch_store(monkeypatch, tmp_path)
    result = runner.invoke(app, ["run", "does_not_exist"])

    assert result.exit_code == 1
    assert "topilmadi" in result.output


def test_run_existing_pipeline_succeeds(monkeypatch, tmp_path) -> None:
    """CLI orqali to'liq zanjir: forma -> save -> `uzpipe run` -> haqiqiy dlt."""
    store = _patch_store(monkeypatch, tmp_path)

    from uzpipe.connectors import register_builtin_connectors
    from uzpipe.connectors.base import registry

    register_builtin_connectors()
    manifest = registry.get_manifest("sql_database")

    import sqlite3

    src_db = tmp_path / "source.sqlite"
    con = sqlite3.connect(src_db)
    con.execute("CREATE TABLE t (id INTEGER)")
    con.execute("INSERT INTO t VALUES (1)")
    con.commit()
    con.close()

    config = PipelineConfig(
        name="cli_test_pipeline",
        connector_key="sql_database",
        source_params={"table_names": "t", "cursor_column": ""},
        destination=DestinationConfig(
            connector="duckdb", connection=str(tmp_path / "warehouse.duckdb")
        ),
    )
    store.save(
        config,
        raw_secrets={"connection_string": f"sqlite:///{src_db}"},
        manifest=manifest,
    )

    result = runner.invoke(app, ["run", "cli_test_pipeline"])

    assert result.exit_code == 0, result.output
    assert "muvaffaqiyatli" in result.output


def test_run_exits_nonzero_when_quality_check_fails(monkeypatch, tmp_path) -> None:
    """Load succeeds, but a configured quality check fails — CLI must
    still exit non-zero, or a cron/CI caller would treat bad data as
    a clean run (see the note in cli.py's `run` command)."""
    store = _patch_store(monkeypatch, tmp_path)

    from uzpipe.connectors import register_builtin_connectors
    from uzpipe.connectors.base import registry
    from uzpipe.core.config import QualityConfig

    register_builtin_connectors()
    manifest = registry.get_manifest("sql_database")

    import sqlite3

    src_db = tmp_path / "source.sqlite"
    con = sqlite3.connect(src_db)
    con.execute("CREATE TABLE t (id INTEGER)")
    con.execute("INSERT INTO t VALUES (1)")
    con.commit()
    con.close()

    config = PipelineConfig(
        name="quality_failing_pipeline",
        connector_key="sql_database",
        source_params={"table_names": "t", "cursor_column": ""},
        destination=DestinationConfig(
            connector="duckdb", connection=str(tmp_path / "warehouse.duckdb")
        ),
        # Only 1 row exists — requiring 5 forces the quality check to fail.
        quality=QualityConfig(row_count_min=5),
    )
    store.save(
        config,
        raw_secrets={"connection_string": f"sqlite:///{src_db}"},
        manifest=manifest,
    )

    result = runner.invoke(app, ["run", "quality_failing_pipeline"])

    assert result.exit_code == 1
    # Rich may wrap long lines in the captured output, so check for
    # the distinctive word rather than the full phrase verbatim.
    assert "Ogohlantirish" in result.output
    assert "✗" in result.output
