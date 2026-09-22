# Status

**Verified:** 2026-09-22

## Latest (filesystem / S3)

- Catalog: **`filesystem`** (local only) vs **`s3`** (object storage) — both use `dlt.destinations.filesystem`.
- Local exports: **`~/chumoli-data/exports/<pipeline>/`** (user-visible). dlt state remains under **`~/.chumoli/pipelines/`**.
- Preview for local filesystem: `export_path`, file list (skips `_dlt*`), CSV sample + copy/open in UI.
- Removed duplicate repo-root `static/`; canonical UI is `src/chumoli/static/index.html`.
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
