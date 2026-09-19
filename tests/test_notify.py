"""P1.1 — Telegram notify (mocked httpx)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from uzpipe.core.config import DestinationConfig, NotifyConfig, PipelineConfig
from uzpipe.core.notify import format_run_message, maybe_notify_run, send_telegram


def test_format_run_message_includes_name() -> None:
    text = format_run_message(
        pipeline_name="demo",
        success=True,
        quality_passed=True,
        row_counts={"events": 10},
        duration_seconds=1.5,
    )
    assert "demo" in text
    assert "events=10" in text


def test_send_telegram_request_shape() -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    with patch("uzpipe.core.notify.httpx.Client") as Client:
        client = Client.return_value.__enter__.return_value
        client.post.return_value = mock_resp
        send_telegram("123", "TOKEN", "hello")
        args, kwargs = client.post.call_args
        assert args[0] == "https://api.telegram.org/botTOKEN/sendMessage"
        assert kwargs["json"]["chat_id"] == "123"
        assert kwargs["json"]["text"] == "hello"


def test_notify_exception_swallowed() -> None:
    store = MagicMock()
    store.get_setting.return_value = "TOKEN"
    cfg = NotifyConfig(on_failure=True, on_success=False, telegram_chat_id="1")
    with patch("uzpipe.core.notify.send_telegram", side_effect=RuntimeError("net")):
        maybe_notify_run(
            store=store,
            notify_cfg=cfg,
            pipeline_name="p",
            success=False,
            quality_passed=False,
            row_counts={},
            error="boom",
        )


def test_run_pipeline_notify_does_not_break(monkeypatch, tmp_path) -> None:
    from uzpipe.connectors import register_builtin_connectors
    from uzpipe.connectors.base import registry
    from uzpipe.core.pipeline_runner import run_pipeline_by_name
    from uzpipe.security.crypto import CredentialCipher
    from uzpipe.store.control_store import ControlStore

    register_builtin_connectors()
    cipher = CredentialCipher(key_path=tmp_path / "k")
    store = ControlStore(db_path=tmp_path / "c.db", cipher=cipher)
    store.set_setting("telegram_bot_token", "T")
    manifest = registry.get_manifest("synthetic_volume")
    config = PipelineConfig(
        name="n1",
        connector_key="synthetic_volume",
        source_params={"row_count": "100", "batch_label": "t"},
        destination=DestinationConfig(
            connector="duckdb",
            connection=str(tmp_path / "x.duckdb"),
            dataset_name="d",
        ),
        notify=NotifyConfig(on_success=True, telegram_chat_id="99"),
    )
    store.save(config, {}, manifest)

    with patch("uzpipe.core.notify.send_telegram", side_effect=RuntimeError("down")):
        result = run_pipeline_by_name("n1", store=store)
    assert result.success is True
