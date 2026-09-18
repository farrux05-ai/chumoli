"""pipeline_runner — ControlStore + connector → dlt.run(); quality after success."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import dlt

from uzpipe.connectors.base import BaseUZConnector, registry
from uzpipe.core.config import PipelineConfig
from uzpipe.core.quality import QualityReport, run_quality_checks
from uzpipe.store.control_store import ControlStore, StoredPipeline


@dataclass
class RunResult:
    pipeline_name: str
    load_info: Any
    row_counts: dict[str, int]
    quality_report: QualityReport
    duration_seconds: float = 0.0

    @property
    def success(self) -> bool:
        return not self.load_info.has_failed_jobs

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts.values())

    @property
    def rows_per_second(self) -> float:
        if self.duration_seconds <= 0:
            return 0.0
        return self.total_rows / self.duration_seconds


def build_dlt_pipeline(config: PipelineConfig) -> dlt.Pipeline:
    destination_kwargs: dict[str, Any] = {}
    if config.destination.connection:
        destination_kwargs["credentials"] = config.destination.connection

    if destination_kwargs:
        destination_factory = getattr(dlt.destinations, config.destination.connector)
        destination: Any = destination_factory(**destination_kwargs)
    else:
        destination = config.destination.connector

    return dlt.pipeline(
        pipeline_name=config.name,
        destination=destination,
        dataset_name=config.destination.dataset_name,
    )


def run_pipeline_by_name(name: str, store: ControlStore | None = None) -> RunResult:
    store = store or ControlStore()
    stored = store.load(name)
    if stored is None:
        raise KeyError(f"Pipeline '{name}' topilmadi")

    connector = registry.get(stored.config.connector_key)
    return _execute(stored, connector)


def _execute(stored: StoredPipeline, connector: BaseUZConnector) -> RunResult:
    source = connector.build_dlt_source(stored.config.source_params, stored.secrets)
    pipeline = build_dlt_pipeline(stored.config)

    t0 = perf_counter()
    load_info = pipeline.run(
        source,
        write_disposition=stored.config.write_disposition.value,
        primary_key=stored.config.primary_key or None,
    )
    duration = perf_counter() - t0

    load_succeeded = not load_info.has_failed_jobs
    row_counts = _get_row_counts(pipeline) if load_succeeded else {}

    if load_succeeded:
        quality_report = run_quality_checks(
            pipeline, stored.config.quality, tables_written=list(row_counts.keys())
        )
    else:
        quality_report = QualityReport()

    return RunResult(
        pipeline_name=stored.config.name,
        load_info=load_info,
        row_counts=row_counts,
        quality_report=quality_report,
        duration_seconds=round(duration, 3),
    )


def _get_row_counts(pipeline: dlt.Pipeline) -> dict[str, int]:
    user_tables = [
        table_name
        for table_name in pipeline.default_schema.tables.keys()
        if not table_name.startswith("_dlt")
    ]

    counts: dict[str, int] = {}
    with pipeline.sql_client() as client:
        for table_name in user_tables:
            result = client.execute_sql(f'SELECT COUNT(*) FROM "{table_name}"')
            counts[table_name] = result[0][0]
    return counts
