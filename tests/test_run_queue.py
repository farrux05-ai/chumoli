"""RunQueue: concurrency limit and dedupe (no Airflow)."""

from __future__ import annotations

import threading
import time

from chumoli.core.run_queue import RunQueue


def test_max_concurrent_and_fifo() -> None:
    started: list[str] = []
    lock = threading.Lock()
    release = {f"p{i}": threading.Event() for i in range(4)}

    def executor(name: str, trigger: str) -> None:
        with lock:
            started.append(name)
        release[name].wait(timeout=2.0)

    q = RunQueue(max_concurrent=2)
    q.set_executor(executor)

    for i in range(4):
        r = q.enqueue(f"p{i}", trigger="schedule")
        assert r["accepted"] is True

    time.sleep(0.15)
    with lock:
        assert len(started) == 2
        assert set(started) == {"p0", "p1"}

    release["p0"].set()
    time.sleep(0.15)
    with lock:
        assert "p2" in started
        assert len(started) == 3

    release["p1"].set()
    release["p2"].set()
    release["p3"].set()
    time.sleep(0.2)
    with lock:
        assert set(started) == {"p0", "p1", "p2", "p3"}


def test_dedupe_while_queued_or_running() -> None:
    gate = threading.Event()

    def executor(name: str, trigger: str) -> None:
        gate.wait(timeout=2.0)

    q = RunQueue(max_concurrent=1)
    q.set_executor(executor)

    assert q.enqueue("same", "schedule")["accepted"] is True
    time.sleep(0.05)
    # second while running
    r2 = q.enqueue("same", "schedule")
    assert r2["accepted"] is False
    assert r2["reason"] in ("already_running", "already_queued")
    gate.set()
    time.sleep(0.1)


def test_schedule_config_daily_at() -> None:
    from chumoli.core.config import ScheduleConfig, ScheduleKind

    s = ScheduleConfig(kind=ScheduleKind.DAILY_AT, daily_at_time="10:00")
    assert s.daily_at_time == "10:00"
    assert s.timezone == "Asia/Tashkent"
