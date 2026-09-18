# Status (MVP)

**Last verified:** 2026-09-18

## Tests
- Unit/e2e fundament: **42/42 passed**
- FastAPI E2E: create REST pipeline → run against jsonplaceholder → **100 rows** to DuckDB → success

## What exists now
- Full foundation (manifest, ControlStore, pipeline_runner, quality, rest_api, sql_database, CLI)
- **FastAPI** (`src/uzpipe/api/app.py`): health, connectors, pipelines CRUD, run
- **HTML dashboard** (`static/index.html`): API-driven, not mock
- Entry: `uzpipe-api` / `python -m uzpipe.api.app`

## Still not done
- UZ connectors (Payme, Click, 1C, Didox)
- API monitor → GitHub issues
- Rename UI to PostgreSQL/MySQL cards
- Notify, scheduler
