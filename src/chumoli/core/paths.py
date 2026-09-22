"""
chumoli.core.paths
=================

Runtime fayllar ikki joyda:

  $CHUMOLI_HOME/          (default ~/.chumoli) — yashirin, tizim fayllari
    chumoli_control.db
    master.key
    api.key
    pipelines/            # dlt working dir / schema state + _dlt metadata

  ~/chumoli-data/         — foydalanuvchi ko'radigan ma'lumotlar
    <pipeline>.duckdb
    examples/
    warehouse.duckdb
    exports/<pipeline>/   # lokal filesystem destination (CSV/Parquet)
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_PIPELINE_NAME_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")

# Cloud / object-storage URL schemes (not local paths)
_REMOTE_SCHEMES = ("s3://", "gs://", "gcs://", "az://", "abfss://", "hf://", "file://")


def chumoli_home() -> Path:
    """Root for control DB, keys, pipelines state (hidden).

    Resolution order:
      1. $CHUMOLI_HOME
      2. ~/.chumoli
    """
    raw = os.environ.get("CHUMOLI_HOME", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".chumoli").resolve()


def user_data_dir() -> Path:
    """Visible DuckDB / demo / exports root: ~/chumoli-data (user can find it).

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
    """User-visible local export root: ~/chumoli-data/exports/"""
    return user_data_dir() / "exports"


def ensure_runtime_dirs() -> Path:
    """Create system home + user-visible data dirs."""
    home = chumoli_home()
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    pipelines_dir().mkdir(mode=0o700, parents=True, exist_ok=True)
    # User-visible data (more open permissions so analyst can browse)
    ud = user_data_dir()
    ud.mkdir(mode=0o755, parents=True, exist_ok=True)
    examples_dir().mkdir(mode=0o755, parents=True, exist_ok=True)
    exports_dir().mkdir(mode=0o755, parents=True, exist_ok=True)
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
    """Local export folder: ~/chumoli-data/exports/<pipeline>/ (user-visible)."""
    ensure_runtime_dirs()
    path = exports_dir() / safe_pipeline_filename(pipeline_name)
    path.mkdir(mode=0o755, parents=True, exist_ok=True)
    return str(path.resolve())


def is_remote_url(url: str) -> bool:
    lower = (url or "").strip().lower()
    return lower.startswith(_REMOTE_SCHEMES)


def resolve_filesystem_url(
    connection: str | None,
    pipeline_name: str,
    *,
    allow_remote: bool = False,
) -> str:
    """Normalize local filesystem destination path.

    - empty → ~/chumoli-data/exports/<pipeline>/
    - remote schemes → only if allow_remote=True (else ValueError)
    - ~/... → expand
    - relative → under exports/
    - absolute local path → as-is (mkdir parent)
    """
    ensure_runtime_dirs()
    raw = (connection or "").strip()
    if not raw:
        return default_filesystem_path(pipeline_name)

    if is_remote_url(raw):
        if not allow_remote:
            raise ValueError(
                "Lokal «Filesystem» destination uchun s3:// / gs:// ishlatilmaydi. "
                "Bulut uchun «S3 / Object storage» destination tanlang."
            )
        return raw

    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = exports_dir() / path
    path.mkdir(mode=0o755, parents=True, exist_ok=True)
    return str(path.resolve())


def resolve_s3_url(connection: str | None) -> str:
    """Normalize object-storage URL — remote schemes only, required."""
    raw = (connection or "").strip()
    if not raw:
        raise ValueError(
            "S3 / Object storage uchun bucket URL majburiy "
            "(masalan s3://bucket/prefix yoki gs://bucket/prefix)."
        )
    if not is_remote_url(raw):
        raise ValueError(
            f"S3 destination faqat bulut URL qabul qiladi (s3://, gs://, …). "
            f"Lokal papka uchun «Lokal fayl» destination tanlang. Berilgan: {raw!r}"
        )
    return raw
