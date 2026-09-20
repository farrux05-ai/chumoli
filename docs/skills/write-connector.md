# Skill: write a connector

**Goal:** L3 connector in dashboard + dlt run.

**Do not** edit dashboard, ControlStore, or pipeline_runner unless manifest contract is broken.

## 0. Wrap dlt or custom HTTP?

| Case | Approach | Template |
|------|----------|----------|
| REST + bearer/api_key | `rest_api_source` | `rest_api/connector.py` |
| SQLAlchemy URL | `sql_database` | `sql_database/connector.py` |
| Custom auth (HMAC, JSON-RPC) | `@dlt.resource` + httpx | `payme_uz/`, `click_uz/` |

Only add if real need or rest_api cannot express auth.

## 1. Folder

```
src/chumoli/connectors/<key>/
  __init__.py
  connector.py   # MANIFEST + class
```

## 2. Manifest

```python
MANIFEST = ConnectorManifest(
    key="example_uz",
    label="Example",
    category=ConnectorCategory.UZ_PAYMENT,
    description="...",
    dlt_source_factory="chumoli.connectors.example_uz.connector.ExampleConnector",
    fields=[
        FieldSpec(key="api_key", label="API key", type=FieldType.PASSWORD, required=True, secret=True),
    ],
)
```

- Every credential = FieldSpec; secrets → `secret=True`
- SELECT → must set `options=`

## 3. Class

```python
class ExampleConnector:
    manifest = MANIFEST
    def build_dlt_source(self, params: dict, secrets: dict[str, str]):
        # keep params and secrets separate
        return source_or_resource
```

## 4. Register in `connectors/__init__.py` only two lines.

## 5. Tests without live network.

## Anti-patterns

- Heavy abstract base with 5 methods
- YAML connector files
- Merging secrets into params for storage
- dltHub dependency
