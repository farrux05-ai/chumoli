"""
chumoli.store.run_store
========================

Pipeline run history for monitor / dashboard.
Includes duration + throughput for volume demos.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
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
    trigger TEXT NOT NULL DEFAULT 'manual',
    duration_seconds REAL NOT NULL DEFAULT 0,
    total_rows INTEGER NOT NULL DEFAULT 0,
    rows_per_second REAL NOT NULL DEFAULT 0,
    new_rows INTEGER NOT NULL DEFAULT 0,
    col_counts_json TEXT NOT NULL DEFAULT '{}',
    schema_changes_json TEXT NOT NULL DEFAULT '[]',
    cursor_last_value TEXT,
    is_first_run INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_runs_pipeline ON runs(pipeline_name);
CREATE INDEX IF NOT EXISTS idx_runs_finished ON runs(finished_at DESC);
"""

_EXTRA_COLUMNS: list[tuple[str, str]] = [
    ("duration_seconds", "REAL NOT NULL DEFAULT 0"),
    ("total_rows", "INTEGER NOT NULL DEFAULT 0"),
    ("rows_per_second", "REAL NOT NULL DEFAULT 0"),
    ("new_rows", "INTEGER NOT NULL DEFAULT 0"),
    ("col_counts_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("schema_changes_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("cursor_last_value", "TEXT"),
    ("is_first_run", "INTEGER NOT NULL DEFAULT 1"),
    ("peak_memory_mb", "REAL NOT NULL DEFAULT 0"),
]


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
    trigger: str
    duration_seconds: float = 0.0
    total_rows: int = 0
    rows_per_second: float = 0.0
    new_rows: int = 0
    col_counts: dict[str, int] = field(default_factory=dict)
    schema_changes: list[str] = field(default_factory=list)
    cursor_last_value: Any = None
    is_first_run: bool = True


class RunStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or self._default_db_path()
        self._db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._init()

    @staticmethod
    def _default_db_path() -> Path:
        home = Path(__import__("os").environ.get("CHUMOLI_HOME") or (Path.home() / ".chumoli"))
        return home / "chumoli_runs.db"

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(runs)").fetchall()}
            for name, ddl in _EXTRA_COLUMNS:
                if name not in cols:
                    conn.execute(f"ALTER TABLE runs ADD COLUMN {name} {ddl}")

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
        duration_seconds: float = 0.0,
        total_rows: int | None = None,
        rows_per_second: float | None = None,
        new_rows: int = 0,
        col_counts: dict[str, int] | None = None,
        schema_changes: list[str] | None = None,
        cursor_last_value: Any = None,
        is_first_run: bool = True,
        peak_memory_mb: float = 0.0,
    ) -> int:
        started = (started_at or datetime.now(UTC)).isoformat()
        finished = (finished_at or datetime.now(UTC)).isoformat()
        counts = row_counts or {}
        total = total_rows if total_rows is not None else sum(counts.values())
        rps = rows_per_second
        if rps is None:
            rps = (total / duration_seconds) if duration_seconds > 0 else 0.0
        cursor_raw = (
            json.dumps(cursor_last_value, default=str) if cursor_last_value is not None else None
        )
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO runs (
                    pipeline_name, success, quality_passed,
                    row_counts_json, quality_details_json, error,
                    started_at, finished_at, trigger,
                    duration_seconds, total_rows, rows_per_second,
                    new_rows, col_counts_json, schema_changes_json,
                    cursor_last_value, is_first_run, peak_memory_mb
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pipeline_name,
                    1 if success else 0,
                    1 if quality_passed else 0,
                    json.dumps(counts),
                    json.dumps(quality_details or []),
                    error,
                    started,
                    finished,
                    trigger,
                    float(duration_seconds),
                    int(total),
                    float(rps),
                    int(new_rows or 0),
                    json.dumps(col_counts or {}),
                    json.dumps(schema_changes or []),
                    cursor_raw,
                    1 if is_first_run else 0,
                    float(peak_memory_mb or 0),
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
            row_sum = conn.execute(
                "SELECT COALESCE(SUM(total_rows), 0) FROM runs"
            ).fetchone()[0]
        return {
            "total_runs": total,
            "success": ok,
            "failed": fail,
            "last_run_at": last[0] if last else None,
            "total_rows_loaded": int(row_sum or 0),
        }

    @staticmethod
    def _decode_cursor(raw: Any) -> Any:
        if raw is None or raw == "":
            return None
        if not isinstance(raw, str):
            return raw
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return raw

    @staticmethod
    def _row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
        keys = set(r.keys())
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
            "duration_seconds": float(r["duration_seconds"] or 0)
            if "duration_seconds" in keys
            else 0.0,
            "total_rows": int(r["total_rows"] or 0) if "total_rows" in keys else 0,
            "rows_per_second": float(r["rows_per_second"] or 0)
            if "rows_per_second" in keys
            else 0.0,
            "new_rows": int(r["new_rows"] or 0) if "new_rows" in keys else 0,
            "col_counts": json.loads(r["col_counts_json"] or "{}")
            if "col_counts_json" in keys
            else {},
            "schema_changes": json.loads(r["schema_changes_json"] or "[]")
            if "schema_changes_json" in keys
            else [],
            "cursor_last_value": RunStore._decode_cursor(
                r["cursor_last_value"] if "cursor_last_value" in keys else None
            ),
            "is_first_run": bool(r["is_first_run"])
            if "is_first_run" in keys and r["is_first_run"] is not None
            else True,
            "peak_memory_mb": float(r["peak_memory_mb"] or 0)
            if "peak_memory_mb" in keys
            else 0.0,
        }
