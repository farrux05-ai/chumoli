"""P1.4 — scheduler startup errors are logged."""

import logging

from fastapi.testclient import TestClient


def test_scheduler_startup_failure_logged(monkeypatch, tmp_path, caplog) -> None:
    monkeypatch.setenv("UZPIPE_API_KEY", "k")
    monkeypatch.setenv("UZPIPE_HOME", str(tmp_path / "h"))

    import uzpipe.api.app as app_mod

    monkeypatch.setattr(app_mod, "_API_KEY", None)
    monkeypatch.setattr(
        app_mod,
        "start_scheduler",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with caplog.at_level(logging.ERROR, logger="uzpipe.api"):
        with TestClient(app_mod.app):
            pass
    assert any("scheduler_startup_failed" in r.message for r in caplog.records)
