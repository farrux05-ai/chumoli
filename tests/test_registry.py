"""
ConnectorRegistry testlari.
"""

from __future__ import annotations

import pytest

from uzpipe.connectors.base import ConnectorRegistry
from uzpipe.core.manifest import ConnectorCategory, ConnectorManifest


class _FakeConnector:
    manifest = ConnectorManifest(
        key="fake",
        label="Fake",
        category=ConnectorCategory.UNIVERSAL,
        dlt_source_factory="dummy.path",
    )

    def build_dlt_source(self, params, secrets):
        return None


class _BrokenConnector:
    """build_dlt_source metodi yo'q — protocol'ga mos kelmasligi kerak."""

    manifest = ConnectorManifest(
        key="broken",
        label="Broken",
        category=ConnectorCategory.UNIVERSAL,
        dlt_source_factory="dummy.path",
    )


def test_register_and_get() -> None:
    registry = ConnectorRegistry()
    registry.register(_FakeConnector())

    assert registry.get("fake") is not None
    assert registry.get_manifest("fake").label == "Fake"


def test_register_duplicate_raises() -> None:
    registry = ConnectorRegistry()
    registry.register(_FakeConnector())

    with pytest.raises(ValueError, match="allaqachon"):
        registry.register(_FakeConnector())


def test_register_without_build_dlt_source_raises() -> None:
    registry = ConnectorRegistry()
    with pytest.raises(TypeError):
        registry.register(_BrokenConnector())


def test_get_unknown_connector_raises_with_helpful_message() -> None:
    registry = ConnectorRegistry()
    registry.register(_FakeConnector())

    with pytest.raises(KeyError, match="fake"):
        registry.get("does_not_exist")


def test_all_manifests_returns_manifests_not_connectors() -> None:
    registry = ConnectorRegistry()
    registry.register(_FakeConnector())

    manifests = registry.all_manifests()
    assert len(manifests) == 1
    assert isinstance(manifests[0], ConnectorManifest)


def test_builtin_sql_connectors_registered() -> None:
    """PostgreSQL, MySQL va generic sql_database bir xil build mantig'i bilan ro'yxatda."""
    from uzpipe.connectors import register_builtin_connectors
    from uzpipe.connectors.base import registry

    register_builtin_connectors()
    keys = {m.key for m in registry.all_manifests()}
    assert "postgresql" in keys
    assert "mysql" in keys
    assert "sql_database" in keys
    assert "rest_api" in keys

    pg = registry.get_manifest("postgresql")
    assert pg.label == "PostgreSQL"
    assert any(f.key == "connection_string" and f.secret for f in pg.fields)

    my = registry.get_manifest("mysql")
    assert my.label == "MySQL"
