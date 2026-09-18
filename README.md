# UzPipe

Lightweight EL tool for Uzbekistan data sources, built on [dlt](https://dlthub.com) (Apache 2.0).

## Quick start

```bash
pip install -e ".[dev]"
PYTHONPATH=src python -m uzpipe.api.app
```

Open: **http://127.0.0.1:8000/**

### What works (v1)

- Connectors: **PostgreSQL**, **MySQL**, **REST API**, **SQL Database**
- UZ payments: **Click**, **Payme**, **Uzum Market**
- Destinations: **DuckDB**, **PostgreSQL**, **Filesystem/S3**, **ClickHouse**
- **Run monitor** + **interval scheduler** (APScheduler)
- Secrets encrypted · Quality checks · CLI + dashboard

### Tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
# 53 passed
```

## Architecture

```
HTML dashboard  →  FastAPI  →  ControlStore + RunStore + scheduler  →  dlt
```

See `docs/status.md` and `AGENTS.md`.

License: Apache-2.0
