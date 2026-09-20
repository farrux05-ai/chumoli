"""Runtime paths must stay under UZPIPE_HOME — never CWD."""

from __future__ import annotations

from pathlib import Path

from uzpipe.core.paths import (
    data_dir,
    default_duckdb_path,
    ensure_runtime_dirs,
    examples_dir,
    pipelines_dir,
    resolve_duckdb_path,
    uzpipe_home,
)


def test_uzpipe_home_respects_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("UZPIPE_HOME", str(tmp_path / "home"))
    h = uzpipe_home()
    assert h == (tmp_path / "home").resolve()
    ensure_runtime_dirs()
    assert data_dir().is_dir()
    assert pipelines_dir().is_dir()
    assert examples_dir().is_dir()


def test_default_duckdb_under_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("UZPIPE_HOME", str(tmp_path / "h"))
    path = default_duckdb_path("rest_test")
    assert path.endswith("rest_test.duckdb")
    assert str(data_dir()) in path
    assert "Desktop" not in path


def test_relative_connection_goes_to_data(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("UZPIPE_HOME", str(tmp_path / "h"))
    path = resolve_duckdb_path("my_wh.duckdb", "p1")
    assert Path(path).parent == data_dir().resolve()
    assert path.endswith("my_wh.duckdb")


def test_empty_connection_uses_pipeline_name(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("UZPIPE_HOME", str(tmp_path / "h"))
    path = resolve_duckdb_path("", "postgress")
    assert path.endswith("postgress.duckdb")
    assert str(data_dir().resolve()) in path


def test_absolute_path_preserved(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("UZPIPE_HOME", str(tmp_path / "h"))
    abs_p = tmp_path / "elsewhere" / "x.duckdb"
    path = resolve_duckdb_path(str(abs_p), "p")
    assert Path(path) == abs_p.resolve()
