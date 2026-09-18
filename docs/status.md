# Status — MVP v1 + volume demo

**Verified:** 2026-09-18

## Tests
- **55 passed**

## New (time-to-value)
- **Volume demo** connector (`synthetic_volume`) — 10k…1M local rows
- **1-click** `POST /api/demo/volume?row_count=100000` + UI button
- Run metrics: **duration_seconds**, **total_rows**, **rows_per_second**
- Verified: 50,000 rows → DuckDB in ~9.3s (~5.3k rows/s)

## Stack
- Connectors: synthetic_volume, PostgreSQL, MySQL, REST, SQL Database, Click, Payme, Uzum
- Destinations, scheduler, RunStore, Docker, skills/docs

## Run
```bash
PYTHONPATH=src python -m uvicorn uzpipe.api.app:app --host 127.0.0.1 --port 8000
# UI: ⚡ Volume demo
```
