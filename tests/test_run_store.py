"""RunStore unit tests."""

from pathlib import Path

from chumoli.store.run_store import RunStore


def test_record_and_list(tmp_path: Path) -> None:
    store = RunStore(db_path=tmp_path / "runs.db")
    rid = store.record(
        pipeline_name="p1",
        success=True,
        quality_passed=True,
        row_counts={"t": 3},
        trigger="manual",
        duration_seconds=1.5,
        total_rows=3,
        rows_per_second=2.0,
    )
    assert rid >= 1
    rows = store.list_recent(limit=10)
    assert len(rows) == 1
    assert rows[0]["pipeline_name"] == "p1"
    assert rows[0]["row_counts"] == {"t": 3}
    assert rows[0]["duration_seconds"] == 1.5
    assert rows[0]["total_rows"] == 3
    assert rows[0]["new_rows"] == 0
    assert rows[0]["is_first_run"] is True
    stats = store.stats()
    assert stats["total_runs"] == 1
    assert stats["success"] == 1
    assert stats["total_rows_loaded"] == 3
