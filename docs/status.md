# Status (MVP)

**Last verified:** 2026-09-18

## Tests
- Unit/e2e fundament: **pytest** (sql + rest e2e, registry, CLI, quality, crypto)
- FastAPI E2E: create REST pipeline → run against jsonplaceholder → rows to DuckDB

## What exists now
- Full foundation (manifest, ControlStore, pipeline_runner, quality, CLI)
- **Connectors (user-facing):**
  - **PostgreSQL** (`postgresql`)
  - **MySQL** (`mysql`)
  - **REST API** (`rest_api`)
  - **SQL Database** generic (`sql_database`) — SQLite / MSSQL / Oracle + tests
- All SQL variants share one dlt `sql_database` adapter
- **FastAPI** + **HTML dashboard** (API-driven)
- Entry: `uzpipe-api` / `python -m uzpipe.api.app`

## Still not done
- UZ connectors (Payme, Click, 1C, Didox)
- API monitor → GitHub issues
- Destination UI beyond DuckDB (PostgreSQL dest)
- Notify, scheduler
