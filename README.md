# UzPipe

Lightweight EL tool for Uzbekistan data sources, built on [dlt](https://dlthub.com) (Apache 2.0).

## Quick start (MVP)

```bash
pip install -e ".[dev]"
PYTHONPATH=src python -m uzpipe.api.app
```

Open: **http://127.0.0.1:8000/**

- Dashboard UI: `/`
- API docs: `/api/docs`
- Health: `/api/health`

### What works now

- Connectors: **PostgreSQL**, **MySQL**, **REST API**, **SQL Database** (generic)
- Create pipeline from UI (manifest-driven form)
- Run → real dlt load to **DuckDB**
- Secrets encrypted in local ControlStore (`~/.uzpipe/`)
- Quality checks after successful load
- CLI: `uzpipe list` / `uzpipe run <name>`

### Tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
# 43 passed
```

## Architecture

```
HTML dashboard  →  FastAPI  →  ControlStore + registry + run_pipeline_by_name  →  dlt
```

See `docs/status.md`, `MVP.md`, and `AGENTS.md` (project instructions).

## Not yet

- UZ connectors (Payme, Click, 1C, Didox)
- API change monitor → GitHub issues
- Scheduler / notify

License: Apache-2.0
