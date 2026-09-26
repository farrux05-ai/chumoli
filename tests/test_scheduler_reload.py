"""BUG 1 — scheduler config o'zgarsa eski job qolmasligi kerak."""

from __future__ import annotations

from chumoli.core.config import (
    DestinationConfig,
    PipelineConfig,
    ScheduleConfig,
    ScheduleKind,
)
from chumoli.core.manifest import ConnectorCategory, ConnectorManifest, FieldSpec
from chumoli.core.scheduler import reload_jobs, start_scheduler, status, stop_scheduler
from chumoli.store.control_store import ControlStore


_MANIFEST = ConnectorManifest(
    key="rest_api",
    label="REST",
    category=ConnectorCategory.UNIVERSAL,
    dlt_source_factory="dummy.path",
    fields=[FieldSpec(key="base_url", label="URL", secret=False)],
)


def _save(name: str, kind: ScheduleKind, minutes: int | None = None) -> None:
    store = ControlStore()
    config = PipelineConfig(
        name=name,
        connector_key="rest_api",
        source_params={"base_url": "https://example.com"},
        destination=DestinationConfig(connector="duckdb"),
        schedule=ScheduleConfig(kind=kind, interval_minutes=minutes),
    )
    store.save(config, raw_secrets={}, manifest=_MANIFEST)


def _job_minutes(job_id: str) -> int | None:
    from chumoli.core import scheduler as sched_mod

    sch = sched_mod._scheduler
    assert sch is not None
    job = sch.get_job(job_id)
    if job is None:
        return None
    return int(job.trigger.interval.total_seconds() // 60)


def test_reload_replaces_interval_and_drops_manual(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "home"))
    try:
        _save("nasa", ScheduleKind.INTERVAL, 1)
        started = start_scheduler()
        assert started["running"] is True
        assert _job_minutes("pipeline:nasa") == 1

        # 1 daqiqa → 60 daqiqa: start_scheduler allaqachon ishlayotgan bo'lsa ham yangilansin
        _save("nasa", ScheduleKind.INTERVAL, 60)
        again = start_scheduler()
        assert again["running"] is True
        assert _job_minutes("pipeline:nasa") == 60

        # interval → manual: eski job o'chsin
        _save("nasa", ScheduleKind.MANUAL)
        reloaded = reload_jobs()
        assert reloaded["running"] is True
        assert _job_minutes("pipeline:nasa") is None
        assert all(j["id"] != "pipeline:nasa" for j in status()["jobs"])
    finally:
        stop_scheduler()
