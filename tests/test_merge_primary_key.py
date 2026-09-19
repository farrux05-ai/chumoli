"""P1.3 — merge requires primary_key at save time."""

import pytest
from pydantic import ValidationError

from uzpipe.core.config import DestinationConfig, PipelineConfig, WriteDisposition


def test_merge_without_pk_raises() -> None:
    with pytest.raises(ValidationError) as ei:
        PipelineConfig(
            name="m1",
            connector_key="rest_api",
            source_params={},
            destination=DestinationConfig(connector="duckdb", dataset_name="raw"),
            write_disposition=WriteDisposition.MERGE,
            primary_key=[],
        )
    assert "primary_key" in str(ei.value).lower() or "merge" in str(ei.value).lower()


def test_merge_with_pk_ok() -> None:
    cfg = PipelineConfig(
        name="m2",
        connector_key="rest_api",
        source_params={},
        destination=DestinationConfig(connector="duckdb", dataset_name="raw"),
        write_disposition=WriteDisposition.MERGE,
        primary_key=["id"],
    )
    assert cfg.primary_key == ["id"]
