# Skill: run and test

```bash
pip install -e ".[dev]"
PYTHONPATH=src python -m pytest tests/ -q
PYTHONPATH=src python -m uvicorn chumoli.api.app:app --host 127.0.0.1 --port 8000
```

Smoke: POST pipeline rest_api → jsonplaceholder `/posts` → duckdb `/tmp/....duckdb` → run → expect 100 rows.

Never commit API keys. DuckDB path under `/tmp` if sandbox fsync fails.
