# Chumoli Skills (for AI + humans)

Each skill is a **procedure**. Follow steps in order. Do not invent extra layers.

| Skill | When to use |
|-------|-------------|
| [write-connector](write-connector.md) | New source connector |
| [add-destination](add-destination.md) | Expose another dlt destination |
| [change-api-or-ui](change-api-or-ui.md) | FastAPI route or dashboard HTML |
| [run-and-test](run-and-test.md) | Verify before push |
| [architecture](../architecture/ARCHITECTURE.md) | Which layer owns the change |

## Global rules

1. Read `docs/status.md` and `AGENTS.md` first.
2. One concern per commit.
3. No `dlt[hub]`.
4. Secrets never in logs or plain config_json.
5. `PYTHONPATH=src python -m pytest tests/ -q` must pass.
