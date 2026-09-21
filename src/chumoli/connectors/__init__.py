"""
chumoli.connectors
====================

Bu paketning `register_builtin_connectors()` funksiyasi — butun
tizimda connectorlarni import qiladigan YAGONA joy.
"""

from __future__ import annotations

from chumoli.connectors.base import registry


def register_builtin_connectors() -> None:
    """Universal + UZ payment/gov connectorlarni ro'yxatga oladi."""
    from chumoli.connectors.click_uz.connector import ClickConnector
    from chumoli.connectors.didox.connector import DidoxConnector
    from chumoli.connectors.payme_uz.connector import PaymeConnector
    from chumoli.connectors.rest_api.connector import RestApiConnector
    from chumoli.connectors.sql_database.connector import (
        MySQLConnector,
        PostgreSQLConnector,
        SqlDatabaseConnector,
    )
    from chumoli.connectors.uzum_market.connector import UzumMarketConnector
    from chumoli.connectors.synthetic_volume.connector import SyntheticVolumeConnector

    already_registered = {m.key for m in registry.all_manifests()}

    builtins = [
        ("rest_api", RestApiConnector),
        ("postgresql", PostgreSQLConnector),
        ("mysql", MySQLConnector),
        ("sql_database", SqlDatabaseConnector),
        ("click_uz", ClickConnector),
        ("payme_uz", PaymeConnector),
        ("uzum_market", UzumMarketConnector),
        ("didox", DidoxConnector),
        ("synthetic_volume", SyntheticVolumeConnector),
    ]
    for key, cls in builtins:
        if key not in already_registered:
            registry.register(cls())
