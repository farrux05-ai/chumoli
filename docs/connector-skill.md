# Skill: writing a new Chumoli connector

Follow this exactly when adding a new connector (Payme, Click, 1C,
Didox, Soliq, MyGov, or anything after). This is the practical
checklist; the reasoning behind each rule is in
[`scalability.md`](architecture/scalability.md) and
[`config-and-manifest.md`](architecture/config-and-manifest.md) — read
those once, then use this file as the repeatable procedure.

## Before you start

Read [`architecture/dlt-boundary.md`](architecture/dlt-boundary.md)
first. If the source you're connecting to can be reached through dlt's
`rest_api_source` (most REST APIs with standard pagination/auth can),
prefer wrapping that over writing raw HTTP calls — check the `rest_api`
connector first as your template. Only write custom request logic
(like Payme's JSON-RPC or Click's HMAC-SHA1) when dlt's built-in
sources genuinely can't express the auth scheme.

## Step 1: create the folder

```
src/chumoli/connectors/<name>/
├── __init__.py       # empty
├── manifest.py        # or inline in connector.py — see existing examples
└── connector.py
```

Naming: lowercase, matches the connector key used everywhere
(`payme_uz`, `click_uz`, etc.) — matches the pattern in
`docs/original-positioning/ROADMAP.md`'s connector table.

## Step 2: write the manifest

```python
from chumoli.core.manifest import (
    ConnectorCategory, ConnectorManifest, FieldSpec, FieldType, SelectOption,
)

MANIFEST = ConnectorManifest(
    key="your_connector_key",
    label="Human-readable name shown in the dashboard",
    category=ConnectorCategory.UZ_PAYMENT,  # or UZ_GOV, UZ_ERP, UNIVERSAL
    description="One line, in Uzbek, describing what this connects to",
    dlt_source_factory="chumoli.connectors.<name>.connector.<ClassName>",
    fields=[
        FieldSpec(key="merchant_id", label="Merchant ID", type=FieldType.TEXT, required=True),
        FieldSpec(key="api_key", label="API key", type=FieldType.PASSWORD, required=True, secret=True),
        # ... one FieldSpec per credential/config value the user must supply
    ],
)
```

Rules (all enforced by `ConnectorManifest`'s own validation, see
`core/manifest.py`):
- Every value the connector needs (URLs, IDs, keys, tokens) becomes
  one `FieldSpec` — nothing is hardcoded in the connector class.
- Anything that should be encrypted at rest (API keys, passwords,
  tokens, connection strings) gets `secret=True`. This is not optional
  — it's what `ControlStore` uses to decide what to encrypt
  (`security.md`).
- `FieldType.SELECT` fields must include `options`.
- Labels and `description` are in Uzbek — this is what the
  non-technical dashboard user sees.

## Step 3: write the connector class

```python
from typing import Any
from chumoli.connectors.base import BaseUZConnector

class YourConnector:
    manifest = MANIFEST  # class attribute, not set in __init__

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        # params  = non-secret FieldSpec values (from PipelineConfig.source_params)
        # secrets = secret FieldSpec values, already decrypted (from ControlStore.load())
        #
        # Return anything dlt.pipeline().run() accepts: a DltSource,
        # a dlt.resource, a plain iterable of dicts, etc.
        ...
```

The one hard rule: **`params` and `secrets` must never be merged into
one dict inside this method before being handed to dlt.** Keep reading
them from their separate arguments throughout — this keeps the origin
of every value traceable, which is what let `ControlStore.save()`'s
leak check catch mistakes automatically (`security.md`).

If wrapping dlt's `rest_api_source`, follow `rest_api/connector.py` as
the template: build a `source_config` dict matching dlt's expected
shape, pass it to `rest_api_source(source_config)`, return the result.
Do not reimplement pagination or retry logic — dlt's source already
does this.

If writing raw request logic (custom auth like HMAC or JSON-RPC), wrap
it as a `@dlt.resource` generator function and return that — dlt still
handles schema inference, state, and load packages for you; only the
HTTP request/auth logic is yours to write.

## Step 4: register it

In `src/chumoli/connectors/__init__.py`, inside
`register_builtin_connectors()`:

```python
from chumoli.connectors.<name>.connector import YourConnector
# ...
if "your_connector_key" not in already_registered:
    registry.register(YourConnector())
```

That's the entire change to this shared file — two lines. If you find
yourself editing more than this in `__init__.py`, or editing the
dashboard code, or editing `control_store.py`, stop — something about
the new connector is breaking the manifest contract, and the fix
belongs in the manifest/connector files, not in shared code. Re-read
`scalability.md`.

## Step 5: write the end-to-end test

Every connector needs its own version of
`tests/test_e2e_rest_api_to_duckdb.py` / `test_e2e_sql_database_to_duckdb.py`:
form values → `manifest.validate_values()` → `PipelineConfig` →
`ControlStore.save()` → `ControlStore.load()` → `_execute()` → assert
against the actual destination table.

For connectors hitting a real external API (Payme, Click, etc.), this
test needs either:
- A local mock HTTP server (see `_StaticJsonHandler` pattern in
  `test_e2e_rest_api_to_duckdb.py`) if the API's request/response shape
  is simple enough to fake, or
- A sandbox/test-mode credential if the provider offers one (common
  for payment gateways) — document which env var or fixture supplies
  it, don't hardcode real credentials anywhere in the test.

Run `python -m pytest tests/ -v` and confirm the full suite still
passes before considering the connector done — this includes every
prior connector's tests, not just the new one, since the shared
registry/store code is exercised by all of them together.

## Checklist summary

- [ ] `connectors/<name>/manifest.py` — fields, labels, category, all in Uzbek
- [ ] `connectors/<name>/connector.py` — `manifest` attribute + `build_dlt_source()`
- [ ] `connectors/__init__.py` — 2 lines added (import + register)
- [ ] `tests/test_e2e_<name>_to_duckdb.py` — full round trip, real destination assertion
- [ ] `python -m pytest tests/ -v` — full suite green
- [ ] No dashboard file touched
- [ ] No `control_store.py` or `crypto.py` file touched
