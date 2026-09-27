"""filesystem_s3 — manifest + config (tarmoq yo'q)."""

from __future__ import annotations

from pathlib import Path

import pytest

from chumoli.connectors import register_builtin_connectors
from chumoli.connectors.base import registry
from chumoli.connectors.filesystem_s3.connector import (
    build_credentials,
    build_readers_kwargs,
    default_glob,
    normalize_bucket_url,
    resolve_glob,
)


def test_filesystem_s3_registered() -> None:
    register_builtin_connectors()
    m = registry.get_manifest("filesystem_s3")
    assert m.label == "Filesystem / S3"
    assert m.category.value == "universal"
    assert m.maturity.value == "stable"
    keys = {f.key for f in m.fields}
    assert {"path_or_url", "file_format", "glob_pattern"} <= keys
    assert "aws_secret_access_key" in m.secret_keys()


def test_normalize_local_dir(tmp_path: Path) -> None:
    bucket, single = normalize_bucket_url(str(tmp_path))
    assert bucket == str(tmp_path)
    assert single is None


def test_normalize_local_file(tmp_path: Path) -> None:
    f = tmp_path / "orders.csv"
    f.write_text("id,n\n1,a\n")
    bucket, single = normalize_bucket_url(str(f))
    assert bucket == str(tmp_path)
    assert single == "orders.csv"


def test_normalize_s3_prefix() -> None:
    bucket, single = normalize_bucket_url("s3://bucket/prefix")
    assert bucket == "s3://bucket/prefix"
    assert single is None


def test_normalize_s3_file() -> None:
    bucket, single = normalize_bucket_url("s3://bucket/prefix/data.parquet")
    assert bucket == "s3://bucket/prefix"
    assert single == "data.parquet"


def test_normalize_rejects_http() -> None:
    with pytest.raises(ValueError, match="HTTP"):
        normalize_bucket_url("https://example.com/file.csv")


def test_normalize_empty() -> None:
    with pytest.raises(ValueError):
        normalize_bucket_url("  ")


def test_glob_defaults_and_override() -> None:
    assert default_glob("csv") == "**/*.csv"
    assert resolve_glob("parquet", "", None) == "**/*.parquet"
    assert resolve_glob("csv", "2024-*.csv", None) == "2024-*.csv"
    assert resolve_glob("csv", "", "one.csv") == "one.csv"
    with pytest.raises(ValueError):
        default_glob("xlsx")


def test_credentials_both_or_neither() -> None:
    assert build_credentials({}, {}) is None
    with pytest.raises(ValueError, match="Secret"):
        build_credentials({}, {"aws_access_key_id": "AKI"})
    with pytest.raises(ValueError, match="Access Key"):
        build_credentials({}, {"aws_secret_access_key": "sec"})
    creds = build_credentials(
        {"aws_region": "eu-central-1"},
        {"aws_access_key_id": "AKI", "aws_secret_access_key": "sec"},
    )
    assert creds == {
        "aws_access_key_id": "AKI",
        "aws_secret_access_key": "sec",
        "region_name": "eu-central-1",
    }


def test_build_readers_kwargs_local(tmp_path: Path) -> None:
    cfg = build_readers_kwargs(
        {"path_or_url": str(tmp_path), "file_format": "jsonl"},
        {},
    )
    assert cfg["bucket_url"] == str(tmp_path)
    assert cfg["file_glob"] == "**/*.jsonl"
    assert cfg["file_format"] == "jsonl"
    assert "credentials" not in cfg


def test_manifest_validate() -> None:
    register_builtin_connectors()
    m = registry.get_manifest("filesystem_s3")
    errors = m.validate_values(
        {"path_or_url": "/tmp/data", "file_format": "csv"}
    )
    assert errors == []


def test_build_dlt_source_no_network(tmp_path: Path) -> None:
    register_builtin_connectors()
    src = registry.get("filesystem_s3").build_dlt_source(
        {"path_or_url": str(tmp_path), "file_format": "jsonl"},
        {},
    )
    assert src is not None
    assert getattr(src, "name", None) == "files"


def test_normalize_s3_dir_with_dot_is_not_a_file() -> None:
    """`data.v2` — papka. Ilgari nuqta evristikasi uni fayl deb hisoblardi."""
    bucket, single = normalize_bucket_url("s3://bucket/data.v2")
    assert bucket == "s3://bucket/data.v2"
    assert single is None


def test_normalize_s3_extensionless_name_is_not_a_file() -> None:
    bucket, single = normalize_bucket_url("s3://bucket/report-2026-09")
    assert bucket == "s3://bucket/report-2026-09"
    assert single is None


def test_normalize_s3_gz_file() -> None:
    bucket, single = normalize_bucket_url("s3://bucket/prefix/orders.csv.gz")
    assert bucket == "s3://bucket/prefix"
    assert single == "orders.csv.gz"
