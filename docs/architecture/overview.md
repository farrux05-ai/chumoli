# Architecture overview

**Read this when you need to know which layer a piece of functionality
belongs to.** For the detailed reasoning behind each layer, follow the
links — this file is the map, not the territory.

## The layering principle

> **We build on top of dlt. We never rewrite what dlt already does.**

Every layer below exists because dlt does NOT provide it (verified in
[`dlt-boundary.md`](dlt-boundary.md)), not because we chose to
duplicate dlt's work.

```
┌─────────────────────────────────────────────────────────┐
│  Layer 4: Chumoli Dashboard (static HTML + FastAPI)       │
│  - Connector selection form (manifest-driven)            │
│  - Pipeline list, run monitor, Preview                   │
│  - Recover panel (wraps free dlt CLI)                    │
│  See: dashboard.md                                        │
└──────────────────────┬────────────────────────────────────┘
                        │ HTTP /api/*
┌──────────────────────▼────────────────────────────────────┐
│  Layer 3: Chumoli Connector layer (our core IP)            │
│  - BaseUZConnector protocol + ConnectorRegistry            │
│  - Manifest per connector (form schema)                    │
│  - UZ + generic connectors (REST, SQL, Payme, Click, …)  │
│  See: config-and-manifest.md, skills/write-connector.md    │
└──────────────────────┬────────────────────────────────────┘
                        │ dlt.sources.*, dlt.pipeline()
┌──────────────────────▼────────────────────────────────────┐
│  Layer 2: Chumoli control plane (config + security)        │
│  - PipelineConfig (Pydantic)                               │
│  - ControlStore (SQLite): configs + encrypted credentials  │
│  - CredentialCipher (Fernet)                                │
│  See: config-and-manifest.md, security.md                  │
└──────────────────────┬────────────────────────────────────┘
                        │
┌──────────────────────▼────────────────────────────────────┐
│  Layer 1: dlt (Apache 2.0, unmodified, called directly)   │
│  - rest_api_source, sql_database, filesystem destinations │
│  - Schema inference, state, load packages                   │
│  - CLI recovery tools, Airflow helper (PipelineTasksGroup)  │
│  See: dlt-boundary.md                                       │
└─────────────────────────────────────────────────────────────┘
```

## Why this order (bottom-up dependency)

Each layer depends only on the layer below it, never sideways or
upward.

- **Layer 1 (dlt):** we call it, we don't extend its source code.
- **Layer 2 (control plane):** `PipelineConfig` is dlt-agnostic; it becomes dlt-aware only inside `pipeline_runner.py`.
- **Layer 3 (connectors):** thin adapters `(params, secrets) → dlt source`. See [`skills/write-connector.md`](../skills/write-connector.md).
- **Layer 4 (dashboard):** never imports dlt. It uses `/api/*` only. Recovery CLI is wrapped in `pipeline_runner.py`.

## Quick lookup: "where does X belong?"

| If you're changing... | It belongs in |
|---|---|
| How a form field is validated | `core/manifest.py` |
| What fields a pipeline config holds | `core/config.py` |
| How credentials are encrypted | `security/crypto.py` |
| How pipelines are persisted | `store/control_store.py` |
| How a specific connector authenticates / paginates | `connectors/<name>/connector.py` |
| How `dlt.pipeline()` gets called | `core/pipeline_runner.py` |
| Destination catalog / paths | `core/destinations.py`, `core/paths.py` |
| Anything the user sees/clicks | `src/chumoli/static/index.html` + `api/app.py` |
