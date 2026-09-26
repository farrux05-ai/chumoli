# Dashboard strategy

Layer 4 in `overview.md` / `ARCHITECTURE.md`.

## Current decision: static HTML + FastAPI

The dashboard is a single-page app:

- **UI:** `src/chumoli/static/index.html` (Uzbek labels, no framework)
- **API:** `src/chumoli/api/app.py` (FastAPI)

It talks only to `/api/*` — it does **not** import dlt.

Main flows:

- Connector selection from manifests
- Pipeline CRUD, Run (sync/async), Preview, schedule
- Recovery actions that wrap free dlt CLI (`failed-jobs`, `sync`, `drop-pending`, `drop-resource` — see `dlt-boundary.md`)

### Filesystem / S3 preview

- **Lokal fayl:** Preview returns `export_path`, data file list (skips `_dlt*`), and CSV samples; UI offers copy path / open folder.
- **S3:** Preview shows bucket URL only (no local files).

## Why not dlt dashboard / dltHub (kept for the record)

**This section stays on purpose** so the same mistake is not repeated.

`dlt dashboard` is **not** part of open-source `dlt`. It requires `dlthub`, a separate commercial package (license / waiting list). Installing `dlt[hub]` pulls that commercial stack — not a free UI.

Chumoli must not depend on `dlt[hub]` or any dltHub-branded UI. See `dlt-boundary.md`.

### Historical note (marimo)

An earlier draft considered building the dashboard on [marimo](https://marimo.io). The **shipped** product uses static HTML instead (simpler deploy, no extra runtime). Docs that still say “marimo” are outdated; this file is the source of truth.

## Rules

1. Dashboard code must not import dlt.
2. All data via authenticated `/api/*`.
3. Secrets never returned to the browser in plaintext lists.
4. Canonical UI path: `src/chumoli/static/` (packaged with the wheel). Do not maintain a duplicate repo-root `static/`.
