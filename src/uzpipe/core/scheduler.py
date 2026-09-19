"""
uzpipe.core.scheduler
=======================

APScheduler asosidagi built-in interval scheduler.

Faqat ScheduleKind.INTERVAL pipeline'larni ishga tushiradi.
MANUAL — faqat dashboard/CLI; AIRFLOW — tashqi tizim.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import Any

from uzpipe.connectors import register_builtin_connectors
from uzpipe.core.config import ScheduleKind
from uzpipe.core.pipeline_runner import run_pipeline_by_name
from uzpipe.store.control_store import ControlStore
from uzpipe.store.run_store import RunStore

log = logging.getLogger("uzpipe.scheduler")

_lock = threading.RLock()
_scheduler: Any = None
_started = False


def _job_id(name: str) -> str:
    return f"pipeline:{name}"


def _run_job(name: str) -> None:
    register_builtin_connectors()
    store = ControlStore()
    runs = RunStore()
    started = datetime.now(UTC)
    try:
        result = run_pipeline_by_name(name, store=store)
        details = [
            {"passed": o.passed, "detail": o.detail}
            for o in result.quality_report.outcomes
        ]
        runs.record(
            pipeline_name=name,
            success=result.success,
            quality_passed=result.quality_report.all_passed,
            row_counts=result.row_counts,
            quality_details=details,
            started_at=started,
            finished_at=datetime.now(UTC),
            trigger="schedule",
        )
        log.info(
            "scheduled_run_ok name=%s rows=%s quality=%s",
            name,
            result.row_counts,
            result.quality_report.all_passed,
        )
    except Exception as e:
        runs.record(
            pipeline_name=name,
            success=False,
            quality_passed=False,
            error=str(e),
            started_at=started,
            finished_at=datetime.now(UTC),
            trigger="schedule",
        )
        log.exception("scheduled_run_failed name=%s", name)


def start_scheduler() -> dict[str, Any]:
    """API process ichida background scheduler ni ishga tushiradi."""
    global _scheduler, _started
    with _lock:
        if _started and _scheduler is not None:
            return status()

        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        scheduler = BackgroundScheduler(timezone="UTC")
        register_builtin_connectors()
        store = ControlStore()

        for item in store.list_all():
            cfg = item.get("config") or {}
            sched = cfg.get("schedule") or {}
            kind = sched.get("kind") or "manual"
            minutes = sched.get("interval_minutes")
            name = item["name"]
            if kind == ScheduleKind.INTERVAL.value and minutes:
                scheduler.add_job(
                    _run_job,
                    trigger=IntervalTrigger(minutes=int(minutes)),
                    id=_job_id(name),
                    args=[name],
                    replace_existing=True,
                    max_instances=1,
                    coalesce=True,
                )
                log.info("scheduled name=%s every=%sm", name, minutes)

        scheduler.start()
        _scheduler = scheduler
        _started = True
        return status()


def stop_scheduler() -> dict[str, Any]:
    global _scheduler, _started
    with _lock:
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)
            _scheduler = None
            _started = False
        return status()


def reload_jobs() -> dict[str, Any]:
    """Pipeline config o'zgarganda job'larni qayta yuklash."""
    stop_scheduler()
    return start_scheduler()


def status() -> dict[str, Any]:
    jobs: list[dict[str, Any]] = []
    running = False
    with _lock:
        if _scheduler is not None and _started:
            running = True
            for job in _scheduler.get_jobs():
                jobs.append(
                    {
                        "id": job.id,
                        "next_run_time": (
                            job.next_run_time.isoformat()
                            if job.next_run_time
                            else None
                        ),
                    }
                )
    return {"running": running, "jobs": jobs, "job_count": len(jobs)}
