# Status — V1 hardening (P0 + P1)

**Verified:** 2026-09-19

## Tests
- **76 passed** (`PYTHONPATH=src python -m pytest tests/ -q`)

## P0 done
- API key auth (`X-API-Key` / Bearer); `/api/health` open
- No silent secret move from `source_params` → 422
- FastAPI coverage: `tests/test_api.py`, `tests/test_api_auth.py`

## P1 done
- Telegram notify (global bot token in settings)
- Recovery helpers + `/api/pipelines/{name}/failed-jobs` + recover actions
- `merge` requires `primary_key` at save time
- Scheduler startup failures logged

## Docker
- Bind `127.0.0.1:8000`
- See README Security section

## Still open (P2)
- Shared HTTP retry helper across UZ connectors
- Broader docs stale cleanup (ROADMAP/POSITIONING/dashboard.md/quality)
- P1.2 recovery test still weak (no forced failed-job assert)
