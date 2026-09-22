"""Bundled sample data for frictionless first run (SQL → DuckDB, REST → DuckDB).

Demo is the product face: data is prepared on disk once, then demos only load
(pyarrow). Generation never blocks the "impressive" path after first ensure.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Bump when sample schema/size changes — forces one-time rebuild of sample_orders.db
_SAMPLE_SQL_VERSION = "v2_100k"
_SAMPLE_ORDERS = 100_000
_SAMPLE_CUSTOMERS = 5_000


def examples_dir() -> Path:
    from chumoli.core.paths import examples_dir as _examples_dir, ensure_runtime_dirs

    ensure_runtime_dirs()
    return _examples_dir()


def sample_sqlite_path() -> Path:
    """Ensure examples/sample_orders.db exists with demo rows (100k orders).

    First call may take a few seconds to build; later demos only read the file.
    """
    path = examples_dir() / "sample_orders.db"
    marker = examples_dir() / f".sample_orders.{_SAMPLE_SQL_VERSION}"
    if path.is_file() and path.stat().st_size > 0 and marker.is_file():
        return path

    # Rebuild (old 500-row file or missing)
    if path.is_file():
        path.unlink(missing_ok=True)

    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode=OFF")
        conn.execute("PRAGMA synchronous=OFF")
        conn.executescript(
            """
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                customer TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT NOT NULL
            );
            """
        )
        cities = ["Toshkent", "Samarqand", "Buxoro", "Namangan", "Andijon", "Farg'ona", "Nukus"]
        customers = [
            (i, f"Mijoz {i}", cities[i % len(cities)])
            for i in range(1, _SAMPLE_CUSTOMERS + 1)
        ]
        conn.executemany("INSERT INTO customers VALUES (?,?,?)", customers)

        statuses = ["paid", "pending", "cancelled", "refunded"]
        chunk = 10_000
        for start in range(1, _SAMPLE_ORDERS + 1, chunk):
            end = min(start + chunk, _SAMPLE_ORDERS + 1)
            orders = [
                (
                    i,
                    f"Mijoz {((i - 1) % _SAMPLE_CUSTOMERS) + 1}",
                    round(10.0 + (i % 97) * 1.35, 2),
                    statuses[i % 4],
                    f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}T{(i % 24):02d}:00:00",
                )
                for i in range(start, end)
            ]
            conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", orders)
        conn.commit()
    finally:
        conn.close()

    marker.write_text(_SAMPLE_SQL_VERSION, encoding="utf-8")
    return path


def sample_sqlite_url() -> str:
    """Absolute sqlite URL (3 slashes + absolute path)."""
    p = sample_sqlite_path().resolve()
    return f"sqlite:///{p}"


def ensure_volume_parquet(row_count: int, batch_label: str = "demo") -> Path:
    """Pre-build examples/volume_{n}.parquet once; demos only read it (pyarrow)."""
    n = max(1, min(int(row_count), 2_000_000))
    path = examples_dir() / f"volume_{n}.parquet"
    if path.is_file() and path.stat().st_size > 1000:
        return path

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as e:
        raise ImportError(
            'Volume demo uchun pyarrow kerak. pip install "pyarrow>=14.0"'
        ) from e

    from datetime import UTC, datetime, timedelta

    base = datetime.now(UTC)
    chunk = 50_000
    writer = None
    schema = pa.schema(
        [
            ("event_id", pa.int64()),
            ("batch", pa.string()),
            ("user_id", pa.int64()),
            ("amount", pa.float64()),
            ("status", pa.string()),
            ("ts", pa.string()),
        ]
    )
    try:
        for start in range(0, n, chunk):
            end = min(start + chunk, n)
            size = end - start
            ids = list(range(start, end))
            table = pa.table(
                {
                    "event_id": ids,
                    "batch": [batch_label] * size,
                    "user_id": [i % 10_000 for i in ids],
                    "amount": [(i % 500) + 0.01 for i in ids],
                    "status": ["ok" if i % 17 else "retry" for i in ids],
                    "ts": [
                        (base - timedelta(seconds=i % 86_400)).isoformat() for i in ids
                    ],
                },
                schema=schema,
            )
            if writer is None:
                writer = pq.ParquetWriter(str(path), schema, compression="zstd")
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()
    return path


def friendly_db_error(exc: BaseException) -> str:
    """Map common DB/API failures to short Uzbek guidance (no secrets)."""
    msg = str(exc)
    low = msg.lower()
    if "unable to open database file" in low:
        return (
            "SQLite fayl ochilmadi. To'liq yo'l yozing, masalan "
            "sqlite:////home/user/data/orders.db — fayl borligini tekshiring. "
            "Yoki Settings da CHUMOLI_HOME ni tekshiring."
        )
    if "pyarrow" in low:
        return (
            'PyArrow o\'rnatilmagan. Tez SQL/Volume demo uchun: '
            'pip install "pyarrow>=14.0"'
        )
    if "could not translate host" in low or "name or service not known" in low:
        return "Host topilmadi — connection string dagi host nomini tekshiring."
    if "password authentication failed" in low or "access denied" in low:
        return "Login/parol noto'g'ri — connection string dagi credentials ni tekshiring."
    if "connection refused" in low:
        return "Ulanish rad etildi — DB ishlayotganini va portni tekshiring."
    if "timeout" in low:
        return "Ulanish vaqti tugadi — tarmoq yoki firewall ni tekshiring."
    return msg[:400] if msg else "Noma'lum xato"
