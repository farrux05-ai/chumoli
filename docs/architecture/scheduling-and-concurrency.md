# Scheduling and concurrency (not Airflow)

## Goal

- Run pipelines on a **timer** (every N minutes or every day at 10:00).
- When many pipelines fire at the **same second**, do **not** start all of them at once and crash the host.
- Stay inside **one process** (`chumoli ui` / uvicorn). No Celery, no Airflow, no DAG UI.

## What we deliberately do not build

| Airflow-style | Chumoli |
|---------------|---------|
| DAG of tasks | Single pipeline = one job |
| Separate scheduler + workers cluster | One API process + thread pool |
| Catch-up backfill policy engine | `coalesce=True` on triggers only |
| Cross-pipeline dependencies | Not supported |

## Components

```
APScheduler (interval | daily_at cron)
        │
        ▼  enqueue only
   RunQueue (FIFO, max concurrent = 2 default)
        │
        ▼  worker threads
   run_pipeline_by_name + RunStore.record
```

1. **Scheduler** (`scheduler.py`)  
   - Loads pipelines with `schedule.kind` in `{interval, daily_at}`.  
   - Callback does **not** run the pipeline — it calls `RunQueue.enqueue(name, trigger="schedule")`.  
   - `daily_at` uses `CronTrigger(hour, minute, timezone=Asia/Tashkent)`.

2. **RunQueue** (`run_queue.py`)  
   - FIFO of pipeline names.  
   - At most `CHUMOLI_MAX_CONCURRENT_RUNS` (default **2**, cap 16) run at once.  
   - Same pipeline cannot be both queued and running twice (dedupe).  
   - When a worker finishes, the next queued job starts (`_pump`).

3. **Per-pipeline lock** (`pipeline_runner.PipelineAlreadyRunning`)  
   - Still enforced: one pipeline never runs two loads in parallel (dlt state safety).

## Why max concurrent = 2 by default

- Typical laptop / single VPS: DuckDB + Python + network cannot safely absorb 20 simultaneous loads.
- 10:00 stampede of 20 schedules → 2 run, 18 wait → host stays up.
- Operators can raise: `export CHUMOLI_MAX_CONCURRENT_RUNS=3`.

## Schedule kinds

| kind | Fields | Behavior |
|------|--------|----------|
| `manual` | — | UI / CLI only |
| `interval` | `interval_minutes` | Every N minutes |
| `daily_at` | `daily_at_time` (`HH:MM`), `timezone` | Once per day at wall clock |
| `airflow` | — | Reserved enum only; no integration |

## Failure behavior

- Queue worker catches exceptions, writes `RunStore` with `success=false`.
- Scheduler keeps running; one failed job does not stop the queue.
- Process restart clears the **in-memory** queue (acceptable for V1; durable queue is a later step if needed).

## Ops

```bash
# limit parallel runs
export CHUMOLI_MAX_CONCURRENT_RUNS=2

chumoli ui
# GET /api/scheduler → includes run_queue: {running, queued, max_concurrent}
```

## Why this scales “tomorrow” without Airflow

- Adding pipelines only adds trigger rows + queue depth, not thread explosions.
- Moving the executor to a second process later still keeps the same enqueue API.
- Cron/timezone cover the “every morning at 10” product need without a workflow engine.
