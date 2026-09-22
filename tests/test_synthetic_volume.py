"""Synthetic volume connector — pre-built Parquet + pyarrow batches."""

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry


def test_synthetic_registered() -> None:
    register_builtin_connectors()
    m = registry.get_manifest("synthetic_volume")
    assert m.label.startswith("Volume")
    assert any(f.key == "row_count" for f in m.fields)


def test_build_yields_requested_count() -> None:
    register_builtin_connectors()
    src = registry.get("synthetic_volume").build_dlt_source(
        {"row_count": "1000", "batch_label": "t"},
        {},
    )
    total = 0
    first_batch = None
    for chunk in src:
        if first_batch is None:
            first_batch = chunk
        if hasattr(chunk, "num_rows"):
            total += int(chunk.num_rows)
        elif isinstance(chunk, list):
            total += len(chunk)
        else:
            total += 1
    assert total == 1000
    # Arrow batch path
    if hasattr(first_batch, "column"):
        names = first_batch.schema.names
        assert "event_id" in names
        assert "batch" in names
