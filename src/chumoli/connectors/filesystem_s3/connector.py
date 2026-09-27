"""
chumoli.connectors.filesystem_s3
=================================

dlt `readers` (filesystem source) ustidagi yupqa adapter.

Local papka yoki S3/GCS/Azure (`s3://`, `gs://`, `az://`).
Formatlar: CSV (DuckDB reader — pandas shart emas), Parquet, JSONL.

Rasmiy dlt: https://dlthub.com/docs/dlt-ecosystem/verified-sources/filesystem/basic
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chumoli.core.manifest import (
    ConnectorCategory,
    ConnectorManifest,
    FieldSpec,
    FieldType,
    SelectOption,
)

_FORMAT_GLOBS = {
    "csv": "**/*.csv",
    "parquet": "**/*.parquet",
    "jsonl": "**/*.jsonl",
}


MANIFEST = ConnectorManifest(
    key="filesystem_s3",
    label="Filesystem / S3",
    category=ConnectorCategory.UNIVERSAL,
    description="Lokal papka yoki S3 dan CSV / Parquet / JSONL o'qish (dlt filesystem)",
    dlt_source_factory="chumoli.connectors.filesystem_s3.connector.FilesystemS3Connector",
    fields=[
        FieldSpec(
            key="path_or_url",
            label="Yo'l yoki URL",
            type=FieldType.TEXT,
            required=True,
            placeholder="/data/exports  yoki  s3://bucket/prefix",
            help_text=(
                "Lokal papka, bitta fayl, yoki s3:// / gs:// / az:// manzil. "
                "S3 uchun pastroqdagi kalitlarni to'ldiring yoki AWS env ishlating."
            ),
        ),
        FieldSpec(
            key="file_format",
            label="Fayl formati",
            type=FieldType.SELECT,
            required=True,
            default="csv",
            options=[
                SelectOption(value="csv", label="CSV"),
                SelectOption(value="parquet", label="Parquet"),
                SelectOption(value="jsonl", label="JSONL"),
            ],
        ),
        FieldSpec(
            key="glob_pattern",
            label="Glob (ixtiyoriy)",
            type=FieldType.TEXT,
            required=False,
            default="",
            placeholder="**/*.csv",
            help_text="Bo'sh qoldirsangiz formatga mos default: **/*.csv va h.k.",
        ),
        FieldSpec(
            key="aws_access_key_id",
            label="AWS Access Key ID (S3, ixtiyoriy)",
            type=FieldType.PASSWORD,
            required=False,
            secret=True,
        ),
        FieldSpec(
            key="aws_secret_access_key",
            label="AWS Secret Access Key (S3, ixtiyoriy)",
            type=FieldType.PASSWORD,
            required=False,
            secret=True,
        ),
        FieldSpec(
            key="aws_region",
            label="AWS region (ixtiyoriy)",
            type=FieldType.TEXT,
            required=False,
            default="us-east-1",
            placeholder="us-east-1",
        ),
    ],
)


# Fayl faqat ma'lum ma'lumot kengaytmalari bo'yicha aniqlanadi.
# "oxirgi segmentda nuqta bor" evristikasi `s3://bucket/data.v2` kabi papkani
# fayl deb hisoblab, o'sha papkadan hech narsa o'qilmasligiga olib kelardi.
_FILE_SUFFIXES = (
    ".csv",
    ".tsv",
    ".parquet",
    ".jsonl",
    ".ndjson",
    ".json",
    ".txt",
    ".gz",
    ".zip",
)


def _split_file_url(raw: str) -> tuple[str, str | None]:
    """Agar URL oxiri ma'lum ma'lumot fayli bo'lsa, (parent, filename) qaytaradi."""
    stripped = raw.rstrip("/")
    if "/" not in stripped:
        return raw, None
    parent, name = stripped.rsplit("/", 1)
    if name.startswith(".") or not name.lower().endswith(_FILE_SUFFIXES):
        return raw, None
    return parent, name


def normalize_bucket_url(path_or_url: str) -> tuple[str, str | None]:
    """(bucket_url, file_name_if_single). file_name_if_single glob o'rniga ishlatiladi."""
    raw = (path_or_url or "").strip()
    if not raw:
        raise ValueError("'Yo'l yoki URL' to'ldirilishi shart")

    if "://" in raw:
        scheme, rest = raw.split("://", 1)
        if scheme in ("http", "https"):
            raise ValueError(
                "filesystem_s3 HTTP URL qabul qilmaydi — lokal yo'l yoki "
                "s3:// / gs:// / az:// yozing"
            )
        parent, name = _split_file_url(raw)
        return parent if name else raw, name

    path = Path(raw).expanduser()
    if path.is_file():
        return str(path.parent), path.name
    return str(path), None


def default_glob(file_format: str) -> str:
    fmt = (file_format or "csv").strip().lower()
    if fmt not in _FORMAT_GLOBS:
        raise ValueError(f"Noma'lum fayl formati: {file_format}")
    return _FORMAT_GLOBS[fmt]


def resolve_glob(file_format: str, glob_pattern: str | None, single_name: str | None) -> str:
    if single_name:
        return single_name
    custom = (glob_pattern or "").strip()
    if custom:
        return custom
    return default_glob(file_format)


def build_credentials(params: dict[str, Any], secrets: dict[str, str]) -> dict[str, str] | None:
    access = (secrets.get("aws_access_key_id") or "").strip()
    secret = (secrets.get("aws_secret_access_key") or "").strip()
    if access and not secret:
        raise ValueError("AWS Secret Access Key ham kerak")
    if secret and not access:
        raise ValueError("AWS Access Key ID ham kerak")
    if not access:
        return None
    region = str(params.get("aws_region") or secrets.get("aws_region") or "us-east-1").strip()
    return {
        "aws_access_key_id": access,
        "aws_secret_access_key": secret,
        "region_name": region or "us-east-1",
    }


def build_readers_kwargs(params: dict[str, Any], secrets: dict[str, str]) -> dict[str, Any]:
    """Test qilinadigan sof config (dlt chaqirmasdan)."""
    fmt = str(params.get("file_format") or "csv").strip().lower()
    if fmt not in _FORMAT_GLOBS:
        raise ValueError(f"Noma'lum fayl formati: {fmt}")
    bucket, single = normalize_bucket_url(str(params.get("path_or_url") or ""))
    glob_pattern = resolve_glob(fmt, params.get("glob_pattern"), single)
    kwargs: dict[str, Any] = {
        "bucket_url": bucket,
        "file_glob": glob_pattern,
        "file_format": fmt,
    }
    creds = build_credentials(params, secrets)
    if creds:
        kwargs["credentials"] = creds
    return kwargs


def _apply_reader(source: Any, file_format: str) -> Any:
    if file_format == "csv":
        # DuckDB CSV reader — pandas kerak emas
        return source.read_csv_duckdb().with_name("files")
    if file_format == "parquet":
        return source.read_parquet().with_name("files")
    return source.read_jsonl().with_name("files")


class FilesystemS3Connector:
    """dlt filesystem `readers` — BaseUZConnector."""

    manifest = MANIFEST

    def build_dlt_source(self, params: dict[str, Any], secrets: dict[str, str]) -> Any:
        from dlt.sources.filesystem import readers

        cfg = build_readers_kwargs(params, secrets)
        fmt = cfg.pop("file_format")
        call: dict[str, Any] = {
            "bucket_url": cfg["bucket_url"],
            "file_glob": cfg["file_glob"],
        }
        if "credentials" in cfg:
            call["credentials"] = cfg["credentials"]
        return _apply_reader(readers(**call), fmt)
