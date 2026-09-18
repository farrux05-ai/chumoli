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
