"""
chumoli.connectors.synthetic_volume
=====================================

Local volume / throughput demo.

Data is pre-built once as Parquet under examples/ (see demo_data.ensure_volume_parquet),
then loaded with PyArrow batches — no row-by-row Python yield on the hot path.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import dlt

from chumoli.core.manifest import (
    ConnectorCategory,
    ConnectorManifest,
    FieldSpec,
    FieldType,
    SelectOption,
)

_MAX_ROWS = 2_000_000

MANIFEST = ConnectorManifest(
    key="synthetic_volume",
    label="Volume demo (synthetic)",
    category=ConnectorCategory.UNIVERSAL,
    description="Tayyor Parquet → DuckDB. Birinchi marta fayl yoziladi, keyin faqat o'qiladi.",
    dlt_source_factory="chumoli.connectors.synthetic_volume.connector.SyntheticVolumeConnector",
    fields=[
        FieldSpec(
            key="row_count",
            label="Qator soni",
            type=FieldType.SELECT,
            required=True,
            default="100000",
            options=[
                SelectOption(value="10000", label="10,000"),
                SelectOption(value="50000", label="50,000"),
                SelectOption(value="100000", label="100,000"),
                SelectOption(value="500000", label="500,000"),
                SelectOption(value="1000000", label="1,000,000"),
            ],
            help_text="Birinchi run faylni tayyorlaydi; keyingilari faqat Parquet o'qiydi",
        ),
        FieldSpec(
            key="batch_label",
            label="Batch yorlig'i (ixtiyoriy)",
            type=FieldType.TEXT,
            required=False,
            default="demo",
            placeholder="demo",
        ),
    ],
)


@dlt.resource(name="events", write_disposition="replace", primary_key="event_id")
def _events_from_parquet(parquet_path: str) -> Iterator[Any]:
    """Yield Arrow record batches from a pre-built Parquet file."""
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(parquet_path)
    for batch in pf.iter_batches(batch_size=50_000):
        yield batch


class SyntheticVolumeConnector:
    """Load pre-built volume Parquet (BaseUZConnector-compatible)."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        del secrets
        n = int(params.get("row_count") or 100_000)
        n = max(1, min(n, _MAX_ROWS))
        label = str(params.get("batch_label") or "demo")
        from chumoli.core.demo_data import ensure_volume_parquet

        path = ensure_volume_parquet(n, batch_label=label)
        return _events_from_parquet(str(path))
