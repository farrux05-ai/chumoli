"""P0.1 — API key auth on /api/* (health excluded)."""

from __future__ import annotations


import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch, tmp_path):
    key = "test-secret-key-abc"
    monkeypatch.setenv("CHUMOLI_API_KEY", key)
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "home"))

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

    with TestClient(app_mod.app) as c:
        yield c, key


def test_health_without_key(client) -> None:
    c, _key = client
    r = c.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_pipelines_missing_key_401(client) -> None:
    c, _key = client
    r = c.get("/api/pipelines")
    assert r.status_code == 401


def test_pipelines_wrong_key_401(client) -> None:
    c, _key = client
    r = c.get("/api/pipelines", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_pipelines_correct_key_200(client) -> None:
    c, key = client
    r = c.get("/api/pipelines", headers={"X-API-Key": key})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_bearer_token_accepted(client) -> None:
    c, key = client
    r = c.get("/api/connectors", headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 200
