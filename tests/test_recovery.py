"""P1.2 — recovery helpers return Uzbek-friendly details."""

from __future__ import annotations

from uzpipe.connectors import register_builtin_connectors
from uzpipe.connectors.base import registry
from uzpipe.core.config import DestinationConfig, PipelineConfig
from uzpipe.core.pipeline_runner import get_failed_jobs
from uzpipe.security.crypto import CredentialCipher
from uzpipe.store.control_store import ControlStore


def test_get_failed_jobs_returns_list(tmp_path) -> None:
    register_builtin_connectors()
    cipher = CredentialCipher(key_path=tmp_path / "k")
    store = ControlStore(db_path=tmp_path / "c.db", cipher=cipher)
    manifest = registry.get_manifest("synthetic_volume")
    config = PipelineConfig(
        name="rec1",
        connector_key="synthetic_volume",
        source_params={"row_count": "10", "batch_label": "t"},
        destination=DestinationConfig(
            connector="duckdb",
            connection=str(tmp_path / "ok.duckdb"),
            dataset_name="d",
        ),
    )
    store.save(config, {}, manifest)
    jobs = get_failed_jobs("rec1", store=store)
    assert isinstance(jobs, list)
    assert len(jobs) >= 1
    assert "detail" in jobs[0]
