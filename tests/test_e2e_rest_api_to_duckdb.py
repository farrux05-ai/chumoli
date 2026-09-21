"""
End-to-end fundament testi.

Bu fayl butun zanjirni sinaydi: foydalanuvchi forma to'ldiradi (dict)
-> ConnectorManifest.validate_values() -> PipelineConfig yaratiladi
-> ControlStore.save() (encryption bilan) -> ControlStore.load()
(decryption bilan) -> pipeline_runner._execute() -> HAQIQIY dlt
pipeline -> HAQIQIY DuckDB fayliga yozish -> natijani tekshirish.

Nega bu test eng muhimi: ARCHITECTURE_DECISION.md da aytilganidek,
"agar manifest tizimi, config qatlami va credential encryption AYNAN
shular [rest_api/sql_database] ustida to'g'ri ishlamasa, Payme yoki
Click kabi custom auth sxemali connectorlarda muammoni topish ancha
qiyinlashadi". Bu test — shu tasdiqning isboti: agar bu o'tsa,
fundament ishlaydi.

Tarmoqqa chiqish yo'q (httpbin yoki tashqi API chaqirilmaydi) —
buning o'rniga `rest_api_source`ga mahalliy, static JSON qaytaruvchi
sahna (fixture server) beriladi, testni tarmoqdan mustaqil va tez
qiladi.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import duckdb
import pytest

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.core.config import DestinationConfig, PipelineConfig, QualityConfig
from chumoli.core.pipeline_runner import _execute, run_pipeline_by_name
from chumoli.security.crypto import CredentialCipher
from chumoli.store.control_store import ControlStore


class _StaticJsonHandler(BaseHTTPRequestHandler):
    """Har doim bir xil, oddiy JSON ro'yxatini qaytaradigan minimal HTTP server.

    dlt'ning rest_api_source haqiqiy HTTP so'rov yuborishini talab
    qiladi (ichida requests/httpx ishlatadi) — shuning uchun bu yerda
    mock qilingan client emas, HAQIQIY (lekin local, tarmoqdan
    mustaqil) HTTP server ishlatiladi. Bu fundament testini "haqiqiy
    dlt kodi ishlaydimi" degan savolga eng yaqin javob qiladi.
    """

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler konventsiyasi)
        payload = [
            {"id": 1, "name": "Birinchi yozuv"},
            {"id": 2, "name": "Ikkinchi yozuv"},
        ]
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass  # test chiqishini iflos qilmaslik uchun jim


@pytest.fixture
def local_json_server():
    server = HTTPServer(("127.0.0.1", 0), _StaticJsonHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join(timeout=2)


def test_full_flow_rest_api_to_duckdb(tmp_path, local_json_server, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "home"))
    # --- 0. Fundament sozlash: registry, encryption, store — hammasi tmp_path'da izolyatsiyalangan
    register_builtin_connectors()
    cipher = CredentialCipher(key_path=tmp_path / "key")
    store = ControlStore(db_path=tmp_path / "control.db", cipher=cipher)
    manifest = registry.get_manifest("rest_api")

    # --- 1. Foydalanuvchi "forma to'ldiradi" (dict, xuddi dashboard yuboradigan kabi)
    form_values = {
        "base_url": local_json_server,
        "endpoint": "/items",
        "auth_type": "none",
    }
    errors = manifest.validate_values(form_values)
    assert errors == [], f"Forma validatsiyasi kutilmagan xatolar berdi: {errors}"

    # --- 2. PipelineConfig yaratiladi — secret maydonlar source_params'da YO'Q
    duckdb_path = tmp_path / "warehouse.duckdb"
    config = PipelineConfig(
        name="e2e_test_pipeline",
        connector_key="rest_api",
        source_params={
            "base_url": form_values["base_url"],
            "endpoint": form_values["endpoint"],
            "auth_type": form_values["auth_type"],
        },
        destination=DestinationConfig(
            connector="duckdb",
            connection=str(duckdb_path),
            dataset_name="raw",
        ),
    )

    # --- 3. Saqlash (auth_type=none bo'lgani uchun secret_value bo'sh string sifatida ham qabul qilinishi kerak)
    store.save(config, raw_secrets={"secret_value": ""}, manifest=manifest)

    # --- 4. Qayta yuklash (bu yerda decrypt ham sinaladi)
    stored = store.load("e2e_test_pipeline")
    assert stored is not None
    assert stored.config.source_params["base_url"] == local_json_server

    # --- 5. HAQIQIY dlt run
    connector = registry.get("rest_api")
    result = _execute(stored, connector)

    assert result.success, f"Pipeline muvaffaqiyatsiz tugadi: {result.load_info}"
    assert result.new_rows >= 2
    assert result.col_counts.get("items", 0) >= 2
    assert result.is_first_run is True

    # --- 6. Natijani to'g'ridan-to'g'ri DuckDB'dan tekshirish — bu dlt ning
    # o'zi emas, BIZNING butun zanjirimiz to'g'ri ishlaganini isbotlaydi
    con = duckdb.connect(str(duckdb_path))
    tables = con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw'"
    ).fetchall()
    table_names = {t[0] for t in tables}
    assert "items" in table_names

    rows = con.execute("SELECT id, name FROM raw.items ORDER BY id").fetchall()
    con.close()

    assert rows == [(1, "Birinchi yozuv"), (2, "Ikkinchi yozuv")]


def test_full_flow_with_quality_checks_via_run_pipeline_by_name(tmp_path, local_json_server, monkeypatch) -> None:
    monkeypatch.setenv("CHUMOLI_HOME", str(tmp_path / "home"))
    """Same full chain as above, but through the PUBLIC entry point
    (run_pipeline_by_name, not _execute) with QualityConfig set —
    proves quality checks are actually wired into the real path a
    CLI/dashboard call takes, not just reachable via the internal
    _execute function used by the other test in this file.
    """
    register_builtin_connectors()
    cipher = CredentialCipher(key_path=tmp_path / "key")
    store = ControlStore(db_path=tmp_path / "control.db", cipher=cipher)
    manifest = registry.get_manifest("rest_api")

    config = PipelineConfig(
        name="e2e_quality_pipeline",
        connector_key="rest_api",
        source_params={
            "base_url": local_json_server,
            "endpoint": "/items",
            "auth_type": "none",
        },
        destination=DestinationConfig(
            connector="duckdb",
            connection=str(tmp_path / "quality_warehouse.duckdb"),
            dataset_name="raw",
        ),
        # The fixture server always returns exactly 2 rows (see
        # _StaticJsonHandler above) — row_count_min=2 should pass;
        # not_null_columns=["name"] should pass since both rows have names.
        quality=QualityConfig(row_count_min=2, not_null_columns=["name"]),
    )
    store.save(config, raw_secrets={"secret_value": ""}, manifest=manifest)

    result = run_pipeline_by_name("e2e_quality_pipeline", store=store)

    assert result.success
    # Regression guard: row_counts must reflect the actual destination
    # state, not an empty dict — this is exactly what silently broke
    # before (see the note in pipeline_runner._get_row_counts).
    assert result.row_counts == {"items": 2}
    assert result.quality_report.all_passed, result.quality_report.failures
    assert len(result.quality_report.outcomes) == 2  # row_count + not_null

