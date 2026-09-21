"""
chumoli.core.scheduler
======================

Built-in APScheduler: interval + daily_at.

Ishlash modeli:
  trigger (interval/cron) → RunQueue.enqueue → max N parallel worker

To'g'ridan-to'g'ri run_pipeline_by_name chaqirilmaydi — ertalab
ko'p job birga o'qsa ham process qulamasin.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from chumoli.connectors import register_builtin_connectors
from chumoli.core.config import ScheduleKind
from chumoli.core.run_queue import get_run_queue
from chumoli.store.control_store import ControlStore

log = logging.getLogger("chumoli.scheduler")

_lock = threading.RLock()
_scheduler: Any = None
_started = False

DEFAULT_TZ = "Asia/Tashkent"


def _job_id(name: str) -> str:
    return f"pipeline:{name}"


def _enqueue_job(name: str) -> None:
    """APScheduler callback — faqat navbatga qo'yadi."""
    get_run_queue().enqueue(name, trigger="schedule")


def _parse_hhmm(value: str) -> tuple[int, int]:
    parts = value.strip().split(":")
    return int(parts[0]), int(parts[1])


def _clear_jobs(scheduler: Any) -> None:
    """Remove every registered job so a reload cannot keep a stale interval."""
    for existing_job in list(scheduler.get_jobs()):
        existing_job.remove()


def _add_jobs_from_store(scheduler: Any, store: ControlStore) -> None:
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    for item in store.list_all():
        cfg = item.get("config") or {}
        sched = cfg.get("schedule") or {}
        kind = sched.get("kind") or "manual"
        name = item["name"]

        if kind == ScheduleKind.INTERVAL.value:
            minutes = sched.get("interval_minutes")
            if not minutes:
                continue
            scheduler.add_job(
                _enqueue_job,
                trigger=IntervalTrigger(minutes=int(minutes)),
                id=_job_id(name),
                args=[name],
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            log.info("scheduled interval name=%s every=%sm", name, minutes)

        elif kind == ScheduleKind.DAILY_AT.value:
            raw_time = sched.get("daily_at_time") or ""
            try:
                hour, minute = _parse_hhmm(raw_time)
            except Exception:
                log.warning("skip daily_at bad time name=%s time=%r", name, raw_time)
                continue
            tz = (sched.get("timezone") or DEFAULT_TZ).strip() or DEFAULT_TZ
            try:
                trigger = CronTrigger(hour=hour, minute=minute, timezone=tz)
            except Exception:
                log.exception("skip daily_at bad tz name=%s tz=%r", name, tz)
                continue
            scheduler.add_job(
                _enqueue_job,
                trigger=trigger,
                id=_job_id(name),
                args=[name],
                replace_existing=True,
                max_instances=1,
                coalesce=True,
            )
            log.info(
                "scheduled daily_at name=%s time=%02d:%02d tz=%s",
                name,
                hour,
                minute,
                tz,
            )

        elif kind == ScheduleKind.AIRFLOW.value:
            log.info(
                "skip airflow kind name=%s — ichki scheduler boshqarmaydi",
                name,
            )


def start_scheduler() -> dict[str, Any]:
    """API process ichida background scheduler ni ishga tushiradi.

    Agar allaqachon ishlayotgan bo'lsa, eski job'lar o'chiriladi va
    joriy config'dan qayta qo'shiladi (interval 1→60 kabi o'zgarishlar
    uchun `replace_existing` yetarli emas: skip/manual qolgan job o'chmaydi).
    """
    global _scheduler, _started
    with _lock:
        from apscheduler.schedulers.background import BackgroundScheduler

        register_builtin_connectors()
        store = ControlStore()
        # Ensure queue executor is wired
        get_run_queue()

        already_running = _started and _scheduler is not None
        if already_running:
            scheduler = _scheduler
        else:
            # Scheduler UTC; daily_at job'lar o'z timezone'ida
            scheduler = BackgroundScheduler(timezone="UTC")

        # Eski job'larni tozalash — interval/kind o'zgarsa ham stale job qolmasin
        _clear_jobs(scheduler)
        _add_jobs_from_store(scheduler, store)

        if not already_running:
            scheduler.start()
            _scheduler = scheduler
            _started = True
        return status()


def stop_scheduler() -> dict[str, Any]:
    global _scheduler, _started
    with _lock:
        if _scheduler is not None:
            try:
                _clear_jobs(_scheduler)
            except Exception:
                log.exception("scheduler_clear_jobs_failed")
            _scheduler.shutdown(wait=False)
            _scheduler = None
            _started = False
        return status()


def reload_jobs() -> dict[str, Any]:
    """Pipeline config o'zgarganda job'larni qayta yuklash."""
    with _lock:
        if _started and _scheduler is not None:
            # Ishlayotgan scheduler ustida job'larni almashtirish —
            # stop()+start() dagi `_started` guard race'ini chetlab o'tadi.
            _clear_jobs(_scheduler)
            register_builtin_connectors()
            _add_jobs_from_store(_scheduler, ControlStore())
            return status()
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
    out: dict[str, Any] = {
        "running": running,
        "jobs": jobs,
        "job_count": len(jobs),
    }
    try:
        out["run_queue"] = get_run_queue().status()
    except Exception:
        out["run_queue"] = {}
    return out
