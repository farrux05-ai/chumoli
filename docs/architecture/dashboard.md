# Dashboard strategy

Covers: the yet-to-be-built dashboard layer (Layer 4 in `overview.md`).

## Current decision: build on `marimo`, from scratch, no dlt-branded code

The dashboard is built using [`marimo`](https://marimo.io) (PyPI:
`marimo`) — an independent, Apache 2.0, license-free reactive notebook
library with no relationship to dlt or dltHub. We write the dashboard
code ourselves, the same way we'd use any other UI library.

It calls exactly three functions from the layers below it (see
`overview.md`):
- `registry.all_manifests()` — to draw the connector selection form
- `ControlStore.save()` — to persist a new/edited pipeline
- `run_pipeline_by_name()` — to trigger a run

A fourth area — "Recover" — wraps dlt's CLI recovery commands (`trace`,
`failed-jobs`, `sync`, `drop`, `drop-pending-packages`; all confirmed
free in `dlt-boundary.md`) behind simple buttons, translated to
Uzbek, so a non-technical user doesn't need to know which command
solves which failure mode.

## Why this decision, and the mistake that preceded it (kept for the record)

**This section stays in the docs on purpose.** The point isn't to
hide that a wrong turn happened — it's to make sure nobody re-makes
the same mistake by trusting a search result over actually running
the command.

### What was originally planned (WRONG)

The first plan was: `dlt dashboard --edit` ejects dlt's own official
dashboard code (assumed to be Marimo-based, Apache 2.0, hackable) into
the project folder, then translate it to Uzbek and extend it with a
UZ-connector form. This was based on reading search results and dlt
documentation pages, not on running the command.

### What was actually found (verified by running the command)

```
$ dlt dashboard --edit
WARNING: Install dlt[hub] for workspace dashboard and mcp support

$ pip install "dlt[hub]"
# installs: dlthub-0.30.0, dlthub-client-0.28.4  (NOT marimo)

$ pip show dlthub
# PyPI description: "dlthub is a commercial extension to dlt...
#  dlthub requires a license to be used, please join our waiting
#  list to get one."
```

`dlt dashboard` is not part of dlt's open-source package. It requires
`dlthub`, a **separate, commercial, EULA-bound package** — even its
"Free tier" requires a license file and a waiting-list signup, per
dltHub's own documentation. Paid tiers start at $1,190/month.

### Why this mattered enough to reverse course

UzPipe's own positioning (`docs/original-positioning/POSITIONING.md`)
explicitly lists Airbyte's "$1000+/month enterprise pricing" as a
weakness to compete against. Building the dashboard on `dlthub` would
have made UzPipe dependent on the exact kind of commercial licensing
gate it was positioned to avoid.

### The fix

Dashboard rebuilt from scratch on `marimo` directly — verified
license-free by installing it (`pip install marimo` — no license
prompt, no waiting list, Apache 2.0). dlt itself (the engine, sources,
CLI recovery tools, Airflow helper) is still used in full — nothing
about "don't rewrite what dlt does" changed. Only "where the dashboard
UI code comes from" changed.

### The process lesson (now enforced, see `dlt-boundary.md`)

Any external library/tool must be verified by actually installing it
and checking for license prompts, before being adopted — not by
trusting documentation phrasing or a search result summary. This rule
is now explicit in `dlt-boundary.md`.

## Planned dashboard sections (not yet built)

1. **Connector picker** — cards per manifest category (`uz_payment`,
   `uz_gov`, `uz_erp`, `universal`), form auto-rendered from
   `FieldSpec` list.
2. **Pipeline list** — from `ControlStore.list_all()`, no secrets shown.
3. **Run monitor** — triggers `run_pipeline_by_name()`, shows
   `RunResult.row_counts` and success/failure.
4. **Recover panel** — appears only when a run failed; offers
   "Retry" / "Sync from destination" / "Reset this table only" as
   plain-Uzbek buttons, each mapped to one dlt CLI command
   underneath.

`marimo` itself provides the reactive UI primitives (forms, tables,
buttons) — no HTML/CSS/JS is hand-written, consistent with the earlier
decision to avoid a separate frontend framework (React/Vue were ruled
out specifically because `marimo`'s Python-native reactivity covers
the same interactivity need without that overhead).
