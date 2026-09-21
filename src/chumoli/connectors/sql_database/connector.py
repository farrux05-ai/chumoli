"""
chumoli.connectors.sql_database.connector
===========================================

dlt'ning tayyor `sql_database` source'i ustidagi yupqa adapterlar.

Strategiya (docs/strategy/chumoli-connector-strategy.md):
  - Ichki dlt source bir xil: `sql_database`
  - Foydalanuvchi UI da alohida kartochkalar ko'radi:
      PostgreSQL, MySQL, SQL Database (generic)
  - Bu "sifat > son" va "user-facing names" qoidalariga mos.

NEGA UCHTA ALOHIDA MANIFEST, BITTA build MANTIG'I
----------------------------------------------------
PostgreSQL va MySQL uchun placeholder, help matni va label farq
qiladi — forma tajribasi yaxshilanadi. Lekin `build_dlt_source`
100% bir xil (SQLAlchemy connection string). Shuning uchun
umumiy `_build_sql_database_source` yordamchi funksiyasi bor;
har bir connector klassi faqat o'z `manifest`ini olib yuradi.

Generic `sql_database` SQLite / MSSQL / Oracle va testlar uchun
qoldirilgan — katalogni "to'ldirish" uchun emas, balki haqiqiy
ehtiyoj (masalan lokal SQLite dump) uchun.
"""
