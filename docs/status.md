# Status (MVP)

**Last verified:** 2026-09-18

## Tests
- **45 passed** (sql + rest e2e, registry, destinations, CLI, quality, crypto)

## What exists now
- Full foundation (manifest, ControlStore, pipeline_runner, quality, CLI)
- **Connectors:** PostgreSQL, MySQL, REST API, SQL Database (generic)
- **Destinations (dlt built-in):** DuckDB, PostgreSQL, Filesystem/S3, ClickHouse
- Destination connection secrets encrypted (not in config_json)
- **FastAPI** + **HTML dashboard** (API-driven)
- Entry: `uzpipe-api` / `python -m uzpipe.api.app`

## Still not done
- UZ connectors (Payme, Click, 1C, Didox)
- API monitor → GitHub issues
- Notify, scheduler
