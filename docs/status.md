# Status

**Verified:** 2026-09-29

## 0.1.2 — prod tayyor

- **Prod deb e’lon qilindi:** `rest_api`, `sql_database` / `postgresql` / `mysql`,
  `filesystem_s3`, `synthetic_volume` va endi **`bitrix24`** hamda **`moysklad`**
  — `maturity: stable` (ikkitasida manbada aniq yozilgan). Beta bo‘lib qoladi:
  `click_uz`, `payme_uz`, `uzum_market`, `didox`, `facebook_ads`.
  `tests/test_manifest.py::test_production_connectors_are_stable` shu ro‘yxatni
  qulflaydi.
- PyPI classifier `Development Status :: 5 - Production/Stable`; README badge yangilandi.
- Versiya yagona manbadan: `src/chumoli/__init__.py` = `0.1.2`.
- Testlar: **236 passed** (0.1.1: 231).

## Latest (V1 connector fixes)

- **`facebook_ads` retry was dead:** Meta 429/5xx arrive as JSON, were raised as
  `ValueError`, and `is_transient_http` does not retry those — rate limits were
  never re-attempted. Transient statuses are now re-raised as `HTTPStatusError`
  via the shared `is_transient_status_code` (`core/retry_policy.py`).
- **`moysklad` filter timezone:** `updated>=` boundary now uses `Europe/Moscow`
  (MoySklad server time). Tashkent (+5) shifted the window 2h forward, so
  records changed inside that window could be skipped by incremental merges.
- **`moysklad` stock key:** `_href` is derived from `meta.href` with the query
  string stripped (stable across `?expand=...`), with nested
  `product.id` / `product.meta.href` fallback.
- **`drop-resource` was a silent no-op (duckdb):** the dlt CLI ran in a
  subprocess with no destination credentials, so it created a stray empty
  `<cwd>/<pipeline>.duckdb`, dropped there and returned success — the real table
  stayed. It now uses dlt's `pipeline_drop` helper **in-process** on the pipeline
  built from the stored config (same as `sync` / `drop-pending`), so the drop hits
  the real destination and leaves no files in the working directory. A drop that
  matches no table/state is now an error, not `ok`.
- **Pagination guards:** `bitrix24` (`next: 0` / non-advancing `next`) and
  `facebook_ads` (repeated `after` cursor) could loop forever; both break out.
- **`filesystem_s3` file detection:** the last bucket-path segment counts as a
  file only for known data extensions — `s3://bucket/data.v2` stays a prefix.
- **`.gitignore`:** `.uzpipe/` was never actually ignored (inline `#` comment on
  the pattern line); the comment now sits on its own line.

## Prior (V1 source connectors)

- **`filesystem_s3`** — dlt `readers` thin wrap (local + `s3://` / `gs://` / `az://`).
  CSV via DuckDB reader (pandas yo‘q), Parquet, JSONL. Lokal e2e: JSONL → DuckDB.
- **`moysklad`** — JSON API 1.2 (`api.moysklad.ru/api/remap/1.2`). Bearer yoki
  Basic (`login:parol`). Resurslar: customerorder, demand, invoiceout, product,
  retaildemand, stock. `Accept-Encoding: gzip` (rasmiy 415 himoyasi).
- **`bitrix24`** — inbound webhook yoki portal + OAuth. `crm.deal.list`,
  `crm.lead.list`, `crm.contact.list`, `tasks.task.list`. Pagination `start`/`next`.
- **`facebook_ads`** — Meta Marketing API (campaigns / adsets / ads). Beta:
  sandbox yo‘q, real `access_token` + `account_id` kerak. dlt Community source
  bilan mos.

## Prior (ClickHouse / load performance)

- **ClickHouse loader format:** `parquet` instead of dlt's `jsonl` default
  (columnar + compressed; `clickhouse_connect.insert_file` is far faster).
  Override per pipeline via `destination.file_format`.
- **Quality checks reuse one `sql_client`** instead of opening one per check —
  removes a connect/auth round-trip per check on remote destinations.
- Note: a run's wall time is dominated by source/destination network latency, not
  row count — a 8-row run and a 740-row run both took ~18s in the same environment.
  For large ClickHouse loads, configure a **staging** destination (S3) so ClickHouse
  reads via `INSERT INTO … SELECT FROM s3(...)` instead of a local file upload.

## Prior (recovery hardening)

- **`drop-resource` was completely broken** — the dlt CLI got `--pipelines-dir`
  after the subcommand (rejected) and no `-y` (could hang). Fixed to
  `dlt -y pipeline --pipelines-dir <dir> <name> drop <resource>`.
  *(Superseded: that CLI call could not see the destination credentials — see
  Latest. The drop is now performed in-process.)*
- Recovery (`sync` / `drop-pending` / `drop-resource`) is **blocked while the pipeline
  is running** — wiping pending dirs or dropping a table mid-load corrupts dlt state.
- Recovery error messages are **redacted** (`sanitize_error`) — no connection-string
  passwords in dashboard toasts.
- Dashboard recovery buttons disable during the action; failures surface as errors
  (an error payload was previously toasted as success).

## Prior (run error handling)

- **Failures are persisted** for manual (sync), async and demo runs — previously only
  scheduler runs recorded failures, so a dashboard-triggered failure left no trace.
- **Error reason captured:** `RunResult.error` / `RunResponse.error` carry the dlt
  failed-jobs reason; the dashboard run history renders it (red text under the badge).
- **Credential redaction:** `core/errors.py` (`sanitize_error`) strips passwords/tokens
  from connection strings, `Authorization`/`Bearer` and `key=value` secrets before
  anything is stored, returned or shown. `friendly_error` maps to plain Uzbek.
- `409 already running` is intentionally **not** recorded as a failure.

## Prior (bug fixes + docs)

- **Fixed:** Click connector auth raised `NameError` (`time` not imported) — connector was unusable.
- **Fixed:** filesystem export silently did nothing (`Path` undefined in `_execute`, swallowed by `except Exception`).
- **Fixed:** wheel build failed on duplicate `chumoli/static/index.html` (redundant `force-include`).
- Version is now single-sourced from `src/chumoli/__init__.py` (`pyproject.toml` + FastAPI app read it dynamically).
- Docs refreshed: architecture/strategy docs corrected; `docs/original-positioning/` marked historical.

## Prior (0.1.0 packaging)

- UZ connectors marked **beta** (`maturity` on manifest + UI badge).
- README: `pip install chumoli` primary path; PyPI classifiers.
- Filesystem: `_dlt_*` stays in `~/.chumoli/fs_staging/`; publish clean data only.

## Prior (filesystem / S3)

- Catalog: **`filesystem`** (local only) vs **`s3`** (object storage) — both use `dlt.destinations.filesystem`.
- Local exports: **`~/chumoli-data/exports/<pipeline>/`** (user-visible). dlt state remains under **`~/.chumoli/pipelines/`**.
- Preview for local filesystem: `export_path`, file list (skips `_dlt*`), CSV sample + copy/open in UI.
- Canonical UI is `src/chumoli/static/index.html` (no duplicate repo-root `static/`).
- Docs aligned: dashboard is static HTML (not marimo / not dltHub).

## Prior (dest connection isolation)

- **UI:** Destination connection cached **per destination key** (`_destConnByKey`).
- **API:** Reject create when destination extra is not installed.
- **Runner:** Scheme mismatch guard between destination types.

## Prior (still valid)

- Async run: `POST /api/pipelines/{name}/run/async` + `GET /api/runs/jobs/{id}`
- API key constant-time compare
- Telegram token via encrypted settings

## Tests

```bash
PYTHONPATH=src python -m pytest tests/ -q
```
