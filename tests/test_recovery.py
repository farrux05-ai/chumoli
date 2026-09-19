"""P1.2 / R2.1 — recovery: get_failed_jobs only reports real failures (Uzbek detail)."""

from __future__ import annotations

from typing import Any

import dlt
import pytest

from uzpipe.connectors import register_builtin_connectors
from uzpipe.connectors.base import registry
from uzpipe.core.config import DestinationConfig, PipelineConfig
from uzpipe.core.pipeline_runner import get_failed_jobs, run_pipeline_by_name
from uzpipe.security.crypto import CredentialCipher
from uzpipe.store.control_store import ControlStore


def test_get_failed_jobs_empty_when_never_run(tmp_path) -> None:
    """Pipeline saqlangan, lekin hech qachon ishga tushmagan → 'none' entry."""
    register_builtin_connectors()
    cipher = CredentialCipher(key_path=tmp_path / "k")
    store = ControlStore(db_path=tmp_path / "c.db", cipher=cipher)
    manifest = registry.get_manifest("synthetic_volume")
    config = PipelineConfig(
        name="rec_never",
        connector_key="synthetic_volume",
        source_params={"row_count": "5", "batch_label": "t"},
        destination=DestinationConfig(
            connector="duckdb",
            connection=str(tmp_path / "ok.duckdb"),
            dataset_name="d",
        ),
    )
    store.save(config, {}, manifest)
    jobs = get_failed_jobs("rec_never", store=store)
    assert isinstance(jobs, list)
    assert len(jobs) == 1
    assert jobs[0]["job"] == "none"
    assert "topilmadi" in jobs[0]["detail"].lower() or "topilmadi" in jobs[0]["detail"]


def test_get_failed_jobs_after_successful_run_has_no_fake_trace(tmp_path) -> None:
    """Muvaffaqiyatli run'dan keyin 'Oxirgi ish kuzatuvi mavjud' kabi mazmunsiz qator bo'lmasin."""
    register_builtin_connectors()
    cipher = CredentialCipher(key_path=tmp_path / "k")
    store = ControlStore(db_path=tmp_path / "c.db", cipher=cipher)
    manifest = registry.get_manifest("synthetic_volume")
    config = PipelineConfig(
        name="rec_ok",
        connector_key="synthetic_volume",
        source_params={"row_count": "3", "batch_label": "ok"},
        destination=DestinationConfig(
            connector="duckdb",
            connection=str(tmp_path / "ok.duckdb"),
            dataset_name="d",
        ),
    )
    store.save(config, {}, manifest)
    result = run_pipeline_by_name("rec_ok", store=store)
    assert result.success is True

    jobs = get_failed_jobs("rec_ok", store=store)
    assert isinstance(jobs, list)
    # faqat 'none' yoki bo'sh — last_trace mavjudligi uchun soxta entry yo'q
    for j in jobs:
        assert "Oxirgi ish kuzatuvi" not in j["detail"]
        assert "last_trace" not in j["job"]
    assert any(j["job"] == "none" for j in jobs) or len(jobs) == 0


def test_get_failed_jobs_reports_real_failure_uzbek(tmp_path, monkeypatch) -> None:
    """Haqiqiy extract failure: get_failed_jobs mazmunli o'zbekcha detail qaytaradi.

    Connector source'ini majburan RuntimeError chiqaradigan resource bilan
    almashtiramiz — bu real pipeline.run() → PipelineStepFailed → last_trace
    step_exception yo'lini ishlatadi (taxmin emas).
    """
    register_builtin_connectors()
    cipher = CredentialCipher(key_path=tmp_path / "k")
    store = ControlStore(db_path=tmp_path / "c.db", cipher=cipher)
    manifest = registry.get_manifest("synthetic_volume")
    config = PipelineConfig(
        name="rec_fail",
        connector_key="synthetic_volume",
        source_params={"row_count": "10", "batch_label": "fail"},
        destination=DestinationConfig(
            connector="duckdb",
            connection=str(tmp_path / "fail.duckdb"),
            dataset_name="d",
        ),
    )
    store.save(config, {}, manifest)

    connector = registry.get("synthetic_volume")
    original_build = connector.build_dlt_source

    def _failing_source(params: dict[str, Any], secrets: dict[str, Any]):
        @dlt.resource(name="forced_fail")
        def _boom():
            raise RuntimeError(
                "UZPIPE_TEST_FORCED_FAILURE: connection refused / destination unreachable"
            )
            yield {"id": 1}  # pragma: no cover

        return _boom

    monkeypatch.setattr(connector, "build_dlt_source", _failing_source)

    with pytest.raises(Exception):
        # dlt PipelineStepFailed ko'tariladi
        run_pipeline_by_name("rec_fail", store=store)

    # restore not strictly needed (test ends) but keep isolation
    monkeypatch.setattr(connector, "build_dlt_source", original_build)

    jobs = get_failed_jobs("rec_fail", store=store)
    assert isinstance(jobs, list)
    assert len(jobs) >= 1
    # 'none' fallback bo'lmasligi kerak
    assert not any(j.get("job") == "none" for j in jobs)

    details = " ".join(j["detail"] for j in jobs).lower()
    # o'zbekcha bosqich yorlig'i
    assert "bosqichida xato" in details or "extract" in details
    # haqiqiy xato matni
    assert "uzpipe_test_forced_failure" in details or "connection refused" in details
    # eski soxta qator yo'q
    assert "oxirgi ish kuzatuvi mavjud" not in details
