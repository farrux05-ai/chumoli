"""
chumoli.core.paths
=================

Runtime fayllar ikki joyda:

  $CHUMOLI_HOME/          (default ~/.chumoli) — yashirin, tizim fayllari
    chumoli_control.db
    master.key
    api.key
    pipelines/            # dlt working dir / schema state
    exports/              # filesystem destination

  ~/chumoli-data/         — foydalanuvchi ko'radigan DuckDB va demo fayllar
    <pipeline>.duckdb
    examples/
    warehouse.duckdb
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_PIPELINE_NAME_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def chumoli_home() -> Path:
    """Root for control DB, keys, pipelines state (hidden).

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


def user_data_dir() -> Path:
    """Visible DuckDB / demo root: ~/chumoli-data (user can find it).

    Override with $CHUMOLI_DATA for tests or custom installs.
    """
    raw = os.environ.get("CHUMOLI_DATA", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.home() / "chumoli-data"


def data_dir() -> Path:
    """Default DuckDB warehouse folder (user-visible)."""
    return user_data_dir()


def pipelines_dir() -> Path:
    return chumoli_home() / "pipelines"


def examples_dir() -> Path:
    """Demo destinations: ~/chumoli-data/examples/"""
    return user_data_dir() / "examples"


def exports_dir() -> Path:
    return chumoli_home() / "exports"


def ensure_runtime_dirs() -> Path:
    """Create system home + user-visible data dirs."""
    home = chumoli_home()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    for sub in (pipelines_dir(), exports_dir()):
        sub.mkdir(mode=0o700, parents=True, exist_ok=True)
    # User-visible data (more open permissions so analyst can browse)
    ud = user_data_dir()
    ud.mkdir(mode=0o755, parents=True, exist_ok=True)
    examples_dir().mkdir(mode=0o755, parents=True, exist_ok=True)
    return home


def safe_pipeline_filename(name: str) -> str:
    cleaned = _PIPELINE_NAME_SAFE.sub("_", (name or "pipeline").strip()) or "pipeline"
    return cleaned[:120]


def default_duckdb_path(pipeline_name: str) -> str:
    """~/chumoli-data/<pipeline>.duckdb — foydalanuvchi topa oladi"""
    ensure_runtime_dirs()
    home = user_data_dir()
    home.mkdir(mode=0o755, parents=True, exist_ok=True)
    return str(home / f"{safe_pipeline_filename(pipeline_name)}.duckdb")


def resolve_duckdb_path(connection: str, pipeline_name: str | None = None) -> str:
    """Normalize user/empty DuckDB path so files never land in CWD.

    - empty → ~/chumoli-data/<pipeline>.duckdb or warehouse.duckdb
    - ~/... → expanduser
    - relative path → under ~/chumoli-data/
    - absolute → as-is
    """
    ensure_runtime_dirs()
    raw = (connection or "").strip()
    if not raw:
        if not pipeline_name:
            home = user_data_dir()
            home.mkdir(mode=0o755, parents=True, exist_ok=True)
            return str(home / "warehouse.duckdb")
        return default_duckdb_path(pipeline_name)

    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = data_dir() / path
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
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
