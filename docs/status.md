# Status — V1 release fixes

**Verified:** 2026-09-19

## Tests
- Run: `PYTHONPATH=src python -m pytest tests/ -q`
- **81 passed** (unit/API/async/notify); 3 e2e DuckDB schema failures are environment-related (pre-existing), not from V1 UI/API fixes

## V1 P0 (this round)
- **Notify:** `pipeline_runner` no longer swallows notify errors with bare `pass` — uses `log.exception("notify_failed …")` while still isolating failures from the run result
- **CORS:** `UZPIPE_CORS_ORIGINS` env (comma-separated or `*`); default remains localhost only
- **Recovery UI:** Pipelines table shows **Tiklash** when `last_run.success === false`; drawer loads failed-jobs + sync / drop-pending / drop-resource with confirm
- **Async jobs:** `_RUN_JOBS` lazy cleanup of finished entries older than 1 hour

## V1 P1
- **Runs page:** quality-fail badge shows first failing `quality_details[].detail` (truncated 80 chars)
- Dashboard already aligned: Runs, Settings, destinations from API, async run poll

## Prior (still valid)
- Async run: `POST /api/pipelines/{name}/run/async` + `GET /api/runs/jobs/{id}`
- API key: `keys_match` / constant-time
- Telegram token encrypted via `set_secret_setting`
- `get_failed_jobs` only real step exceptions
