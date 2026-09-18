# UzPipe — Agent / Contributor Instructions

Read this first. Then open only the doc you need. Do not invent scope.

## What this is

**UzPipe** — lightweight EL tool for Uzbekistan. Built on **dlt** (Apache 2.0).  
Moat: local connectors (Payme, Click, 1C, Didox…), not a 500-connector catalog.  
Dashboard: **HTML** (not marimo, not dltHub dashboard).

Repo: `farrux05-ai/uzpipe` (private).

## Read in this order

| Order | File | When |
|-------|------|------|
| 1 | `docs/status.md` (or project status) | What exists / what does not |
| 2 | `uzpipe-connector-strategy.md` | Which connectors, open core, priority |
| 3 | `uzpipe-api-maintenance.md` | How we detect API drift and open issues |
| 4 | `uzpipe-dlt-boundary` skill / dlt-boundary doc | Free dlt vs commercial dltHub |
| 5 | `docs/architecture/*` | Layer map, only if changing structure |

Original positioning lives under `docs/original-positioning/` — historical, not day-to-day rules.

## Architecture (do not blur layers)

```
Layer 4  Dashboard (HTML)     → only calls: all_manifests, ControlStore.save, run_pipeline_by_name
Layer 3  Connectors           → thin adapters → dlt sources (UZ + universal)
Layer 2  Control plane        → PipelineConfig, ControlStore, Fernet secrets
Layer 1  dlt                  → use as-is; never rewrite engine features
```

- New feature → pick **one** layer from the table in architecture overview.
- Dashboard must not import dlt internals.
- Connectors must keep `params` and `secrets` separate in `build_dlt_source`.

## Hard rules

1. **No dltHub / `dlt[hub]` / `dlt dashboard`.** Commercial license trap. Verify new deps by install, not by blog posts.
2. **Quality over count.** Write a connector only if: real client need **or** repeated UZ demand **or** cannot be done with plain `rest_api`/`sql_database`.
3. **User-facing names:** PostgreSQL, MySQL, REST API, Filesystem — not internal `sql_database` as the product name.
4. **Open core:** core DB/REST/filesystem free; UZ payment/ERP connectors are commercial value (stability + support).
5. **Maintenance:** prefer monitor → GitHub issue → fix. Do not assume vendors publish OpenAPI (Payme/Click often do not).
6. **Secrets:** never log or snapshot values; schema/shape only in monitors.

## How to work

- **Code:** match existing package layout under `src/uzpipe/`.
- **Tests:** extend pytest patterns already in `tests/` (e2e against DuckDB where possible).
- **Git:** small commits; push to `uzpipe` when asked. Prefer issue-linked changes for connector breakage.
- **Claude / other AI:** may be changing dashboard or foundation in parallel — do not overwrite their WIP without checking status. Prefer additive, tested changes.
- **This chat (Grok):** strategy, maintenance design, dlt boundary, connector priority, GitHub ops, coding when tasked.

## Do not

- Add catalog connectors “for completeness.”
- Depend on commercial dltHub features.
- Put business logic in the HTML dashboard beyond calling the three entry points.
- Merge `params` and `secrets` into one dict inside connectors.
- Use production merchant keys in CI monitors — sandbox only.

## Quick pointers

- Connector writing procedure (when foundation is stable): project `docs/connector-skill.md`.
- Strategy artifacts in this workspace: `uzpipe-connector-strategy.md`, `uzpipe-api-maintenance.md`, `uzpipe-dlt-boundary-SKILL.md`.
- UI reference: `elt-console-mvp(2).html` (MVP shell; wire to backend later).

---

*Keep this file short. Update when a rule changes; put long reasoning in strategy/architecture docs.*
