# Chumoli Architecture

**Audience:** human + AI agents. Read this before changing code.

## One sentence

Chumoli is a **thin control plane + UZ connectors** on top of **unmodified dlt**. We do not reimplement extract/load.

## Layers (do not blur)

```
L4  Dashboard (static HTML + JS)
      │  only: GET manifests, CRUD pipelines, run, runs, scheduler
L3  Connectors (thin adapters)
      │  build_dlt_source(params, secrets) → dlt source/resource
L2  Control plane
      │  PipelineConfig, ControlStore, RunStore, CredentialCipher, scheduler
L1  dlt (Apache 2.0, unmodified)
      │  rest_api, sql_database, destinations, schema, state, load
```

| Layer | Package / path | Knows about dlt? |
|-------|----------------|------------------|
| L4 | `src/chumoli/static/index.html`, `api/app.py` | No (calls our API only) |
| L3 | `connectors/*` | Yes — only inside `build_dlt_source` |
| L2 | `core/`, `store/`, `security/` | Only `pipeline_runner` + `scheduler` |
| L1 | external `dlt` package | — |

### Hard boundaries

1. **Dashboard must not import dlt.**
2. **Connectors must not touch ControlStore / FastAPI / HTML.**
3. **ControlStore must not import dlt** (only stores config + secrets).
4. **Never depend on `dlt[hub]` / dltHub commercial features.**

## Data flow (one pipeline run)

```
UI/API
  → ControlStore.load(name)
  → registry.get(connector_key)
  → connector.build_dlt_source(params, secrets)
  → pipeline_runner.build_dlt_pipeline(config)
  → dlt.pipeline.run(source)
  → quality checks (optional)
  → RunStore.record(...)
```

## Key types

| Type | Where | Role |
|------|--------|------|
| `ConnectorManifest` | `core/manifest.py` | Form schema + secret keys |
| `BaseUZConnector` | `connectors/base.py` | Protocol: `manifest` + `build_dlt_source` |
| `PipelineConfig` | `core/config.py` | Runnable config (no secrets in source_params) |
| `DestinationConfig` | `core/config.py` + `core/destinations.py` | duckdb / postgresql / filesystem / s3 / clickhouse |
| `ControlStore` | `store/control_store.py` | SQLite configs + Fernet secrets |
| `RunStore` | `store/run_store.py` | Run history (no secrets) |

## Secrets rules

- Manifest field with `secret=True` → stored only in `secrets_json` (encrypted).
- Destination connection → secret key `_destination_connection`.
- `params` and `secrets` stay **separate** inside `build_dlt_source`.
- Never log secret values.

## Runtime paths

| Path | Role |
|------|------|
| `$CHUMOLI_HOME` (default `~/.chumoli`) | Control DB, keys, dlt `pipelines/` state (hidden) |
| `$CHUMOLI_DATA` (default `~/chumoli-data`) | DuckDB files, local CSV/Parquet exports |
| `~/chumoli-data/exports/<pipeline>/` | Default local filesystem destination |

## Destinations (MVP set)

| Catalog key | dlt backend | Connection |
|-------------|-------------|------------|
| `duckdb` | duckdb | optional path → `~/chumoli-data/<pipeline>.duckdb` |
| `postgresql` | postgres | required SQLAlchemy URL |
| `filesystem` | filesystem | optional local path → `~/chumoli-data/exports/<pipeline>/` |
| `s3` | filesystem | required `s3://` / `gs://` / `az://` … |
| `clickhouse` | clickhouse | required URL (`dlt[clickhouse]` extra) |

- `filesystem` and `s3` are **separate** UI entries; both use `dlt.destinations.filesystem`.
- Local data files are user-visible; dlt `_dlt*` metadata under the dataset is filtered in UI preview.

## Scheduler

- `manual` — UI/CLI only
- `interval` — APScheduler in API process
- `airflow` — export only

## Where does change X go?

| Change | Put it here |
|--------|-------------|
| New form field | connector MANIFEST + build_dlt_source |
| New connector | `connectors/<key>/` + `__init__.py` |
| New destination | `core/destinations.py` |
| Persist config | `store/control_store.py` |
| Run history | `store/run_store.py` |
| Schedule | `core/scheduler.py` |
| HTTP route | `api/app.py` |
| UI | `src/chumoli/static/index.html` |

## Skills

See `docs/skills/README.md`.
