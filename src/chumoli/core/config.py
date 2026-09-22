"""chumoli.core.config — PipelineConfig (format-agnostic, no dlt import)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class WriteDisposition(str, Enum):
    APPEND = "append"
    REPLACE = "replace"
    MERGE = "merge"


class ScheduleKind(str, Enum):
    MANUAL = "manual"
    INTERVAL = "interval"
    DAILY_AT = "daily_at"
    # Legacy — built-in scheduler does not integrate Airflow
    AIRFLOW = "airflow"


class ScheduleConfig(BaseModel):
    kind: ScheduleKind = ScheduleKind.MANUAL
    interval_minutes: int | None = Field(default=None)
    daily_at_time: str | None = Field(
        default=None, description='Har kuni soat, masalan "10:00"'
    )
    timezone: str = Field(default="Asia/Tashkent")

    @field_validator("daily_at_time")
    @classmethod
    def _normalize_daily_at_time(cls, v: str | None) -> str | None:
        if v is None or str(v).strip() == "":
            return None
        s = str(v).strip()
        parts = s.split(":")
        if len(parts) != 2:
            raise ValueError("daily_at_time formati HH:MM bo'lishi kerak")
        try:
            h, m = int(parts[0]), int(parts[1])
        except ValueError as e:
            raise ValueError("daily_at_time formati HH:MM bo'lishi kerak") from e
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("daily_at_time: soat 0-23, daqiqa 0-59")
        return f"{h:02d}:{m:02d}"

    @model_validator(mode="after")
    def _schedule_fields_required(self) -> "ScheduleConfig":
        if self.kind == ScheduleKind.INTERVAL and not self.interval_minutes:
            raise ValueError("kind=interval uchun interval_minutes majburiy")
        if self.kind == ScheduleKind.DAILY_AT and not self.daily_at_time:
            raise ValueError('kind=daily_at uchun daily_at_time majburiy (masalan "10:00")')
        return self


class DestinationConfig(BaseModel):
    connector: str = Field(..., description="duckdb|postgresql|clickhouse|filesystem")
    connection: str | None = Field(default=None)
    dataset_name: str = Field(default="raw")
    # filesystem only: csv (Excel-friendly default) | parquet | jsonl
    file_format: str | None = Field(
        default=None,
        description="Loader file format for filesystem destination",
    )

    @field_validator("file_format")
    @classmethod
    def _file_format_ok(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        allowed = {"csv", "parquet", "jsonl"}
        low = v.strip().lower()
        if low not in allowed:
            raise ValueError(f"file_format faqat {sorted(allowed)} bo'lishi mumkin")
        return low


class QualityConfig(BaseModel):
    row_count_min: int | None = 1
    not_null_columns: list[str] = Field(default_factory=list)
    no_duplicates_key: str | None = None
    freshness_max_minutes: int | None = None
    freshness_column: str | None = None
    table_name: str | None = None


class NotifyConfig(BaseModel):
    on_failure: bool = True
    on_success: bool = False
    telegram_chat_id: str | None = None


class PipelineConfig(BaseModel):
    name: str
    connector_key: str
    source_params: dict[str, Any] = Field(default_factory=dict)
    destination: DestinationConfig
    write_disposition: WriteDisposition = WriteDisposition.APPEND
    primary_key: list[str] = Field(default_factory=list)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)

    @field_validator("name")
    @classmethod
    def _name_is_filesystem_safe(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Pipeline nomi bo'sh bo'lishi mumkin emas")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
        if not set(cleaned) <= allowed:
            raise ValueError(
                "Pipeline nomida faqat harf, raqam, '_' va '-' bo'lishi mumkin"
            )
        return cleaned

    @model_validator(mode="after")
    def merge_requires_primary_key(self) -> "PipelineConfig":
        if self.write_disposition == WriteDisposition.MERGE and not self.primary_key:
            raise ValueError(
                "write_disposition=merge uchun primary_key majburiy "
                "(bo'sh ro'yxat bilan merge ishlamaydi)"
            )
        return self

    def to_storable_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
