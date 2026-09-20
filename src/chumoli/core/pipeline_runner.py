"""pipeline_runner — ControlStore + connector → dlt.run(); quality; notify; recovery."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import dlt

from chumoli.connectors.base import BaseUZConnector, registry
from chumoli.core.config import PipelineConfig
from chumoli.core.quality import QualityReport, run_quality_checks
from chumoli.core.row_counts import get_row_counts
from chumoli.store.control_store import ControlStore, StoredPipeline

log = logging.getLogger("chumoli.pipeline_runner")

# Parallel run guard: same pipeline_name + concurrent dlt.run → LoadPackageNotFound
# (dlt working dir shared). One in-process run per name at a time.
_RUNNING_PIPELINES: dict[str, dict[str, Any]] = {}
_RUNNING_LOCK = threading.Lock()


class PipelineAlreadyRunning(RuntimeError):
    """Same pipeline is already executing in this process."""


@dataclass
class RunResult:
    pipeline_name: str
    load_info: Any
    row_counts: dict[str, int]
    quality_report: QualityReport
    duration_seconds: float = 0.0

    @property
    def success(self) -> bool:
        return not self.load_info.has_failed_jobs

    @property
    def total_rows(self) -> int:
        return sum(self.row_counts.values())

    @property
    def rows_per_second(self) -> float:
        if self.duration_seconds <= 0:
            return 0.0
        return self.total_rows / self.duration_seconds


# UI/catalog keys → dlt.destinations attribute names (when they differ).
# Catalog keeps user-facing names (postgresql); dlt module uses postgres.
_DLT_DEST_ALIASES: dict[str, str] = {
    "postgresql": "postgres",
}


def build_dlt_pipeline(config: PipelineConfig) -> dlt.Pipeline:
    from chumoli.core.paths import (
        ensure_runtime_dirs,
        pipelines_dir,
        resolve_duckdb_path,
        resolve_filesystem_url,
    )

    ensure_runtime_dirs()
    dest_key = config.destination.connector
    connection = config.destination.connection
    dlt_key = _DLT_DEST_ALIASES.get(dest_key, dest_key)

    # DuckDB without an explicit path used to write <cwd>/<name>.duckdb — force under CHUMOLI_HOME/data
    if dest_key == "duckdb":
        connection = resolve_duckdb_path(connection or "", config.name)

    if dest_key == "filesystem":
        # bucket_url: local folder or s3://… (not credentials=)
        bucket_url = resolve_filesystem_url(connection, config.name)
        destination: Any = dlt.destinations.filesystem(bucket_url=bucket_url)
    elif connection:
        try:
            destination_factory = getattr(dlt.destinations, dlt_key)
        except AttributeError as e:
            raise ValueError(
                f"dlt destination '{dest_key}' (dlt key '{dlt_key}') topilmadi. "
                f"Kerak bo'lsa: pip install \"dlt[{dlt_key}]\""
            ) from e
        destination = destination_factory(credentials=connection)
    else:
        destination = dlt_key

    pdir = pipelines_dir()
    return dlt.pipeline(
        pipeline_name=config.name,
        destination=destination,
        dataset_name=config.destination.dataset_name,
        pipelines_dir=str(pdir),
    )


def get_running_pipelines() -> dict[str, dict[str, Any]]:
    """Currently executing pipelines and coarse progress (for UI polling)."""
    with _RUNNING_LOCK:
        return {k: dict(v) for k, v in _RUNNING_PIPELINES.items()}


def _set_run_step(name: str, step: str, **extra: Any) -> None:
    with _RUNNING_LOCK:
        info = _RUNNING_PIPELINES.get(name)
        if info is None:
            return
        info["step"] = step
        info.update(extra)


def run_pipeline_by_name(name: str, store: ControlStore | None = None) -> RunResult:
    store = store or ControlStore()
    stored = store.load(name)
    if stored is None:
        raise KeyError(f"Pipeline '{name}' topilmadi")

    with _RUNNING_LOCK:
        if name in _RUNNING_PIPELINES:
            raise PipelineAlreadyRunning(
                f"Pipeline '{name}' hozir ishga tushgan. "
                "Tugaguncha kuting — parallel run dlt holatini buzadi."
            )
        _RUNNING_PIPELINES[name] = {
            "started_at": time.time(),
            "step": "starting",
            "rows_so_far": 0,
        }

    try:
        connector = registry.get(stored.config.connector_key)
        result = _execute(stored, connector)
    finally:
        with _RUNNING_LOCK:
            _RUNNING_PIPELINES.pop(name, None)

    try:
        from chumoli.core.notify import maybe_notify_run

        maybe_notify_run(
            store=store,
            notify_cfg=stored.config.notify,
            pipeline_name=result.pipeline_name,
            success=result.success,
            quality_passed=result.quality_report.all_passed,
            row_counts=result.row_counts,
            quality_details=[
                {"passed": o.passed, "detail": o.detail}
                for o in result.quality_report.outcomes
            ],
            duration_seconds=result.duration_seconds,
        )
    except Exception:
        log.exception("notify_failed pipeline=%s", name)
    return result


def _execute(stored: StoredPipeline, connector: BaseUZConnector) -> RunResult:
    name = stored.config.name
    _set_run_step(name, "extract")
    source = connector.build_dlt_source(stored.config.source_params, stored.secrets)
    pipeline = build_dlt_pipeline(stored.config)

    t0 = perf_counter()
    _set_run_step(name, "run")
    run_kwargs: dict[str, Any] = {
        "write_disposition": stored.config.write_disposition.value,
        "primary_key": stored.config.primary_key or None,
    }
    # Filesystem: explicit loader format (csv default for local-friendly exports)
    dest = stored.config.destination
    if dest.connector == "filesystem":
        import os

        fmt = dest.file_format or "csv"
        run_kwargs["loader_file_format"] = fmt
        # CSV: uncompressed for Excel; other formats must not inherit this process env
        if fmt == "csv":
            os.environ["NORMALIZE__DATA_WRITER__DISABLE_COMPRESSION"] = "true"
        else:
            os.environ.pop("NORMALIZE__DATA_WRITER__DISABLE_COMPRESSION", None)

    load_info = pipeline.run(source, **run_kwargs)
    duration = perf_counter() - t0

    load_succeeded = not load_info.has_failed_jobs
    _set_run_step(name, "count" if load_succeeded else "failed")
    row_counts = (
        get_row_counts(
            pipeline,
            dest_key=dest.connector,
            load_info=load_info,
        )
        if load_succeeded
        else {}
    )
    if row_counts:
        _set_run_step(name, "count", rows_so_far=sum(row_counts.values()))

    if load_succeeded:
        _set_run_step(name, "quality")
        # Filesystem (CSV/Parquet files) — SQL quality checks don't apply reliably
        if dest.connector == "filesystem":
            quality_report = QualityReport()
        else:
            quality_report = run_quality_checks(
                pipeline, stored.config.quality, tables_written=list(row_counts.keys())
            )
    else:
        quality_report = QualityReport()

    _set_run_step(name, "done", rows_so_far=sum(row_counts.values()))
    return RunResult(
        pipeline_name=stored.config.name,
        load_info=load_info,
        row_counts=row_counts,
        quality_report=quality_report,
        duration_seconds=round(duration, 3),
    )


def _load_stored(name: str, store: ControlStore | None = None):
    store = store or ControlStore()
    stored = store.load(name)
    if stored is None:
        raise KeyError(f"Pipeline '{name}' topilmadi")
    return store, stored


def _uz_step_fail_detail(step_name: str, exception_text: str) -> str:
    """dlt step failure → qisqa o'zbekcha tavsif.

    dlt ko'pincha multi-line xabar beradi: birinchi qator umumiy
    'Pipeline execution failed at step=...', keyinroq qatorlarda asl
    sabab ('caused an exception: ...'). Eng ma'noli qatorni tanlaymiz.
    """
    step_labels = {
        "extract": "ma'lumot olish (extract)",
        "normalize": "normalizatsiya",
        "load": "yuklash (load)",
        "run": "pipeline ishga tushirish",
        "sync": "destination bilan sinxronlash",
    }
    label = step_labels.get(step_name, step_name)
    text = (exception_text or "").strip()
    if not text:
        return f"{label} bosqichida xato: noma'lum xato"

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # prefer the line with the actual root cause
    preferred = None
    for ln in lines:
        low = ln.lower()
        if "caused an exception:" in low or "connection refused" in low or "operationalerror" in low:
            preferred = ln
            break
    if preferred is None:
        # skip pure class-name lines like "<class '...'>"
        for ln in reversed(lines):
            if not (ln.startswith("<class ") and ln.endswith(">")):
                preferred = ln
                break
    if preferred is None:
        preferred = lines[0]

    if len(preferred) > 240:
        preferred = preferred[:237] + "..."
    return f"{label} bosqichida xato: {preferred}"


def get_failed_jobs(name: str, store: ControlStore | None = None) -> list[dict[str, str]]:
    """Faqat haqiqiy muvaffaqiyatsizliklarni qaytaradi (o'zbekcha detail).

    dlt 1.30: PipelineTrace.steps[*].step_exception faqat step yiqilganda
    to'ldiriladi. Muvaffaqiyatli run'da step_exception=None — ular bu yerga
    kirmaydi. "Oxirgi ish kuzatuvi mavjud" kabi mazmunsiz qator yozilmaydi.
    """
    _, stored = _load_stored(name, store)
    pipeline = build_dlt_pipeline(stored.config)
    out: list[dict[str, str]] = []
    try:
        last = pipeline.last_trace
        if last is not None:
            for step in getattr(last, "steps", []) or []:
                exc = getattr(step, "step_exception", None)
                if not exc:
                    continue
                step_name = str(getattr(step, "step", "unknown"))
                # step_exception odatda multi-line va asl sababni o'z ichiga oladi
                detail = _uz_step_fail_detail(step_name, str(exc))
                out.append({"job": f"step:{step_name}", "detail": detail})

            # package-level failed jobs (load_id ma'lum bo'lsa)
            fn = getattr(pipeline, "list_failed_jobs_in_package", None)
            if callable(fn):
                load_ids: list[str] = []
                load_info = getattr(last, "last_load_info", None)
                if load_info is not None:
                    loads = getattr(load_info, "loads_ids", None) or getattr(
                        load_info, "load_ids", None
                    )
                    if loads:
                        load_ids = list(loads)
                for lid in load_ids:
                    try:
                        jobs = fn(lid)
                    except TypeError as e:
                        log.warning("failed_jobs_lookup_unsupported: %s", e)
                        break
                    except Exception as e:
                        log.warning("failed_jobs_lookup_error: %s", e)
                        continue
                    if not jobs:
                        continue
                    for j in jobs:
                        out.append(
                            {
                                "job": str(getattr(j, "job_id", j)),
                                "detail": f"Yuklash job muvaffaqiyatsiz: {j}",
                            }
                        )
    except Exception as e:
        log.warning("get_failed_jobs_error: %s", e)
        out.append({"job": "error", "detail": f"Failed jobs o'qib bo'lmadi: {e}"})

    if not out:
        out.append(
            {
                "job": "none",
                "detail": "Hozircha muvaffaqiyatsiz ish topilmadi",
            }
        )
    return out


def drop_pending_packages(name: str, store: ControlStore | None = None) -> dict[str, str]:
    _, stored = _load_stored(name, store)
    pipeline = build_dlt_pipeline(stored.config)
    try:
        pipeline.drop_pending_packages()
        return {"status": "ok", "detail": "Pending paketlar o'chirildi"}
    except Exception as e:
        return {"status": "error", "detail": f"Pending paketlar o'chirilmadi: {e}"}


def sync_from_destination(name: str, store: ControlStore | None = None) -> dict[str, str]:
    _, stored = _load_stored(name, store)
    pipeline = build_dlt_pipeline(stored.config)
    try:
        pipeline.sync_destination()
        return {"status": "ok", "detail": "Destination bilan sinxronlashtirildi"}
    except Exception as e:
        return {"status": "error", "detail": f"Sinxronlash xatosi: {e}"}


def get_preview_rows(
    name: str, store: ControlStore | None = None, limit: int = 10
) -> dict[str, Any]:
    """First N rows per loaded table (UI preview). Max 3 tables."""
    # DuckDB (and many warehouses) reject concurrent writers — never open
    # a second connection while this pipeline is still loading.
    if name in get_running_pipelines():
        return {
            "tables": {},
            "error": "Pipeline hozir ishlayapti. Preview uchun tugashini kuting.",
        }
    _, stored = _load_stored(name, store)
    if stored.config.destination.connector == "filesystem":
        return {
            "tables": {},
            "error": "Fayl (CSV/Parquet) destination uchun SQL preview yo'q — fayllarni papkadan oching.",
        }
    pipeline = build_dlt_pipeline(stored.config)
    limit = max(1, min(int(limit), 100))
    dataset = stored.config.destination.dataset_name or "raw"

    try:
        user_tables = [
            t
            for t in pipeline.default_schema.tables.keys()
            if not t.startswith("_dlt")
        ]
        if not user_tables:
            return {"tables": {}, "error": "Hali hech qanday jadval yuklanmagan"}

        result: dict[str, Any] = {}
        with pipeline.sql_client() as client:
            for table_name in user_tables[:3]:
                try:
                    # Schema-qualified name required for DuckDB / multi-dataset destinations
                    fqn = f'"{dataset}"."{table_name}"'
                    # LIMIT is an int we control (not user SQL) — portable across destinations
                    with client.execute_query(
                        f"SELECT * FROM {fqn} LIMIT {int(limit)}"
                    ) as cursor:
                        columns = [d[0] for d in (cursor.description or [])]
                        rows = [list(r) for r in cursor.fetchall()]
                    result[table_name] = {"columns": columns, "rows": rows}
                except Exception as e:
                    result[table_name] = {"error": str(e), "columns": [], "rows": []}
        return {"tables": result}
    except Exception as e:
        return {"tables": {}, "error": str(e)}


def drop_resource(name: str, resource: str, store: ControlStore | None = None) -> dict[str, str]:
    """Selectively reset one resource (table + state).

    NOTE: ``pipeline.drop()`` in dlt deletes the *entire* local pipeline
    working dir — it does NOT take a resource name. Selective drop is done
    via the supported CLI: ``dlt pipeline <name> drop <resource>``.
    """
    import subprocess
    import sys

    _, stored = _load_stored(name, store)
    pipeline = build_dlt_pipeline(stored.config)
    res = (resource or "").strip()
    if not res:
        return {"status": "error", "detail": "Resource nomi bo'sh"}
    try:
        cmd = [
            sys.executable,
            "-m",
            "dlt",
            "pipeline",
            name,
            "drop",
            res,
            "--pipelines-dir",
            str(pipeline.pipelines_dir),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()[:400]
            return {"status": "error", "detail": f"Drop xatosi: {err or 'noma\'lum'}"}
        return {"status": "ok", "detail": f"Resource o'chirildi: {res}"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "detail": "Drop timeout (60s)"}
    except Exception as e:
        return {"status": "error", "detail": f"Drop xatosi: {e}"}
