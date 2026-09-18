from uzpipe.store.run_store import RunStore


def test_run_store_record_and_list(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    rid = store.record(
        pipeline_name="p1",
        success=True,
        quality_passed=True,
        row_counts={"t": 3},
        trigger="manual",
    )
    assert rid >= 1
    rows = store.list_recent(limit=10)
    assert len(rows) == 1
    assert rows[0]["pipeline_name"] == "p1"
    assert rows[0]["row_counts"] == {"t": 3}
    stats = store.stats()
    assert stats["total_runs"] == 1
    assert stats["success"] == 1
