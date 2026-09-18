# UzPipe — Agent Instructions

Read this first. Then open **one** skill. Do not invent scope.

## Product

**UzPipe** — lightweight EL for Uzbekistan on **dlt** (Apache 2.0).
Moat: UZ connectors. UI: static HTML + FastAPI.
Repo: `farrux05-ai/uzpipe`.

## Read order

1. `docs/status.md`
2. `docs/architecture/ARCHITECTURE.md`
3. `docs/skills/README.md`
4. Specific skill

## Layers

```
L4 HTML → L3 connectors → L2 control plane → L1 dlt
```

## Hard rules

1. No dltHub / `dlt[hub]`
2. Quality over count
3. params ≠ secrets in build_dlt_source
4. Dashboard does not import dlt
5. Secrets never logged

## Skills

| Task | File |
|------|------|
| New connector | `docs/skills/write-connector.md` |
| Destination | `docs/skills/add-destination.md` |
| API/UI | `docs/skills/change-api-or-ui.md` |
| Test | `docs/skills/run-and-test.md` |

```bash
PYTHONPATH=src python -m pytest tests/ -q
```
