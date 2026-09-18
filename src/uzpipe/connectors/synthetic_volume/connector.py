"""
uzpipe.connectors.synthetic_volume
====================================

Local synthetic row generator — volume / throughput demos.

No network. Generates dict rows in-process for dlt to load into
DuckDB/Postgres/etc. Purpose: show time-to-value (rows + seconds).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import dlt

from uzpipe.core.manifest import (
    ConnectorCategory,
    ConnectorManifest,
    FieldSpec,
    FieldType,
    SelectOption,
)

# Cap to protect accidental multi-million runs in shared demos.
_MAX_ROWS = 2_000_000

MANIFEST = ConnectorManifest(
    key="synthetic_volume",
    label="Volume demo (synthetic)",
    category=ConnectorCategory.UNIVERSAL,
    description="Local generator — 10k…1M rows, no API. Shows dlt speed.",
    dlt_source_factory="uzpipe.connectors.synthetic_volume.connector.SyntheticVolumeConnector",
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
            help_text="Katta qiymat — birinchi run sekinroq bo'lishi mumkin",
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
def _events(row_count: int, batch_label: str) -> Iterator[dict[str, Any]]:
    base = datetime.now(UTC)
    for i in range(row_count):
        yield {
            "event_id": i,
            "batch": batch_label,
            "user_id": i % 10_000,
            "amount": (i % 500) + 0.01,
            "status": "ok" if i % 17 else "retry",
            "ts": (base - timedelta(seconds=i % 86_400)).isoformat(),
        }


class SyntheticVolumeConnector:
    """In-process volume generator — BaseUZConnector."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        del secrets  # no secrets
        n = int(params.get("row_count") or 100_000)
        n = max(1, min(n, _MAX_ROWS))
        label = str(params.get("batch_label") or "demo")
        return _events(row_count=n, batch_label=label)
