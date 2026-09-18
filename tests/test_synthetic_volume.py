"""Synthetic volume connector — no network."""

from uzpipe.connectors import register_builtin_connectors
from uzpipe.connectors.base import registry


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
    rows = list(src)
    assert len(rows) == 1000
    assert rows[0]["event_id"] == 0
    assert rows[-1]["batch"] == "t"
