"""
chumoli.core.run_queue
======================

Oddiy in-process run navbati. Airflow emas.

Maqsad: ertalab 10:00 da 20 ta schedule o'qsa ham hammasi birga
CPU/RAM ni yeb qulab tushmasin — bir vaqtda faqat N ta ishlaydi.

Qoidalar:
  - Bir pipeline bir vaqtda faqat 1 marta (queue yoki running da)
  - Global max concurrent (default 2, env CHUMOLI_MAX_CONCURRENT_RUNS)
  - Scheduler va manual async ham shu navbat orqali
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

log = logging.getLogger("chumoli.run_queue")


def _max_concurrent() -> int:
    raw = os.environ.get("CHUMOLI_MAX_CONCURRENT_RUNS", "2").strip()
    try:
        n = int(raw)
    except ValueError:
        n = 2
    return max(1, min(n, 16))


@dataclass
class QueueItem:
    pipeline_name: str
    trigger: str
    enqueued_at: float = field(default_factory=time.time)


class RunQueue:
    """Thread-safe FIFO with global concurrency limit."""

    def __init__(self, max_concurrent: int | None = None) -> None:
        self._max = max_concurrent if max_concurrent is not None else _max_concurrent()
        self._q: deque[QueueItem] = deque()
        self._queued_names: set[str] = set()
        self._running_names: set[str] = set()
        self._lock = threading.RLock()
        self._executor: Callable[[str, str], None] | None = None

    def set_executor(self, fn: Callable[[str, str], None]) -> None:
        """fn(pipeline_name, trigger) — actual run + record."""
        self._executor = fn

    def enqueue(self, pipeline_name: str, trigger: str = "manual") -> dict[str, Any]:
        """Add job if not already queued/running. Returns status dict."""
        name = (pipeline_name or "").strip()
        if not name:
            return {"accepted": False, "reason": "empty_name"}

        with self._lock:
            if name in self._running_names:
                return {
                    "accepted": False,
                    "reason": "already_running",
                    "pipeline_name": name,
                }
            if name in self._queued_names:
                return {
                    "accepted": False,
                    "reason": "already_queued",
                    "pipeline_name": name,
                }
            self._q.append(QueueItem(pipeline_name=name, trigger=trigger))
            self._queued_names.add(name)
            log.info(
                "enqueue name=%s trigger=%s queue_len=%s running=%s max=%s",
                name,
                trigger,
                len(self._q),
                len(self._running_names),
                self._max,
            )

        self._pump()
        return {
            "accepted": True,
            "pipeline_name": name,
            "trigger": trigger,
            "queue_depth": self.queue_depth(),
            "running": self.running_count(),
        }

    def queue_depth(self) -> int:
        with self._lock:
            return len(self._q)

    def running_count(self) -> int:
        with self._lock:
            return len(self._running_names)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "max_concurrent": self._max,
                "running": sorted(self._running_names),
                "running_count": len(self._running_names),
                "queued": [i.pipeline_name for i in self._q],
                "queue_depth": len(self._q),
            }

    def _pump(self) -> None:
        while True:
            item: QueueItem | None = None
            with self._lock:
                if len(self._running_names) >= self._max:
                    return
                if not self._q:
                    return
                item = self._q.popleft()
                self._queued_names.discard(item.pipeline_name)
                self._running_names.add(item.pipeline_name)

            t = threading.Thread(
                target=self._worker,
                args=(item,),
                name=f"chumoli-run-{item.pipeline_name}",
                daemon=True,
            )
            t.start()

    def _worker(self, item: QueueItem) -> None:
        name = item.pipeline_name
        trigger = item.trigger
        try:
            if self._executor is None:
                log.error("run_queue executor not set name=%s", name)
                return
            self._executor(name, trigger)
        except Exception:
            log.exception("run_queue_worker_failed name=%s trigger=%s", name, trigger)
        finally:
            with self._lock:
                self._running_names.discard(name)
            self._pump()


# Process-wide singleton (one API process)
_QUEUE: RunQueue | None = None
_QUEUE_LOCK = threading.Lock()


def get_run_queue() -> RunQueue:
    global _QUEUE
    with _QUEUE_LOCK:
        if _QUEUE is None:
            _QUEUE = RunQueue()
            _QUEUE.set_executor(_default_executor)
        return _QUEUE


def reset_run_queue_for_tests(max_concurrent: int = 2) -> RunQueue:
    """Tests only — replace singleton."""
    global _QUEUE
    with _QUEUE_LOCK:
        _QUEUE = RunQueue(max_concurrent=max_concurrent)
        _QUEUE.set_executor(_default_executor)
        return _QUEUE


def _default_executor(pipeline_name: str, trigger: str) -> None:
    from chumoli.connectors import register_builtin_connectors
    from chumoli.core.pipeline_runner import PipelineAlreadyRunning, run_pipeline_by_name
    from chumoli.store.control_store import ControlStore
    from chumoli.store.run_store import RunStore

    register_builtin_connectors()
    store = ControlStore()
    runs = RunStore()
    started = datetime.now(UTC)
    try:
        result = run_pipeline_by_name(pipeline_name, store=store)
        details = [
            {"passed": o.passed, "detail": o.detail}
            for o in result.quality_report.outcomes
        ]
        runs.record(
            pipeline_name=pipeline_name,
            success=result.success,
            quality_passed=result.quality_report.all_passed,
            row_counts=result.row_counts,
            quality_details=details,
            started_at=started,
            finished_at=datetime.now(UTC),
            trigger=trigger,
            duration_seconds=result.duration_seconds,
            total_rows=result.total_rows,
            rows_per_second=result.rows_per_second,
            new_rows=result.new_rows,
            col_counts=result.col_counts,
            schema_changes=result.schema_changes,
            cursor_last_value=result.cursor_last_value,
            is_first_run=result.is_first_run,
        )
        log.info(
            "queue_run_ok name=%s trigger=%s rows=%s",
            pipeline_name,
            trigger,
            result.row_counts,
        )
    except PipelineAlreadyRunning:
        # Concurrent manual /run won the lock — not a failure, just skip
        log.info(
            "queue_skip_already_running name=%s trigger=%s — not recording failure",
            pipeline_name,
            trigger,
        )
        return
    except Exception as e:
        log.exception("queue_run_failed name=%s", pipeline_name)
        runs.record(
            pipeline_name=pipeline_name,
            success=False,
            quality_passed=False,
            error=str(e),
            started_at=started,
            finished_at=datetime.now(UTC),
            trigger=trigger,
        )
