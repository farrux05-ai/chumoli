# Skill: add a destination

**Goal:** expose a dlt built-in destination in API + UI.

## 1. Confirm dlt supports it

Check `dir(dlt.destinations)` for the real attribute name. Add pip extra if needed
(e.g. `pip install "dlt[clickhouse]"`).

## 2. Catalog — `src/chumoli/core/destinations.py`

```python
DestinationSpec(
    key="postgresql",  # UI/catalog key (stable for saved pipelines)
    label="PostgreSQL",
    needs_connection=True,
    connection_placeholder="postgresql://...",
)
```

If catalog key ≠ dlt attribute (e.g. `postgresql` → `postgres`), add an entry to
`_DLT_DEST_ALIASES` in `pipeline_runner.py`. Do not change existing catalog keys.

Only add if UZ market needs it.

## 3. Storage already encrypts connection as `_destination_connection`.

## 4. API/UI auto from catalog — no hardcoded select list.

## 5. Test catalog key + no plaintext password in config_json.
