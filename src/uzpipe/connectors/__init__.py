"""
uzpipe.connectors
====================

Bu paketning `register_builtin_connectors()` funksiyasi — butun
tizimda connectorlarni import qiladigan YAGONA joy.

NEGA IMPORTLAR FUNKSIYA ICHIDA, MODUL DARAJASIDA EMAS
-----------------------------------------------------------
Agar barcha connector modullari `uzpipe.connectors` paketi import
qilinganda darhol yuklansa, bu ikkita muammo keltirib chiqaradi:
  1. Har bir connector o'z bog'liqliklarini talab qiladi (masalan
     sql_database uchun DB drayverlar) — ular hatto ishlatilmasa ham
     import xatosi berishi mumkin.
  2. Test yozishda faqat bitta connectorni tekshirish uchun
     boshqalarini ham yuklashga majbur bo'lasiz.

Funksiya sifatida saqlash CLI/dashboard ishga tushganda ANIQ bir
marta, ANIQ shu yerda chaqirilishini ta'minlaydi — import vaqti va
"ro'yxatdan o'tkazish" vaqti ataylab ajratilgan.
"""

from __future__ import annotations

from uzpipe.connectors.base import registry


def register_builtin_connectors() -> None:
    """dlt bilan bevosita keladigan universal connectorlarni ro'yxatga oladi.

    UZ connectorlar (Payme, Click, 1C, Didox, Soliq, MyGov) shu yerga
    xuddi shu naqsh bilan qo'shiladi.
    Har biri qo'shilganda BU FUNKSIYAGA bitta import + bitta register()
    qatori qo'shiladi, boshqa hech narsa o'zgarmaydi.

    SQL tomoni: PostgreSQL va MySQL — asosiy UI kartochkalar;
    sql_database — generic (SQLite/MSSQL/Oracle + testlar).
    """
    from uzpipe.connectors.rest_api.connector import RestApiConnector
    from uzpipe.connectors.sql_database.connector import (
        MySQLConnector,
        PostgreSQLConnector,
        SqlDatabaseConnector,
    )

    # Takroriy chaqiruvlarda xato bermaslik uchun (masalan test'larda
    # bir nechta marta chaqirilsa) — registry allaqachon to'ldirilgan
    # bo'lsa, jimgina qaytamiz.
    already_registered = {m.key for m in registry.all_manifests()}

    if "rest_api" not in already_registered:
        registry.register(RestApiConnector())
    if "postgresql" not in already_registered:
        registry.register(PostgreSQLConnector())
    if "mysql" not in already_registered:
        registry.register(MySQLConnector())
    if "sql_database" not in already_registered:
        registry.register(SqlDatabaseConnector())
