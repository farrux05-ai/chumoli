"""
chumoli.core.paths
=================

Barcha runtime fayllar uchun yagona joy: $CHUMOLI_HOME (default ~/.chumoli).

  $CHUMOLI_HOME/
    chumoli_control.db
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


def chumoli_home() -> Path:
    """Root for control DB, keys, pipelines state, and data files.

    Resolution order:
      1. $CHUMOLI_HOME
      2. $UZPIPE_HOME (legacy rename compatibility)
      3. ~/.chumoli, or existing ~/.uzpipe if new dir not created yet
    """
    raw = os.environ.get("CHUMOLI_HOME", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    legacy = os.environ.get("UZPIPE_HOME", "").strip()
    if legacy:
        return Path(legacy).expanduser().resolve()
    new_home = Path.home() / ".chumoli"
    old_home = Path.home() / ".uzpipe"
    if not new_home.exists() and old_home.exists():
        return old_home.resolve()
    return new_home.resolve()


def data_dir() -> Path:
    return chumoli_home() / "data"


def pipelines_dir() -> Path:
    return chumoli_home() / "pipelines"


def examples_dir() -> Path:
    return chumoli_home() / "examples"


def exports_dir() -> Path:
    return chumoli_home() / "exports"


def ensure_runtime_dirs() -> Path:
    """Create home + data + pipelines + examples with restrictive mode."""
    home = chumoli_home()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    for sub in (data_dir(), pipelines_dir(), examples_dir(), exports_dir()):
        sub.mkdir(mode=0o700, parents=True, exist_ok=True)
    return home


def safe_pipeline_filename(name: str) -> str:
    cleaned = _PIPELINE_NAME_SAFE.sub("_", (name or "pipeline").strip()) or "pipeline"
    return cleaned[:120]


def default_duckdb_path(pipeline_name: str) -> str:
    """Absolute path: $CHUMOLI_HOME/data/<pipeline>.duckdb"""
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


def default_filesystem_path(pipeline_name: str) -> str:
    """Local export folder: $CHUMOLI_HOME/exports/<pipeline>/"""
    ensure_runtime_dirs()
    path = exports_dir() / safe_pipeline_filename(pipeline_name)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return str(path.resolve())


def resolve_filesystem_url(connection: str | None, pipeline_name: str) -> str:
    """Normalize filesystem destination URL/path.

    - empty → exports/<pipeline>/
    - s3:// gs:// az:// hf:// → as-is
    - ~/... → expand
    - relative → under exports/
    - absolute local path → as-is (mkdir parent)
    """
    ensure_runtime_dirs()
    raw = (connection or "").strip()
    if not raw:
        return default_filesystem_path(pipeline_name)

    lower = raw.lower()
    if lower.startswith(("s3://", "gs://", "gcs://", "az://", "abfss://", "hf://", "file://")):
        return raw

    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = exports_dir() / path
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return str(path.resolve())
