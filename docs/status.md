# Status — V1 P0 + Round 2

**Verified:** 2026-09-19

## Tests
- Run: `PYTHONPATH=src python -m pytest tests/ -q`
- **82 passed** (78 prior + 4 async/P0 tests)

## V1 P0
- Async run endpoint (`POST /api/pipelines/{name}/run/async` + `GET /api/runs/jobs/{id}`) — sinxron HTTP timeout xavfini yo'qotadi; eski `/run` saqlangan (backward-compat)
- API key solishtirish: `hmac.compare_digest` / `keys_match` (constant-time)
- Run history yozish xatolari endi `log.exception` bilan qayd etiladi (silent `pass` yo'q)

## Round 2
- `get_failed_jobs` faqat haqiqiy `step_exception`
- Telegram token encrypted (`set_secret_setting`)
- Recover UI: confirm + failed-job detail
- CORS localhost
