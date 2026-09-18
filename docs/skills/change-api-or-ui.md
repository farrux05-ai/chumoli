# Skill: change API or UI

## API (`api/app.py`)

- HTTP ↔ registry, ControlStore, RunStore, run_pipeline_by_name, scheduler
- No extract/load business logic; no returning secrets

## UI (`static/index.html`)

- Data only via `/api/*`
- Forms from manifest.fields
- Uzbek apostrophes break JS single quotes — use double quotes
- Optional CONNECTOR_ORDER for sort only
