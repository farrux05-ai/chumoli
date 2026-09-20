# Config and manifest layer

Covers: `core/manifest.py`, `core/config.py`.

## Why the manifest exists

Every connector (Payme, Click, dlt's `rest_api`, etc.) must describe
itself in one common format so the dashboard can draw a form
automatically. Without this, each new connector would require hand-
written dashboard code — by connector #6 (out of 6 remaining UZ
connectors) the dashboard code becomes unmaintainable branching logic.

`ConnectorManifest` is that common format. It carries no connection
logic — only data: field list, labels, which fields are secret, which
connector class to call. See `scalability.md` for why this specific
design scales to N connectors without touching dashboard code.

## Why `FieldType` is a closed enum

The form-rendering code (dashboard) must only ever need to know a
fixed, small set of input types: `text`, `password`, `select`,
`number`, `boolean`, `date`. If any connector author could request an
arbitrary custom widget, the dashboard would need connector-specific
rendering branches — the exact thing the manifest exists to prevent.
Adding a new `FieldType` is a deliberate, rare decision that touches
both this file and the dashboard's rendering code together.

## Why `secret: bool` is separate from `type: password`

- `type=password` controls how the UI **renders** the field (masked
  input).
- `secret=True` controls how the **storage layer** treats the value
  (must be encrypted — see `security.md`).

These are different concerns. `base_url` is `type=text, secret=False`
normally, but could be `secret=True` in an edge case (internal network
URL). Collapsing them into one flag would lose that distinction.

## Why `PipelineConfig` knows nothing about dlt

`config.py` imports nothing from `dlt`. This is intentional: config is
a pure data structure with validation, sourced from a dict (never
YAML, never a file — the user never writes YAML or code, all input
comes through form values). The translation from `PipelineConfig` +
manifest + secrets into an actual `dlt.pipeline()` call happens in
`core/pipeline_runner.py`, which is the ONLY file allowed to import
`dlt` at the orchestration level.

This separation means: if dlt's Python API changes shape, only
`pipeline_runner.py` changes. If the config schema needs a new field
(e.g. a new destination type), only `config.py` changes, and the
runner adapts without needing to know why.

## Why YAML was removed entirely (not just hidden)

Early versions of Chumoli used a `pipeline.yml` file as input. The
explicit requirement became: **the user must never write code or YAML
— every value comes from a form.** Rather than keep YAML as an
internal format that the dashboard secretly generates, `PipelineConfig`
is built directly from `dict` (originating as form values). This
avoids maintaining a YAML parser/serializer that has no user-facing
purpose anymore — one less thing to keep in sync, one less place for
bugs.

## Why `source_params` and secrets are physically separate

`PipelineConfig.source_params` never contains secret values. Secrets
are passed separately (`raw_secrets` at save-time, `secrets` at
run-time) and are enforced not to leak into `source_params` by
`ControlStore.save()` — see `security.md` for the actual enforcement
mechanism. This means a config dump (e.g. printed for debugging, or
shown in `list_all()`) is safe to display without redaction logic —
there is nothing sensitive in it by construction.
