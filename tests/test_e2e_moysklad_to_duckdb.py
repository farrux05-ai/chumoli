"""MoySklad → DuckDB, lokal mock HTTP (rasmiy {meta, rows} shakli)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import duckdb
import pytest

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.core.config import DestinationConfig, PipelineConfig
from chumoli.core.pipeline_runner import _execute
from chumoli.security.crypto import CredentialCipher
from chumoli.store.control_store import ControlStore

_PRODUCTS = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Non",
        "code": "N-1",
        "meta": {
            "href": "https://api.moysklad.ru/api/remap/1.2/entity/product/11111111-1111-1111-1111-111111111111",
            "type": "product",
        },
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "name": "Sut",
        "code": "S-1",
        "meta": {
            "href": "https://api.moysklad.ru/api/remap/1.2/entity/product/22222222-2222-2222-2222-222222222222",
            "type": "product",
        },
    },
]


class _MoySkladHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.rstrip("/") != "/entity/product":
            self.send_response(404)
            self.end_headers()
            return
        qs = parse_qs(parsed.query)
        offset = int((qs.get("offset") or ["0"])[0])
        limit = int((qs.get("limit") or ["1000"])[0])
        page = _PRODUCTS[offset : offset + limit]
        payload = {
            "meta": {
                "size": len(_PRODUCTS),
                "limit": limit,
                "offset": offset,
                "href": "http://local/entity/product",
            },
            "rows": page,
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass


@pytest.fixture
def moysklad_server():
    server = HTTPServer(("127.0.0.1", 0), _MoySkladHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join(timeout=2)


def test_full_flow_moysklad_to_duckdb(tmp_path, moysklad_server, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "home"))
    register_builtin_connectors()
    cipher = CredentialCipher(key_path=tmp_path / "key")
    store = ControlStore(db_path=tmp_path / "control.db", cipher=cipher)
    manifest = registry.get_manifest("moysklad")

    duckdb_path = tmp_path / "warehouse.duckdb"
    config = PipelineConfig(
        name="e2e_moysklad",
        connector_key="moysklad",
        source_params={
            "resources": "product",
            "from_days_ago": "7",
            "base_url": moysklad_server,
        },
        destination=DestinationConfig(
            connector="duckdb",
            connection=str(duckdb_path),
            dataset_name="raw",
        ),
    )
    store.save(config, raw_secrets={"token": "test-token"}, manifest=manifest)
    stored = store.load("e2e_moysklad")
    assert stored is not None

    result = _execute(stored, registry.get("moysklad"))
    assert result.success, result.load_info
    assert result.new_rows >= 2

    con = duckdb.connect(str(duckdb_path))
    names = {
        t[0]
        for t in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw'"
        ).fetchall()
    }
    assert "product" in names
    rows = con.execute("SELECT name FROM raw.product ORDER BY name").fetchall()
    con.close()
    assert rows == [("Non",), ("Sut",)]
