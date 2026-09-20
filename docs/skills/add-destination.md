# Skill: add a destination

**Goal:** expose a dlt built-in destination in API + UI.

## 1. Confirm dlt supports it

Name must match dlt destination id. Add pip extra if needed.

## 2. Catalog — `src/chumoli/core/destinations.py`

```python
DestinationSpec(
    key="postgresql",
    label="PostgreSQL",
    needs_connection=True,
    connection_placeholder="postgresql://...",
)
```

Only add if UZ market needs it.

## 3. Storage already encrypts connection as `_destination_connection`.

## 4. API/UI auto from catalog — no hardcoded select list.

## 5. Test catalog key + no plaintext password in config_json.
