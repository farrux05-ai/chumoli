"""
uzpipe.store.run_store
========================

Pipeline run tarixi — monitor / dashboard uchun.

NEGA ALOHIDA FAYL (control_store emas)
----------------------------------------
ControlStore — konfiguratsiya (kam yozish, maxfiy ma'lumot).
RunStore — har bir run natijasi (ko'p yozish, hech qanday secret yo'q).
Ikki xil yozish naqshi → ikki xil do'kon (architecture/overview).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_name TEXT NOT NULL,
    success INTEGER NOT NULL,
    quality_passed INTEGER NOT NULL,
    row_counts_json TEXT NOT NULL DEFAULT '{}',
    quality_details_json TEXT NOT NULL DEFAULT '[]',
    error TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    trigger TEXT NOT NULL DEFAULT 'manual'
);
CREATE INDEX IF NOT EXISTS idx_runs_pipeline ON runs(pipeline_name);
CREATE INDEX IF NOT EXISTS idx_runs_finished ON runs(finished_at DESC);
"""


@dataclass
class RunRecord:
    id: int
    pipeline_name: str
    success: bool
    quality_passed: bool
    row_counts: dict[str, int]
    quality_details: list[dict[str, Any]]
    error: str | None
    started_at: str
    finished_at: str
    trigger: str  # manual | schedule


class RunStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or self._default_db_path()
        self._db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._init()

    @staticmethod
    def _default_db_path() -> Path:
        return Path.home() / ".uzpipe" / "uzpipe_runs.db"

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def record(
        self,
        *,
        pipeline_name: str,
        success: bool,
        quality_passed: bool,
        row_counts: dict[str, int] | None = None,
        quality_details: list[dict[str, Any]] | None = None,
        error: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        trigger: str = "manual",
    ) -> int:
        started = (started_at or datetime.now(UTC)).isoformat()
        finished = (finished_at or datetime.now(UTC)).isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO runs (
                    pipeline_name, success, quality_passed,
                    row_counts_json, quality_details_json, error,
                    started_at, finished_at, trigger
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pipeline_name,
                    1 if success else 0,
                    1 if quality_passed else 0,
                    json.dumps(row_counts or {}),
                    json.dumps(quality_details or []),
                    error,
                    started,
                    finished,
                    trigger,
                ),
            )
            return int(cur.lastrowid)

    def list_recent(
        self, *, limit: int = 50, pipeline_name: str | None = None
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 200))
        with self._connect() as conn:
            if pipeline_name:
                rows = conn.execute(
                    """
                    SELECT * FROM runs
                    WHERE pipeline_name = ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (pipeline_name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM runs ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            ok = conn.execute(
                "SELECT COUNT(*) FROM runs WHERE success = 1"
            ).fetchone()[0]
            fail = conn.execute(
                "SELECT COUNT(*) FROM runs WHERE success = 0"
            ).fetchone()[0]
            last = conn.execute(
                "SELECT finished_at FROM runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return {
            "total_runs": total,
            "success": ok,
            "failed": fail,
            "last_run_at": last[0] if last else None,
        }

    @staticmethod
    def _row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": r["id"],
            "pipeline_name": r["pipeline_name"],
            "success": bool(r["success"]),
            "quality_passed": bool(r["quality_passed"]),
            "row_counts": json.loads(r["row_counts_json"] or "{}"),
            "quality_details": json.loads(r["quality_details_json"] or "[]"),
            "error": r["error"],
            "started_at": r["started_at"],
            "finished_at": r["finished_at"],
            "trigger": r["trigger"],
        }
