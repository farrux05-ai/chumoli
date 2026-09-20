# Status — V1 release fixes

**Verified:** 2026-09-20

## Tests
- Run: `PYTHONPATH=src python -m pytest tests/ -q`
- Prior: 139 passed on clean install

## Latest fix (dest connection isolation)
- **UI:** Destination connection is cached **per destination key** only (`_destConnByKey`). Shared `f-dest-conn` fallback removed so a PostgreSQL URL cannot leak into ClickHouse / filesystem / others.
- **UI:** `closeDrawer` clears `draft` and inspect state (no stale strings after close).
- **UI:** Dest conn input starts empty; unavailable destinations (e.g. ClickHouse without `dlt[clickhouse]`) shown disabled.
- **API:** Reject create when destination extra is not installed (clear 422 in Uzbek).
- **Runner:** Scheme mismatch guard (postgres:// under clickhouse dest → clear error); clearer `pip install "dlt[…]"` message.

## V1 P0 (prior)
- Notify, CORS, Recovery UI, async job cleanup

## Prior (still valid)
- Async run: `POST /api/pipelines/{name}/run/async` + `GET /api/runs/jobs/{id}`
- API key: `keys_match` / constant-time
- Telegram token encrypted via `set_secret_setting`
