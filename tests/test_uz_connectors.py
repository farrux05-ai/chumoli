"""UZ payment connectorlar — manifest va auth (live API yo'q)."""

from __future__ import annotations

import base64
import hashlib

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.connectors.click_uz.connector import _build_auth_header
from chumoli.connectors.payme_uz.connector import _auth_header


def test_uz_connectors_registered() -> None:
    register_builtin_connectors()
    keys = {m.key for m in registry.all_manifests()}
    assert {"click_uz", "payme_uz", "uzum_market"} <= keys

    for key, label in (
        ("click_uz", "Click"),
        ("payme_uz", "Payme"),
        ("uzum_market", "Uzum Market"),
    ):
        m = registry.get_manifest(key)
        assert m.label == label
        assert m.category.value == "uz_payment"
        assert any(f.secret for f in m.fields)


def test_click_auth_header_shape() -> None:
    header = _build_auth_header("svc1", "secret", timestamp="1700000000")
    parts = header.split(":")
    assert len(parts) == 3
    assert parts[0] == "svc1"
    assert parts[2] == "1700000000"
    expected = hashlib.sha1(b"1700000000secret").hexdigest()
    assert parts[1] == expected


def test_payme_auth_header_base64() -> None:
    h = _auth_header("mid", "key")
    assert base64.b64decode(h).decode() == "mid:key"


def test_click_manifest_validate() -> None:
    register_builtin_connectors()
    m = registry.get_manifest("click_uz")
    errors = m.validate_values(
        {
            "service_id": "1",
            "secret_key": "sk",
            "resources": "payments",
        }
    )
    assert errors == []


def test_payme_manifest_validate() -> None:
    register_builtin_connectors()
    m = registry.get_manifest("payme_uz")
    errors = m.validate_values(
        {
            "merchant_id": "m1",
            "api_key": "k1",
            "sandbox": "false",
        }
    )
    assert errors == []


def test_uzum_manifest_validate() -> None:
    register_builtin_connectors()
    m = registry.get_manifest("uzum_market")
    errors = m.validate_values({"api_key": "tok", "resources": "orders"})
    assert errors == []


def test_build_dlt_source_returns_without_network() -> None:
    """build_dlt_source faqat source/resource obyektini yasaydi — HTTP yo'q."""
    register_builtin_connectors()
    for key, secrets, params in (
        (
            "click_uz",
            {"secret_key": "sk"},
            {"service_id": "1", "resources": "payments", "from_days_ago": "1"},
        ),
        (
            "payme_uz",
            {"api_key": "k"},
            {"merchant_id": "m", "sandbox": "true", "from_days_ago": "1"},
        ),
        (
            "uzum_market",
            {"api_key": "tok"},
            {"resources": "orders", "from_days_ago": "1"},
        ),
    ):
        src = registry.get(key).build_dlt_source(params, secrets)
        assert src is not None
