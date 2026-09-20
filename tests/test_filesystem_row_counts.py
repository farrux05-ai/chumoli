"""Filesystem destination must not COUNT(*) via DuckDB CSV reader."""

from __future__ import annotations

from types import SimpleNamespace

from chumoli.core.row_counts import get_row_counts, row_counts_from_load_packages


def test_row_counts_from_load_packages() -> None:
    job = SimpleNamespace(table_name="posts", rows_count=42)
    dlt_job = SimpleNamespace(table_name="_dlt_loads", rows_count=1)
    package = SimpleNamespace(jobs={"completed_jobs": [job, dlt_job]})
    info = SimpleNamespace(load_packages=[package])
    assert row_counts_from_load_packages(info) == {"posts": 42}


def test_get_row_counts_prefers_trace() -> None:
    pipe = SimpleNamespace(
        pipeline_name="p",
        last_trace=SimpleNamespace(
            last_normalize_info=SimpleNamespace(
                row_counts={"posts": 10, "_dlt_pipeline_state": 1}
            )
        ),
        default_schema=SimpleNamespace(tables={}),
    )
    assert get_row_counts(pipe, dest_key="filesystem") == {"posts": 10}


def test_get_row_counts_filesystem_skips_sql() -> None:
    def boom():
        raise AssertionError("sql_client must not be called for filesystem")

    pipe = SimpleNamespace(
        pipeline_name="p",
        last_trace=None,
        default_schema=SimpleNamespace(tables={"posts": {}}),
        sql_client=boom,
    )
    job = SimpleNamespace(table_name="posts", rows_count=7)
    info = SimpleNamespace(load_packages=[SimpleNamespace(jobs={"completed_jobs": [job]})])
    assert get_row_counts(pipe, dest_key="filesystem", load_info=info) == {"posts": 7}
