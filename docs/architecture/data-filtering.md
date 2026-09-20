# Data filtering vs quality checks

## The confusion

UI had **“Minimum qator soni”** next to pipeline settings. That looks like
a filter (“only load min…max rows”). It is **not**.

| Concern | When | What it does |
|---------|------|----------------|
| **Extract filter** | *Before / during* load | Which rows leave the source |
| **Quality check** | *After* load | Did the result meet expectations? |

`row_count_min` = quality only (“at least N rows arrived”).  
Time windows (“from May 2016”) = extract filter.

## Extract filters (by connector family)

### SQL (PostgreSQL / MySQL / SQL Database)

1. **`cursor_column`** — e.g. `updated_at`, `created_at`, or numeric id.  
2. **`cursor_initial_value`** — first-run lower bound, e.g. `2016-05-01`.  

Implementation: dlt `sql_table(..., incremental=incremental(cursor, initial_value=…))`.

- First run: load rows with cursor **≥ initial_value** (time filter).  
- Later runs: continue from last stored cursor (incremental).  
- No cursor: full table every time (replace/append as configured).

There is **no** generic min/max row id filter in the UI — wrong abstraction
for business questions like “from May 2016”.

### Click / Payme (and similar APIs)

- **`from_days_ago`** — relative window (“last N days”).  
- Absolute calendar start is less common in those APIs; relative fits their
  list endpoints. Do not force SQL-style initial dates onto them.

### REST (generic)

- No universal time filter: every API uses different query params.  
- Advanced users put params in endpoint/query; dedicated connectors later.

## Quality checks (unchanged role)

- `row_count_min` — fail if too few rows  
- `not_null_columns`, `no_duplicates_key`  
- `freshness_*` — “is the newest row too old?” (SLA), still not a source filter  

Default `row_count_min=1` when empty remains a safety net against silent empty loads.

## Product rule

> Users ask **when** (from date) more often than **how many rows**.  
> Put time on the **source** step; put counts on **quality**.

## Files

- `connectors/sql_database/connector.py` — `cursor_initial_value` + parser  
- `core/quality.py` — post-load checks only  
- Dashboard step 3 (tables) — cursor + start value; step 4 — quality labels  
