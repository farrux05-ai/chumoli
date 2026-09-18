# Status — MVP v1 (showable)

**Verified:** 2026-09-18

## Tests
- **53 passed**

## Done
- Connectors: PostgreSQL, MySQL, REST API, SQL Database
- UZ: Click, Payme, Uzum Market
- Destinations: DuckDB, PostgreSQL, Filesystem, ClickHouse
- Secrets encrypted (source + destination)
- Run monitor + last_run on pipeline list
- Interval scheduler (APScheduler)
- Dashboard: Pipelines / Runs / Connectors / Scheduler
- Docker: `Dockerfile` + `docker-compose.yml`
- `UZPIPE_HOME` env for data dir
- Demo verified: REST (jsonplaceholder) → DuckDB, 100 rows

## Run
```bash
pip install -e ".[dev]"
PYTHONPATH=src python -m uzpipe.api.app
# or: docker compose up --build
```

## Not yet
- 1C / Didox / Soliq
- Telegram notify
- API contract monitor
