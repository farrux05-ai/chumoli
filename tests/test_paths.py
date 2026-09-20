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
    h = chumoli_home()
    assert h == (tmp_path / "home").resolve()
    ensure_runtime_dirs()
    assert data_dir().is_dir()
    assert pipelines_dir().is_dir()
    assert examples_dir().is_dir()


def test_default_duckdb_under_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "h"))
    path = default_duckdb_path("rest_test")
    assert path.endswith("rest_test.duckdb")
    assert str(data_dir()) in path
    assert "Desktop" not in path


def test_relative_connection_goes_to_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "h"))
    path = resolve_duckdb_path("my_wh.duckdb", "p1")
    assert Path(path).parent == data_dir().resolve()
    assert path.endswith("my_wh.duckdb")


def test_empty_connection_uses_pipeline_name(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "h"))
    path = resolve_duckdb_path("", "postgress")
    assert path.endswith("postgress.duckdb")
    assert str(data_dir().resolve()) in path


def test_absolute_path_preserved(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "h"))
    abs_p = tmp_path / "elsewhere" / "x.duckdb"
    path = resolve_duckdb_path(str(abs_p), "p")
    assert Path(path) == abs_p.resolve()


def test_exports_dir_and_filesystem_resolve(tmp_path, monkeypatch) -> None:
    from chumoli.core.paths import (
        default_filesystem_path,
        exports_dir,
        resolve_filesystem_url,
    )

    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "h"))
    p = default_filesystem_path("demo_rest")
    assert "exports" in p
    assert p.endswith("demo_rest") or p.rstrip("/").endswith("demo_rest")
    assert Path(p).is_dir()

    rel = resolve_filesystem_url("my_out", "p1")
    assert str(exports_dir()) in rel

    s3 = resolve_filesystem_url("s3://bucket/prefix", "p1")
    assert s3 == "s3://bucket/prefix"

    empty = resolve_filesystem_url("", "orders_pipe")
    assert "orders_pipe" in empty


def test_destination_file_format_validation() -> None:
    from chumoli.core.config import DestinationConfig

    d = DestinationConfig(connector="filesystem", file_format="CSV")
    assert d.file_format == "csv"
    try:
        DestinationConfig(connector="filesystem", file_format="avro")
        raise AssertionError("should reject")
    except Exception:
        pass
