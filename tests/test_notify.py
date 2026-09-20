"""P1.1 — Telegram notify (mocked httpx)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from chumoli.core.config import DestinationConfig, NotifyConfig, PipelineConfig
from chumoli.core.notify import format_run_message, maybe_notify_run, send_telegram


def test_format_run_message_success_clear() -> None:
    text = format_run_message(
        pipeline_name="rest_test",
        success=True,
        quality_passed=True,
        row_counts={"posts": 100, "users": 30},
        duration_seconds=2.7,
    )
    assert "rest_test" in text
    assert "Chumoli" in text
    assert "Muvaffaqiyatli" in text
    assert "130" in text  # total
    assert "posts" in text and "100" in text
    assert "users" in text and "30" in text
    assert "2.7" in text
    assert "✅" in text


def test_format_run_message_fail() -> None:
    text = format_run_message(
        pipeline_name="broken",
        success=False,
        quality_passed=False,
        row_counts={},
        error="connection refused",
        duration_seconds=0.4,
    )
    assert "❌" in text
    assert "Xato" in text
    assert "connection refused" in text
    assert "400 ms" in text or "0.4" in text


def test_format_run_message_quality() -> None:
    text = format_run_message(
        pipeline_name="q",
        success=True,
        quality_passed=False,
        row_counts={"t": 5},
        quality_details=[{"passed": False, "detail": "nulls > 10%"}],
    )
    assert "⚠️" in text
    assert "Quality" in text
    assert "nulls" in text


def test_send_telegram_request_shape() -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    with patch("chumoli.core.notify.httpx.Client") as Client:
        client = Client.return_value.__enter__.return_value
        client.post.return_value = mock_resp
        send_telegram("123", "TOKEN", "hello")
        args, kwargs = client.post.call_args
        assert args[0] == "https://api.telegram.org/botTOKEN/sendMessage"
        assert kwargs["json"]["chat_id"] == "123"
        assert kwargs["json"]["text"] == "hello"
        assert kwargs["json"]["parse_mode"] == "HTML"


def test_notify_exception_swallowed() -> None:
    store = MagicMock()
    store.get_setting.return_value = "TOKEN"
    cfg = NotifyConfig(on_failure=True, on_success=False, telegram_chat_id="1")
    with patch("chumoli.core.notify.send_telegram", side_effect=RuntimeError("net")):
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
    from chumoli.connectors import register_builtin_connectors
    from chumoli.connectors.base import registry
    from chumoli.core.pipeline_runner import run_pipeline_by_name
    from chumoli.security.crypto import CredentialCipher
    from chumoli.store.control_store import ControlStore

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

    with patch("chumoli.core.notify.send_telegram", side_effect=RuntimeError("down")):
        result = run_pipeline_by_name("n1", store=store)
    assert result.success is True
