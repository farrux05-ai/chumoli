"""P0.3 — FastAPI layer coverage (TestClient + tmp_path stores)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from chumoli.connectors import register_builtin_connectors


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
    key = "test-api-key-p03"
    monkeypatch.setenv("CHUMOLI_API_KEY", key)
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "uzhome"))

    import chumoli.api.app as app_mod

    monkeypatch.setattr(app_mod, "_API_KEY", None)

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


def test_health_ok(api) -> None:
    c, key, _ = api
    r = c.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_connectors_include_v1(api) -> None:
    c, key, _ = api
    r = c.get("/api/connectors", headers=_h(key))
    assert r.status_code == 200
    keys = {x["key"] for x in r.json()}
    for needed in (
        "rest_api",
        "sql_database",
        "click_uz",
        "payme_uz",
        "uzum_market",
        "synthetic_volume",
    ):
        assert needed in keys


def test_create_and_get_pipeline_no_secret_values(api) -> None:
    c, key, _ = api
    body = {
        "name": "p_rest",
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
    r = c.post("/api/pipelines", headers=_h(key), json=body)
    assert r.status_code == 201, r.text
    g = c.get("/api/pipelines/p_rest", headers=_h(key))
    assert g.status_code == 200
    data = g.json()
    assert data["name"] == "p_rest"
    assert "secret_keys" in data


def test_create_missing_required_422(api) -> None:
    c, key, _ = api
    body = {
        "name": "bad",
        "connector_key": "rest_api",
        "source_params": {"auth_type": "none"},
        "secrets": {},
        "destination": {"connector": "duckdb", "dataset_name": "raw"},
    }
    r = c.post("/api/pipelines", headers=_h(key), json=body)
    assert r.status_code == 422


def test_create_unknown_destination_400(api) -> None:
    c, key, _ = api
    body = {
        "name": "bad_dest",
        "connector_key": "rest_api",
        "source_params": {
            "base_url": "https://example.com",
            "endpoint": "/",
            "auth_type": "none",
        },
        "secrets": {},
        "destination": {"connector": "not_a_real_dest", "dataset_name": "raw"},
    }
    r = c.post("/api/pipelines", headers=_h(key), json=body)
    assert r.status_code == 400


def test_secret_in_source_params_422(api) -> None:
    c, key, _ = api
    body = {
        "name": "leak",
        "connector_key": "rest_api",
        "source_params": {
            "base_url": "https://example.com",
            "endpoint": "/",
            "auth_type": "api_key",
            "secret_value": "should-not-be-here",
        },
        "secrets": {},
        "destination": {"connector": "duckdb", "dataset_name": "raw"},
    }
    r = c.post("/api/pipelines", headers=_h(key), json=body)
    assert r.status_code == 422
    assert "secret_value" in str(r.json())


def test_run_pipeline_local_json(api, local_json_server) -> None:
    c, key, tmp_path = api
    duck = str(tmp_path / "out.duckdb")
    body = {
        "name": "run_me",
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
    r = c.post("/api/pipelines/run_me/run", headers=_h(key))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["success"] is True


def test_delete_then_get_404(api) -> None:
    c, key, _ = api
    body = {
        "name": "to_delete",
        "connector_key": "rest_api",
        "source_params": {
            "base_url": "https://example.com",
            "endpoint": "/",
            "auth_type": "none",
        },
        "secrets": {},
        "destination": {"connector": "duckdb", "dataset_name": "raw"},
    }
    assert c.post("/api/pipelines", headers=_h(key), json=body).status_code == 201
    assert c.delete("/api/pipelines/to_delete", headers=_h(key)).status_code == 200
    assert c.get("/api/pipelines/to_delete", headers=_h(key)).status_code == 404


def test_destinations_catalog(api) -> None:
    c, key, _ = api
    r = c.get("/api/destinations", headers=_h(key))
    assert r.status_code == 200
    keys = {x["key"] for x in r.json()}
    assert {"duckdb", "postgresql", "filesystem", "clickhouse"} <= keys


def test_create_with_notify_and_schedule(api) -> None:
    c, key, _ = api
    body = {
        "name": "p_notify",
        "connector_key": "rest_api",
        "source_params": {
            "base_url": "https://example.com",
            "endpoint": "/items",
            "auth_type": "none",
        },
        "secrets": {},
        "destination": {"connector": "duckdb", "dataset_name": "raw"},
        "write_disposition": "replace",
        "schedule": {"kind": "manual"},
        "quality": {"row_count_min": 1},
        "notify": {
            "on_failure": True,
            "on_success": False,
            "telegram_chat_id": "12345",
        },
    }
    r = c.post("/api/pipelines", headers=_h(key), json=body)
    assert r.status_code == 201, r.text
    g = c.get("/api/pipelines/p_notify", headers=_h(key))
    assert g.status_code == 200
    cfg = g.json()["config"]
    assert cfg["notify"]["telegram_chat_id"] == "12345"
    assert cfg["quality"]["row_count_min"] == 1


def test_telegram_settings_encrypted_round_trip(api) -> None:
    c, key, tmp_path = api
    r = c.get("/api/settings/telegram", headers=_h(key))
    assert r.status_code == 200
    assert r.json()["configured"] is False
    put = c.put(
        "/api/settings/telegram",
        headers=_h(key),
        json={"bot_token": "tok-secret-xyz"},
    )
    assert put.status_code == 200
    assert put.json()["configured"] is True
    again = c.get("/api/settings/telegram", headers=_h(key))
    assert again.json()["configured"] is True
    # token itself never returned
    assert "tok-secret-xyz" not in again.text


def test_saved_destinations_crud(api) -> None:
    c, key, tmp_path = api
    r = c.get("/api/destinations/saved", headers=_h(key))
    assert r.status_code == 200
    assert r.json() == []

    create = c.post(
        "/api/destinations/saved",
        headers=_h(key),
        json={
            "label": "Prod PG",
            "connector": "postgresql",
            "connection": "postgresql://u:secret@h/db",
            "dataset_name": "wh",
        },
    )
    assert create.status_code == 201
    dest_id = create.json()["id"]

    listed = c.get("/api/destinations/saved", headers=_h(key)).json()
    assert len(listed) == 1
    assert listed[0]["label"] == "Prod PG"
    assert "connection" not in listed[0]
    assert "secret" not in create.text.lower()

    # use saved dest when creating pipeline
    pipe = c.post(
        "/api/pipelines",
        headers=_h(key),
        json={
            "name": "via_saved",
            "connector_key": "synthetic_volume",
            "source_params": {"row_count": "10000", "batch_label": "t"},
            "secrets": {},
            "saved_destination_id": dest_id,
            "destination": {"connector": "duckdb", "dataset_name": "ignored"},
        },
    )
    assert pipe.status_code == 201, pipe.text

    deleted = c.delete(f"/api/destinations/saved/{dest_id}", headers=_h(key))
    assert deleted.status_code == 200
    assert c.get("/api/destinations/saved", headers=_h(key)).json() == []


def test_sql_inspect_endpoint(api, tmp_path) -> None:
    from sqlalchemy import create_engine, text

    c, key, _ = api
    db = tmp_path / "inspect_src.db"
    eng = create_engine(f"sqlite:///{db}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE alpha (id INT)"))
        conn.execute(text("CREATE TABLE beta (id INT)"))
    eng.dispose()

    r = c.post(
        "/api/connectors/sql_database/inspect",
        headers=_h(key),
        json={"connection_string": f"sqlite:///{db}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["tables"]) >= {"alpha", "beta"}
    assert body["count"] >= 2

    bad = c.post(
        "/api/connectors/sql_database/inspect",
        headers=_h(key),
        json={"connection_string": ""},
    )
    assert bad.status_code == 422
