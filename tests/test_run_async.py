"""P0 hardening — background run endpoint + constant-time API key compare."""

from __future__ import annotations

import json
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from chumoli.connectors import register_builtin_connectors
from chumoli.security.api_key import keys_match


class _StaticJsonHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        payload = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass


@pytest.fixture()
def local_json_server():
    server = HTTPServer(("127.0.0.1", 0), _StaticJsonHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join(timeout=2)


@pytest.fixture()
def api(monkeypatch, tmp_path):
    key = "test-api-key-async"
    monkeypatch.setenv("CHUMOLI_API_KEY", key)
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "uzhome"))

    import chumoli.api.app as app_mod

    monkeypatch.setattr(app_mod, "_API_KEY", None)
    monkeypatch.setattr(app_mod, "_RUN_JOBS", {})

    from chumoli.security.crypto import CredentialCipher
    from chumoli.store.control_store import ControlStore
    from chumoli.store.run_store import RunStore

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


def test_keys_match_constant_time() -> None:
    assert keys_match("abc123", "abc123") is True
    assert keys_match("abc123", "abc124") is False
    assert keys_match("", "abc124") is False


def test_run_async_returns_run_id_and_completes(api, local_json_server) -> None:
    c, key, tmp_path = api
    duck = str(tmp_path / "out.duckdb")
    body = {
        "name": "run_async_me",
        "connector_key": "rest_api",
        "source_params": {
            "base_url": local_json_server,
            "endpoint": "/",
            "auth_type": "none",
        },
        "secrets": {},
        "destination": {
            "connector": "duckdb",
            "connection": duck,
            "dataset_name": "raw",
        },
        "write_disposition": "replace",
    }
    assert c.post("/api/pipelines", headers=_h(key), json=body).status_code == 201

    started = c.post("/api/pipelines/run_async_me/run/async", headers=_h(key))
    assert started.status_code == 200, started.text
    run_id = started.json()["run_id"]
    assert started.json()["status"] in ("queued", "running", "done")

    deadline = time.time() + 10
    status = None
    while time.time() < deadline:
        r = c.get(f"/api/runs/jobs/{run_id}", headers=_h(key))
        assert r.status_code == 200
        status = r.json()
        if status["status"] in ("done", "error"):
            break
        time.sleep(0.05)

    assert status is not None
    assert status["status"] == "done", status
    assert status["result"]["success"] is True


def test_run_async_unknown_pipeline_404(api) -> None:
    c, key, _ = api
    r = c.post("/api/pipelines/does_not_exist/run/async", headers=_h(key))
    assert r.status_code == 404


def test_run_job_status_unknown_id_404(api) -> None:
    c, key, _ = api
    r = c.get("/api/runs/jobs/not-a-real-job-id", headers=_h(key))
    assert r.status_code == 404
