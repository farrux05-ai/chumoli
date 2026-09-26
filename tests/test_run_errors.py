"""Run failure handling: sanitization, persistence, and API surfacing.

Covers the production guarantee that a failed run is (a) recorded in run
history with a reason and (b) never leaks credentials into that reason.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from chumoli.connectors import register_builtin_connectors
from chumoli.core.errors import friendly_error, sanitize_error
from chumoli.core.pipeline_runner import record_run_failure, record_run_result
from chumoli.store.run_store import RunStore

# ── sanitize_error ────────────────────────────────────────────────


def test_sanitize_error_redacts_url_password() -> None:
    out = sanitize_error("connect failed: postgresql://admin:s3cr3t@db:5432/prod")
    assert "s3cr3t" not in out
    assert "postgresql://admin:***@db:5432/prod" in out


def test_sanitize_error_redacts_password_with_at_sign() -> None:
    out = sanitize_error("postgresql://user:p@ss@host/db")
    assert "p@ss" not in out
    assert "postgresql://user:***@host/db" in out


def test_sanitize_error_redacts_bearer_and_kv() -> None:
    assert "eyJhbGci" not in sanitize_error("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.x.y")
    assert "hunter2" not in sanitize_error("password=hunter2 rejected")
    assert "sk-live-123" not in sanitize_error("api_key: sk-live-123")


def test_sanitize_error_keeps_safe_text() -> None:
    # auth_type is not a secret key — must not be mangled
    assert sanitize_error("auth_type: none is invalid") == "auth_type: none is invalid"
    assert sanitize_error("OperationalError: connection refused") == (
        "OperationalError: connection refused"
    )


def test_sanitize_error_bounds_length() -> None:
    out = sanitize_error("x" * 5000, max_len=100)
    assert len(out) <= 100
    assert out.endswith("…")


def test_friendly_error_redacts_and_maps() -> None:
    out = friendly_error(RuntimeError("postgresql://u:pw@h/db connection refused"))
    assert "pw" not in out
    assert "Ulanish rad etildi" in out  # mapped to Uzbek guidance


# ── record_run_result / record_run_failure ────────────────────────


class _FakeResult:
    """Minimal stand-in for RunResult (avoids a real dlt run in unit tests)."""

    pipeline_name = "p1"
    success = False
    row_counts: dict[str, int] = {}
    new_rows = 0
    col_counts: dict[str, int] = {}
    schema_changes: list[str] = []
    cursor_last_value = None
    is_first_run = True
    duration_seconds = 0.0
    total_rows = 0
    rows_per_second = 0.0
    peak_memory_mb = 0.0
    error = "load failed: postgresql://u:pw@h/db"
    quality_report = SimpleNamespace(all_passed=False, outcomes=[])


def test_record_run_failure_persists_and_redacts(tmp_path) -> None:
    runs = RunStore(db_path=tmp_path / "runs.db")
    record_run_failure(runs, "p1", RuntimeError("boom: token=abc123"), trigger="manual")
    rows = runs.list_recent(limit=5)
    assert len(rows) == 1
    assert rows[0]["success"] is False
    assert rows[0]["trigger"] == "manual"
    assert "abc123" not in (rows[0]["error"] or "")
    assert "token=***" in rows[0]["error"]


def test_record_run_result_persists_error(tmp_path) -> None:
    runs = RunStore(db_path=tmp_path / "runs.db")
    record_run_result(runs, _FakeResult(), trigger="manual")
    rows = runs.list_recent(limit=5)
    assert len(rows) == 1
    assert rows[0]["success"] is False
    assert "pw" not in (rows[0]["error"] or "")
    assert "postgresql://u:***@h/db" in rows[0]["error"]


# ── API: failures are recorded, not just toasted ──────────────────


@pytest.fixture()
def api(monkeypatch, tmp_path):
    key = "test-api-key-errors"
    monkeypatch.setenv("CHUMOLI_API_KEY", key)
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "uzhome"))

    import chumoli.api.app as app_mod

    monkeypatch.setattr(app_mod, "_API_KEY", None)
    monkeypatch.setattr(app_mod, "_RUN_JOBS", {})

    from chumoli.security.crypto import CredentialCipher
    from chumoli.store.control_store import ControlStore

    cipher = CredentialCipher(key_path=tmp_path / "master.key")
    store = ControlStore(db_path=tmp_path / "control.db", cipher=cipher)
    runs = RunStore(db_path=tmp_path / "runs.db")
    monkeypatch.setattr(app_mod, "_store", lambda: store)
    monkeypatch.setattr(app_mod, "_runs", lambda: runs)

    register_builtin_connectors()

    with TestClient(app_mod.app) as client:
        yield client, key, tmp_path


def _h(key: str) -> dict[str, str]:
    return {"X-API-Key": key}


def test_sync_run_failure_recorded_and_redacted(api, monkeypatch) -> None:
    c, key, _ = api
    import chumoli.api.app as app_mod

    def boom(*_a, **_k):
        raise RuntimeError("connect failed: postgresql://admin:s3cr3t@db:5432/prod")

    monkeypatch.setattr(app_mod, "run_pipeline_by_name", boom)

    r = c.post("/api/pipelines/ghost/run", headers=_h(key))
    assert r.status_code == 500
    assert "s3cr3t" not in r.text  # response is redacted too

    runs = c.get("/api/runs", headers=_h(key)).json()
    assert len(runs) == 1
    row = runs[0]
    assert row["pipeline_name"] == "ghost"
    assert row["success"] is False
    assert row["trigger"] == "manual"
    assert "s3cr3t" not in (row["error"] or "")
    assert "postgresql://admin:***@db:5432/prod" in row["error"]


def test_async_run_failure_recorded_and_redacted(api, monkeypatch) -> None:
    c, key, _ = api
    import chumoli.api.app as app_mod

    # Async endpoint requires the pipeline to exist before it enqueues.
    body = {
        "name": "ghost",
        "connector_key": "rest_api",
        "source_params": {
            "base_url": "https://example.com",
            "endpoint": "/items",
            "auth_type": "none",
        },
        "secrets": {},
        "destination": {"connector": "duckdb", "dataset_name": "raw"},
        "write_disposition": "replace",
    }
    assert c.post("/api/pipelines", headers=_h(key), json=body).status_code == 201

    def boom(*_a, **_k):
        raise RuntimeError("boom: token=abc123secret")

    monkeypatch.setattr(app_mod, "run_pipeline_by_name", boom)

    started = c.post("/api/pipelines/ghost/run/async", headers=_h(key))
    assert started.status_code == 200
    run_id = started.json()["run_id"]

    deadline = time.time() + 10
    job = None
    while time.time() < deadline:
        job = c.get(f"/api/runs/jobs/{run_id}", headers=_h(key)).json()
        if job["status"] in ("done", "error"):
            break
        time.sleep(0.05)

    assert job is not None and job["status"] == "error"
    assert "abc123secret" not in (job["error"] or "")

    runs = c.get("/api/runs", headers=_h(key)).json()
    assert len(runs) == 1
    assert runs[0]["success"] is False
    assert runs[0]["trigger"] == "manual-async"
    assert "abc123secret" not in (runs[0]["error"] or "")


def test_already_running_not_recorded_as_failure(api, monkeypatch) -> None:
    """409 (already running) is not a run failure — must not pollute history."""
    c, key, _ = api
    import chumoli.api.app as app_mod
    from chumoli.core.pipeline_runner import PipelineAlreadyRunning

    def busy(*_a, **_k):
        raise PipelineAlreadyRunning("already running")

    monkeypatch.setattr(app_mod, "run_pipeline_by_name", busy)

    r = c.post("/api/pipelines/ghost/run", headers=_h(key))
    assert r.status_code == 409
    assert c.get("/api/runs", headers=_h(key)).json() == []
