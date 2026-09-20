"""Bundled sample data for frictionless first run (SQL → DuckDB, REST → DuckDB)."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def examples_dir() -> Path:
    from chumoli.core.paths import examples_dir as _examples_dir, ensure_runtime_dirs
    ensure_runtime_dirs()
    return _examples_dir()


def sample_sqlite_path() -> Path:
    """Ensure ~/.chumoli/examples/sample_orders.db exists with demo rows."""
    path = examples_dir() / "sample_orders.db"
    if path.is_file() and path.stat().st_size > 0:
        return path

    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                customer TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT NOT NULL
            );
            """
        )
        customers = [
            (i, f"Mijoz {i}", city)
            for i, city in enumerate(
                ["Toshkent", "Samarqand", "Buxoro", "Namangan", "Andijon"] * 40, start=1
            )
        ]
        conn.executemany("INSERT OR REPLACE INTO customers VALUES (?,?,?)", customers)
        statuses = ["paid", "pending", "cancelled", "refunded"]
        orders = [
            (
                i,
                f"Mijoz {(i % 200) + 1}",
                round(10.0 + (i % 97) * 1.35, 2),
                statuses[i % 4],
                f"2026-01-{(i % 28) + 1:02d}T10:00:00",
            )
            for i in range(1, 501)
        ]
        conn.executemany("INSERT OR REPLACE INTO orders VALUES (?,?,?,?,?)", orders)
        conn.commit()
    finally:
        conn.close()
    return path


def sample_sqlite_url() -> str:
    """Absolute sqlite URL (4 slashes after scheme for absolute path)."""
    p = sample_sqlite_path().resolve()
    return f"sqlite:///{p}"


def friendly_db_error(exc: BaseException) -> str:
    """Map common DB/API failures to short Uzbek guidance (no secrets)."""
    msg = str(exc)
    low = msg.lower()
    if "unable to open database file" in low:
        return (
            "SQLite fayl ochilmadi. To'liq yo'l yozing, masalan "
            "sqlite:////home/user/data/orders.db — fayl borligini tekshiring. "
            "Yoki Settings → «Namuna SQL» tugmasini bosing."
        )
    if "password authentication failed" in low or "access denied" in low:
        return "Login yoki parol noto'g'ri. Connection stringni tekshiring."
    if "could not connect" in low or "connection refused" in low:
        return "Serverga ulanib bo'lmadi. Host, port va tarmoqni tekshiring."
    if "name or service not known" in low or "nodename nor servname" in low:
        return "Host nomi topilmadi. URL yoki hostname noto'g'ri."
    if "401" in msg or "unauthorized" in low:
        return "API autentifikatsiya xatosi (401). Token/API keyni tekshiring."
    if "404" in msg:
        return "Endpoint topilmadi (404). Base URL va yo'lni tekshiring."
    if "unboundcolumn" in low or "did not receive any data" in low:
        return (
            "Primary key ustuni bu yuklamada yo'q yoki bo'sh. "
            "Write disposition ni 'replace' qiling yoki primary key ni olib tashlang. "
            "Keyin Tiklash → 'Kutayotgan paketlarni tozalash' bosing."
        )
    if "pending" in low and "package" in low:
        return (
            "Oldingi run qoldiq paketlar bor. "
            "Tiklash → 'Kutayotgan paketlarni tozalash', keyin qayta Run."
        )
    # Keep short; avoid dumping full SQLAlchemy chain to the toast
    first = msg.split("\n")[0]
    if len(first) > 220:
        first = first[:220] + "…"
    return first
