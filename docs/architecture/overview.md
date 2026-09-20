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
│  Layer 4: Chumoli Dashboard (marimo, built from scratch)  │
│  - Connector selection form (manifest-driven)            │
│  - Pipeline list, run monitor                             │
│  - "Recover" panel (calls dlt CLI commands underneath)    │
│  See: dashboard.md                                        │
└──────────────────────┬────────────────────────────────────┘
                        │ direct Python function calls
┌──────────────────────▼────────────────────────────────────┐
│  Layer 3: Chumoli Connector layer (our core IP)            │
│  - BaseUZConnector protocol + ConnectorRegistry            │
│  - manifest.py per connector (form schema)                │
│  - UZ connectors: Payme, Click, 1C, Didox, Soliq, MyGov    │
│  See: config-and-manifest.md, scalability.md, connector-skill.md │
└──────────────────────┬────────────────────────────────────┘
                        │ dlt.sources.*, dlt.pipeline()
┌──────────────────────▼────────────────────────────────────┐
│  Layer 2: Chumoli control plane (config + security)        │
│  - PipelineConfig (Pydantic, no YAML)                      │
│  - ControlStore (SQLite): configs + encrypted credentials  │
│  - CredentialCipher (Fernet)                                │
│  See: config-and-manifest.md, security.md                  │
└──────────────────────┬────────────────────────────────────┘
                        │
┌──────────────────────▼────────────────────────────────────┐
│  Layer 1: dlt (Apache 2.0, unmodified, called directly)   │
│  - rest_api_source, sql_database, filesystem                │
│  - Schema inference, state, load packages, schema contracts │
│  - CLI recovery tools, Airflow helper (PipelineTasksGroup)  │
│  See: dlt-boundary.md                                       │
└─────────────────────────────────────────────────────────────┘
```

## Why this order (bottom-up dependency)

Each layer depends only on the layer below it, never sideways or
upward. This is what makes the "swap dashboard tech, keep everything
else" move (documented in [`dashboard.md`](dashboard.md)) possible
without touching layers 1–3.

- **Layer 1 (dlt):** we call it, we don't extend its source code.
- **Layer 2 (control plane):** knows nothing about dlt's Python API
  directly — `PipelineConfig` is dlt-agnostic on purpose (see
  [`config-and-manifest.md`](config-and-manifest.md)). It only becomes
  dlt-aware inside `pipeline_runner.py`, which is the seam between
  layer 2 and layer 1.
- **Layer 3 (connectors):** each connector is a thin adapter that
  turns `(params, secrets)` into a `dlt.sources.DltSource`. This is
  the only place where Chumoli code touches dlt's `dlt.sources` API
  directly — see [`connector-skill.md`](connector-skill.md) for the
  exact contract.
- **Layer 4 (dashboard):** never imports dlt's internals directly. It
  calls three functions: `registry.all_manifests()`,
  `ControlStore.save()`, `run_pipeline_by_name()`. Everything dlt-CLI
  related (recovery) is wrapped by a small function in
  `pipeline_runner.py`, not called raw from the dashboard.

## Quick lookup: "where does X belong?"

| If you're changing... | It belongs in |
|---|---|
| How a form field is validated | `core/manifest.py` |
| What fields a pipeline config holds | `core/config.py` |
| How credentials are encrypted | `security/crypto.py` |
| How pipelines are persisted | `store/control_store.py` |
| How a specific connector authenticates / paginates | `connectors/<name>/connector.py` |
| How `dlt.pipeline()` gets called | `core/pipeline_runner.py` |
| Anything the user sees/clicks | dashboard (marimo) |
