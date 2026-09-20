---
name: chumoli-dlt-boundary
description: Chumoli dlt vs dltHub licensing boundary. Use when adding dlt features, recovery commands, quality checks, dashboard tech, schema_contract, Airflow helpers, or any new dependency related to dlt. Prevents commercial license traps.
---

# chumoli-dlt-boundary

Hard rule for every dlt-related decision in Chumoli.

## The rule (apply every time)

Before using any dlt feature or installing any related package:

1. Identify the package name (`pip show <package>`)
2. Search description / Requires-Dist for license, EULA, waiting list, commercial
3. If unsure — install it. If it asks for a license or fails without one, it is commercial
4. Never trust search results or marketing pages alone — verify by running the install

## FREE — use these (`pip install dlt`, Apache 2.0)

| Capability | What it does | Chumoli use |
|---|---|---|
| `rest_api_source`, `sql_database`, `filesystem` | Universal sources | connectors/rest_api, sql_database |
| Schema inference, incremental state, load packages | Core pipeline engine | pipeline_runner.py |
| `schema_contract` | Structural quality (evolve/freeze tables/columns) | Planned, not wired yet |
| CLI `dlt pipeline <name> trace` | Full last-run trace | Recovery panel |
| CLI `dlt pipeline <name> failed-jobs` | Failed jobs + error text | Recovery panel |
| CLI `dlt pipeline <name> sync` | Restore local state from destination | Recovery panel |
| CLI `dlt pipeline <name> drop <resource>` | Reset one resource state | Recovery panel |
| CLI `dlt pipeline <name> drop-pending-packages` | Clear half-loaded packages | Recovery panel |
| Automatic retry + terminal error detection | Built-in | Do not reimplement |
| `dlt.helpers.airflow_helper.PipelineTasksGroup` | Airflow task group wrapper | Scheduler / Airflow option |
| `dlt deploy <pipeline> airflow-composer` | Generates Airflow DAG | Do not rewrite — already free |

Note on `dlthub.com/products/orchestration`: the domain looks commercial, but `PipelineTasksGroup` and `dlt deploy` live in the open-source `dlt` repo. Judge by the package, not the domain name.

## COMMERCIAL — never use (`pip install dlt[hub]` → dlthub)

| Capability | Why blocked |
|---|---|
| `dlt dashboard` command | Requires dlthub + license file even on "Free tier" |
| Content quality helpers (`is_in`, `is_unique`, `is_primary_key`) | Documented as dltHub-only — implement ourselves in quality.py |
| dltHub AI Workbench | Early access / commercial |
| Advanced dltHub metrics/checks | Under development, commercial path |

Verified 2026-09-17 by actual install:

```
pip install "dlt[hub]"   # installs dlthub, not marimo
pip show dlthub          # "commercial extension... requires a license"
dlt dashboard --edit     # without hub → warning to install dlt[hub]
```

## Decision summary

- Everything inside core `dlt` package → **use it, do not rewrite**
- Anything that requires `dlt[hub]` or `dlthub` → **do not use**; write open alternative or own code
- When a new dlt version or feature appears → re-verify by install, then update this skill

## Dashboard consequence (already decided)

Do not build on `dlt dashboard` / dlthub. Dashboard is a separate UI layer that only calls:

- `registry.all_manifests()`
- `ControlStore.save()`
- `run_pipeline_by_name()`

(UI stack may be HTML or other open tools — never dlthub.)
