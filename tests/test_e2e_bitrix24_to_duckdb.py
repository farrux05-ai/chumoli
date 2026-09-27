"""Bitrix24 → DuckDB, lokal mock webhook (crm.deal.list)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import duckdb
import pytest

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.core.config import DestinationConfig, PipelineConfig
from chumoli.core.pipeline_runner import _execute
from chumoli.security.crypto import CredentialCipher
from chumoli.store.control_store import ControlStore

_DEALS = [
    {"ID": "101", "TITLE": "Deal A", "STAGE_ID": "NEW", "OPPORTUNITY": "1000"},
    {"ID": "102", "TITLE": "Deal B", "STAGE_ID": "WON", "OPPORTUNITY": "2500"},
]


class _BitrixHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if not path.endswith("/crm.deal.list.json"):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        payload = {"result": _DEALS, "total": len(_DEALS)}
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass


@pytest.fixture
def bitrix_server():
    server = HTTPServer(("127.0.0.1", 0), _BitrixHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}/rest/1/testtoken/"
    server.shutdown()
    thread.join(timeout=2)


def test_full_flow_bitrix24_to_duckdb(tmp_path, bitrix_server, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "home"))
    register_builtin_connectors()
    cipher = CredentialCipher(key_path=tmp_path / "key")
    store = ControlStore(db_path=tmp_path / "control.db", cipher=cipher)
    manifest = registry.get_manifest("bitrix24")

    duckdb_path = tmp_path / "warehouse.duckdb"
    config = PipelineConfig(
        name="e2e_bitrix24",
        connector_key="bitrix24",
        source_params={"resources": "deals", "from_days_ago": "7"},
        destination=DestinationConfig(
            connector="duckdb",
            connection=str(duckdb_path),
            dataset_name="raw",
        ),
    )
    store.save(
        config,
        raw_secrets={"webhook_url": bitrix_server, "oauth_token": ""},
        manifest=manifest,
    )
    stored = store.load("e2e_bitrix24")
    assert stored is not None

    result = _execute(stored, registry.get("bitrix24"))
    assert result.success, result.load_info
    assert result.new_rows >= 2

    con = duckdb.connect(str(duckdb_path))
    names = {
        t[0]
        for t in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw'"
        ).fetchall()
    }
    assert "deals" in names
    rows = con.execute("SELECT TITLE FROM raw.deals ORDER BY ID").fetchall()
    con.close()
    assert rows == [("Deal A",), ("Deal B",)]
