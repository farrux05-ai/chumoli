# Status (MVP v1 — production-ready core)

**Last verified:** 2026-09-18

## Tests
- **53 passed**

## v1 (prod core)
- Connectors: PostgreSQL, MySQL, REST API, SQL Database
- UZ payments: **Click**, **Payme**, **Uzum Market**
- Destinations: DuckDB, PostgreSQL, Filesystem/S3, ClickHouse
- Secrets encrypted (source + destination connection)
- **Run monitor** (`RunStore` + dashboard Runs)
- **Scheduler** (APScheduler interval jobs, auto-start on API boot)
- FastAPI + HTML dashboard (Pipelines / Runs / Connectors / Scheduler)

## Not yet
- 1C, Didox, Soliq
- API contract monitor → GitHub issues
- Telegram notify
