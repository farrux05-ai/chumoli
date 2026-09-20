"""
uzpipe.core.paths
=================

Barcha runtime fayllar uchun yagona joy: $UZPIPE_HOME (default ~/.uzpipe).

  $UZPIPE_HOME/
    uzpipe_control.db
    master.key
    api.key
    pipelines/          # dlt working dir / schema state
    data/               # default DuckDB warehouses
    examples/           # demo destinations
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_PIPELINE_NAME_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def uzpipe_home() -> Path:
    """Root for control DB, keys, pipelines state, and data files."""
    raw = os.environ.get("UZPIPE_HOME", "").strip()
    home = Path(raw).expanduser() if raw else (Path.home() / ".uzpipe")
    return home.resolve()


def data_dir() -> Path:
    return uzpipe_home() / "data"


def pipelines_dir() -> Path:
    return uzpipe_home() / "pipelines"


def examples_dir() -> Path:
    return uzpipe_home() / "examples"


def ensure_runtime_dirs() -> Path:
    """Create home + data + pipelines + examples with restrictive mode."""
    home = uzpipe_home()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    for sub in (data_dir(), pipelines_dir(), examples_dir()):
        sub.mkdir(mode=0o700, parents=True, exist_ok=True)
    return home


def safe_pipeline_filename(name: str) -> str:
    cleaned = _PIPELINE_NAME_SAFE.sub("_", (name or "pipeline").strip()) or "pipeline"
    return cleaned[:120]


def default_duckdb_path(pipeline_name: str) -> str:
    """Absolute path: $UZPIPE_HOME/data/<pipeline>.duckdb"""
    ensure_runtime_dirs()
    return str(data_dir() / f"{safe_pipeline_filename(pipeline_name)}.duckdb")


def resolve_duckdb_path(connection: str, pipeline_name: str | None = None) -> str:
    """Normalize user/empty DuckDB path so files never land in CWD.

    - empty → default under data/
    - ~/... → expanduser
    - relative path → under data/
    - absolute → as-is
    """
    ensure_runtime_dirs()
    raw = (connection or "").strip()
    if not raw:
        if not pipeline_name:
            return str(data_dir() / "warehouse.duckdb")
        return default_duckdb_path(pipeline_name)

    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = data_dir() / path
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    return str(path.resolve())
