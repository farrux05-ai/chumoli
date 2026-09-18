# Scalability: why this holds at N connectors

This is the answer to "does this architecture survive growth, or does
it fall apart at connector #10, #20, #50?" — checked explicitly
because the person building this asked for a design that stays light
and doesn't accumulate debt as UZ connectors (Payme, Click, 1C, Didox,
Soliq, MyGov, and whatever comes after) are added one by one.

## The one rule that makes this work

**Adding a connector touches exactly two new files and one existing
file by exactly two lines.** Nothing else. See
[`connector-skill.md`](connector-skill.md) for the literal steps.

```
connectors/<name>/manifest.py     # NEW — field list, labels, category
connectors/<name>/connector.py    # NEW — build_dlt_source() implementation
connectors/__init__.py            # +2 lines — import + registry.register(...)
```

## Where scalability could have broken, and how each was avoided

| Risk | What would have happened without the fix | The fix |
|---|---|---|
| Dashboard hardcodes each connector's form | Dashboard code grows an if/elif per connector; connector #6 makes it unmaintainable | Manifest-driven forms — dashboard reads `FieldSpec` lists generically, never named connector logic (`config-and-manifest.md`) |
| Each connector needs its own secret-handling code | Copy-pasted encryption logic per connector, inconsistent | `ControlStore` + `CredentialCipher` handle ALL connectors identically, driven by `manifest.secret_keys()` (`security.md`) |
| Auth schemes differ wildly (Payme JSON-RPC + header auth, Click HMAC-SHA1, 1C Basic/OData) | Registry or config layer would need to special-case each auth type | Auth logic lives entirely inside each connector's own `build_dlt_source()` — the registry and config layers never inspect *how* a connector authenticates, only that it returns a valid `DltSource` |
| New DB migration needed per connector (different secret fields) | `ALTER TABLE` per connector, schema churn | Secrets stored as one JSON blob column; manifest (not DB schema) defines which keys exist (`security.md`) |
| Registering a connector wrong (e.g. missing `build_dlt_source`) fails silently at runtime | Bug discovered only when a user tries to run that pipeline | `ConnectorRegistry.register()` checks protocol conformance at import time — `TypeError` raised immediately, not at first use |
| Connector needs pagination/rate-limiting/retry logic | Would require UzPipe to reimplement these per connector | For `rest_api`-shaped connectors, dlt's `rest_api_source` already handles pagination/auth types — the connector adapter stays a few lines (see `rest_api/connector.py`). Custom-auth UZ connectors (Payme, Click) still delegate retry/backoff to dlt's pipeline execution layer, only authentication is connector-specific |

## Why `BaseUZConnector` is a `Protocol`, not an abstract base class

A `Protocol` (structural typing) means a connector author only needs
to provide a `manifest` attribute and a `build_dlt_source()` method —
no forced inheritance chain, no coupling to a specific class
hierarchy. This matters most for the two dlt-builtin-backed
connectors (`rest_api`, `sql_database`): they are thin adapters
around dlt's own source factories and should not be shoehorned into
inheriting from some UzPipe-specific base class that dlt knows
nothing about.

## Why the registry rejects duplicate keys at registration time

If two connectors accidentally both registered as `"payme_uz"`, this
would silently overwrite one connector's manifest with another's —
a bug that would be very hard to trace (the dashboard would show one
connector's form but might invoke the other's `build_dlt_source`,
depending on registration order). Failing loudly at import time turns
this into a five-second fix instead of a confusing runtime mystery.

## What does NOT scale automatically (known, deliberate limits)

- **`sql_database`'s single cursor column across multiple selected
  tables** (documented in `connectors/sql_database/connector.py`) —
  if a user needs different incremental columns per table, they must
  create separate pipelines. This was a deliberate simplicity-over-
  completeness tradeoff for the connector form, not a scalability gap
  in the core architecture.
- **One credential set per pipeline (1:1)** — if a future connector
  genuinely needs multiple, separate credential scopes (e.g. OAuth
  refresh token + API key), this would need a small `ControlStore`
  schema extension. Not currently needed by any planned connector, so
  not built preemptively (YAGNI) — but noted here so it isn't a
  surprise later.

## The test that proves the architecture, not just the code

The two end-to-end tests
(`test_e2e_rest_api_to_duckdb.py`, `test_e2e_sql_database_to_duckdb.py`)
exist specifically to validate the FULL path — manifest validation →
config → encryption → SQLite → real dlt run → real destination —
before any UZ-specific connector was written. The reasoning: if the
foundation doesn't work end-to-end on dlt's own most battle-tested
sources, a failure in a custom-auth connector (Payme, Click) would be
much harder to isolate to "our code" vs. "dlt itself." Every new
connector is expected to add its own such test, following the same
pattern.
