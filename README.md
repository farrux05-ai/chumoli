# UzPipe

Lightweight EL tool for Uzbekistan data sources, built on [dlt](https://dlthub.com) (Apache 2.0).

## Quick start

```bash
pip install -e ".[dev]"
PYTHONPATH=src python -m uzpipe.api.app
```

Open **http://127.0.0.1:8000/**

Docker:

```bash
docker compose up --build
```

## v1 features

| Area | Status |
|------|--------|
| SQL (Postgres / MySQL / generic) | ✅ |
| REST API | ✅ |
| Click / Payme / Uzum Market | ✅ |
| Destinations (DuckDB, Postgres, FS, ClickHouse) | ✅ |
| Run monitor + last status | ✅ |
| Interval scheduler | ✅ |
| Encrypted secrets | ✅ |
| Docker | ✅ |

## Tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
# 53 passed
```

## Architecture

```
Dashboard → FastAPI → ControlStore + RunStore + Scheduler → dlt
```

Data dir: `~/.uzpipe` or `$UZPIPE_HOME`.

License: Apache-2.0
