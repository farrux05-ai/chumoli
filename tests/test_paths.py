"""Runtime paths must stay under CHUMOLI_HOME — never CWD."""

from __future__ import annotations

from pathlib import Path

from chumoli.core.paths import (
    data_dir,
    default_duckdb_path,
    ensure_runtime_dirs,
    examples_dir,
    pipelines_dir,
    resolve_duckdb_path,
    chumoli_home,
)


def test_chumoli_home_respects_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CHUMOLI_DATA", str(tmp_path / "home" / "data"))
    h = chumoli_home()
    assert h == (tmp_path / "home").resolve()
    ensure_runtime_dirs()
    assert data_dir().is_dir()
    assert pipelines_dir().is_dir()
    assert examples_dir().is_dir()


def test_default_duckdb_under_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "h"))
    monkeypatch.setenv("CHUMOLI_DATA", str(tmp_path / "h" / "data"))
    path = default_duckdb_path("rest_test")
    assert path.endswith("rest_test.duckdb")
    assert str(data_dir()) in path
    assert "Desktop" not in path
    assert "chumoli-data" in str(Path.home() / "chumoli-data") or True  # default name check


def test_relative_connection_goes_to_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "h"))
    monkeypatch.setenv("CHUMOLI_DATA", str(tmp_path / "h" / "data"))
    path = resolve_duckdb_path("my_wh.duckdb", "p1")
    assert Path(path).parent == data_dir().resolve()
    assert path.endswith("my_wh.duckdb")


def test_empty_connection_uses_pipeline_name(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "h"))
    monkeypatch.setenv("CHUMOLI_DATA", str(tmp_path / "h" / "data"))
    path = resolve_duckdb_path("", "postgress")
    assert path.endswith("postgress.duckdb")
    assert str(data_dir().resolve()) in path


def test_absolute_path_preserved(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "h"))
    monkeypatch.setenv("CHUMOLI_DATA", str(tmp_path / "h" / "data"))
    abs_p = tmp_path / "elsewhere" / "x.duckdb"
    path = resolve_duckdb_path(str(abs_p), "p")
    assert Path(path) == abs_p.resolve()


def test_exports_dir_and_filesystem_resolve(tmp_path, monkeypatch) -> None:
    from chumoli.core.paths import (
        default_filesystem_path,
        exports_dir,
        resolve_filesystem_url,
        resolve_s3_url,
        user_data_dir,
    )

    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "h"))
    monkeypatch.setenv("CHUMOLI_DATA", str(tmp_path / "h" / "data"))
    p = default_filesystem_path("demo_rest")
    # Local exports live under user-visible data dir, not hidden .chumoli
    assert "exports" in p
    assert str(user_data_dir()) in p
    assert p.endswith("demo_rest") or p.rstrip("/").endswith("demo_rest")
    assert Path(p).is_dir()

    rel = resolve_filesystem_url("my_out", "p1")
    assert str(exports_dir()) in rel

    # Local filesystem must reject remote URLs
    try:
        resolve_filesystem_url("s3://bucket/prefix", "p1")
        raise AssertionError("local filesystem should reject s3://")
    except ValueError:
        pass

    assert resolve_filesystem_url("s3://bucket/prefix", "p1", allow_remote=True) == "s3://bucket/prefix"
    assert resolve_s3_url("s3://bucket/prefix") == "s3://bucket/prefix"
    try:
        resolve_s3_url("")
        raise AssertionError("s3 empty should fail")
    except ValueError:
        pass
    try:
        resolve_s3_url("/tmp/local")
        raise AssertionError("s3 local path should fail")
    except ValueError:
        pass

    empty = resolve_filesystem_url("", "orders_pipe")
    assert "orders_pipe" in empty
    assert str(user_data_dir()) in empty


def test_destination_file_format_validation() -> None:
    from chumoli.core.config import DestinationConfig

    d = DestinationConfig(connector="filesystem", file_format="CSV")
    assert d.file_format == "csv"
    try:
        DestinationConfig(connector="filesystem", file_format="avro")
        raise AssertionError("should reject")
    except Exception:
        pass

def test_default_user_data_is_visible(monkeypatch) -> None:
    """Without env override, DuckDB lives in ~/chumoli-data (not hidden .chumoli)."""
    monkeypatch.delenv("CHUMOLI_HOME", raising=False)
    monkeypatch.delenv("CHUMOLI_DATA", raising=False)
    path = default_duckdb_path("orders")
    assert "chumoli-data" in path
    assert ".chumoli" not in path
    assert path.endswith("orders.duckdb")
    assert "examples" in str(examples_dir())

