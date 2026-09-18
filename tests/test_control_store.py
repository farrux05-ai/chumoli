"""
ControlStore testlari.

Eng muhim test bu faylda `test_save_rejects_secret_leaked_in_source_params`
— bu ARCHITECTURE_DECISION.md 3.3 bandida va control_store.py da
tasvirlangan himoya qatlamini tekshiradi: agar kimdir chaqiruv
tartibini buzib, maxfiy qiymatni oddiy source_params ichiga qo'ysa,
save() buni RAD ETISHI SHART, jimgina saqlab qo'ymasligi kerak.
"""

from __future__ import annotations

import pytest

from uzpipe.core.config import DestinationConfig, PipelineConfig
from uzpipe.core.manifest import ConnectorCategory, ConnectorManifest, FieldSpec, FieldType
from uzpipe.security.crypto import CredentialCipher
from uzpipe.store.control_store import ControlStore

TEST_MANIFEST = ConnectorManifest(
    key="test_connector",
    label="Test",
    category=ConnectorCategory.UNIVERSAL,
    dlt_source_factory="dummy.path",
    fields=[
        FieldSpec(key="base_url", label="URL", secret=False),
        FieldSpec(key="api_key", label="Key", type=FieldType.PASSWORD, secret=True),
    ],
)


def _make_store(tmp_path) -> ControlStore:
    cipher = CredentialCipher(key_path=tmp_path / "key")
    return ControlStore(db_path=tmp_path / "control.db", cipher=cipher)


def _make_config(**overrides) -> PipelineConfig:
    defaults = dict(
        name="test_pipeline",
        connector_key="test_connector",
        source_params={"base_url": "https://example.com"},
        destination=DestinationConfig(connector="duckdb"),
    )
    defaults.update(overrides)
    return PipelineConfig(**defaults)


def test_save_and_load_round_trip(tmp_path) -> None:
    store = _make_store(tmp_path)
    config = _make_config()

    store.save(config, raw_secrets={"api_key": "sk_test_123"}, manifest=TEST_MANIFEST)
    loaded = store.load("test_pipeline")

    assert loaded is not None
    assert loaded.config.name == "test_pipeline"
    assert loaded.config.source_params == {"base_url": "https://example.com"}
    assert loaded.secrets == {"api_key": "sk_test_123"}


def test_save_rejects_secret_leaked_in_source_params(tmp_path) -> None:
    """Xavfsizlik invarianti: secret maydon source_params ichida bo'lsa, save() rad etishi shart."""
    store = _make_store(tmp_path)
    config = _make_config(source_params={"base_url": "https://x.com", "api_key": "leaked!"})

    with pytest.raises(ValueError, match="Maxfiy maydonlar"):
        store.save(config, raw_secrets={"api_key": "sk_test_123"}, manifest=TEST_MANIFEST)


def test_save_rejects_missing_required_secret(tmp_path) -> None:
    store = _make_store(tmp_path)
    config = _make_config()

    with pytest.raises(ValueError, match="yetishmayapti"):
        store.save(config, raw_secrets={}, manifest=TEST_MANIFEST)


def test_list_all_never_returns_secrets(tmp_path) -> None:
    """list_all() natijasida hech qanday shifrlangan yoki ochiq secret bo'lmasligi kerak."""
    store = _make_store(tmp_path)
    config = _make_config()
    store.save(config, raw_secrets={"api_key": "sk_test_123"}, manifest=TEST_MANIFEST)

    rows = store.list_all()
    assert len(rows) == 1
    serialized = str(rows[0])
    assert "sk_test_123" not in serialized
    assert "api_key" not in rows[0]["config"].get("source_params", {})


def test_load_missing_pipeline_returns_none(tmp_path) -> None:
    store = _make_store(tmp_path)
    assert store.load("does_not_exist") is None


def test_save_is_idempotent_upsert(tmp_path) -> None:
    """Bir xil nom bilan ikkinchi marta save() qilinsa, yangilanishi kerak, xato emas."""
    store = _make_store(tmp_path)
    config_v1 = _make_config()
    store.save(config_v1, raw_secrets={"api_key": "v1_key"}, manifest=TEST_MANIFEST)

    config_v2 = _make_config(source_params={"base_url": "https://updated.com"})
    store.save(config_v2, raw_secrets={"api_key": "v2_key"}, manifest=TEST_MANIFEST)

    loaded = store.load("test_pipeline")
    assert loaded.config.source_params["base_url"] == "https://updated.com"
    assert loaded.secrets["api_key"] == "v2_key"
    assert len(store.list_all()) == 1


def test_delete_removes_pipeline(tmp_path) -> None:
    store = _make_store(tmp_path)
    store.save(_make_config(), raw_secrets={"api_key": "sk"}, manifest=TEST_MANIFEST)

    store.delete("test_pipeline")
    assert store.load("test_pipeline") is None
