"""chumoli.api.app — FastAPI: auth, pipelines, runs, scheduler, demo, recovery, async run."""
from __future__ import annotations

import threading
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError

from chumoli.connectors import register_builtin_connectors
from chumoli.core.logging_setup import configure_logging
import structlog
from chumoli.connectors.base import registry
from chumoli.core.config import (
    DestinationConfig,
    NotifyConfig,
    PipelineConfig,
    QualityConfig,
    ScheduleConfig,
    WriteDisposition,
)
from chumoli.core.destinations import (
    DEST_CONNECTION_SECRET_KEY,
    all_destinations,
    get_destination,
    is_destination_available,
)
from chumoli.core.pipeline_runner import (
    PipelineAlreadyRunning,
    drop_pending_packages,
    drop_resource,
    get_failed_jobs,
    get_preview_rows,
    get_running_pipelines,
    run_pipeline_by_name,
    sync_from_destination,
)
from chumoli.core.scheduler import (
    reload_jobs,
    start_scheduler,
    status as scheduler_status,
    stop_scheduler,
)
from chumoli.security.api_key import keys_match, load_or_create_api_key
from chumoli.store.control_store import ControlStore
from chumoli.store.run_store import RunStore

register_builtin_connectors()

log = structlog.get_logger("chumoli.api")


def _cors_origins() -> list[str]:
    raw = os.environ.get("CHUMOLI_CORS_ORIGINS", "").strip()
    if not raw:
        return ["http://127.0.0.1:8000", "http://localhost:8000"]
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(title="Chumoli", version="0.1.0", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def _static_dir() -> Path:
    # Installed wheel: chumoli/static (next to api/)
    # Dev / Docker: repo-root static/ or /app/static
    pkg_root = Path(__file__).resolve().parent.parent
    candidates = [
        Path("/app/static"),
        pkg_root / "static",
        Path(__file__).resolve().parents[3] / "static",
        Path(__file__).resolve().parents[2] / "static",
        Path.cwd() / "static",
    ]
    for p in candidates:
        if p.is_dir() and (p / "index.html").is_file():
            return p
    return candidates[0]


_STATIC = _static_dir()
if _STATIC.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_STATIC)), name="assets")

_API_KEY: str | None = None


def _get_api_key() -> str:
    global _API_KEY
    if _API_KEY is None:
        _API_KEY = load_or_create_api_key()
    return _API_KEY


async def require_api_key(request: Request) -> None:
    expected = _get_api_key()
    provided = request.headers.get("X-API-Key") or ""
    if not provided:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()
    if not provided or not keys_match(provided, expected):
        raise HTTPException(status_code=401, detail="API key kerak yoki noto'g'ri (X-API-Key)")


@app.on_event("startup")
def _startup() -> None:
    configure_logging()
    _get_api_key()
    try:
        start_scheduler()
    except Exception:
        log.exception("scheduler_startup_failed")


def _store() -> ControlStore:
    return ControlStore()


def _runs() -> RunStore:
    return RunStore()


class CreatePipelineBody(BaseModel):
    name: str
    connector_key: str
    source_params: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, str] = Field(default_factory=dict)
    destination: DestinationConfig = Field(
        default_factory=lambda: DestinationConfig(connector="duckdb", dataset_name="raw")
    )
    saved_destination_id: str | None = None
    write_disposition: WriteDisposition = WriteDisposition.REPLACE
    primary_key: list[str] = Field(default_factory=list)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)


class RunResponse(BaseModel):
    pipeline_name: str
    success: bool
    row_counts: dict[str, int]
    quality_passed: bool
    quality_details: list[dict[str, Any]]
    duration_seconds: float = 0.0
    total_rows: int = 0
    rows_per_second: float = 0.0
    new_rows: int = 0
    col_counts: dict[str, int] = Field(default_factory=dict)
    schema_changes: list[str] = Field(default_factory=list)
    cursor_last_value: Any = None
    is_first_run: bool = True
    peak_memory_mb: float = 0.0


# Background run jobs (in-memory; single uvicorn process). See review notes.
_RUN_JOBS: dict[str, dict[str, Any]] = {}
_RUN_JOBS_LOCK = threading.Lock()


def _cleanup_old_run_jobs() -> None:
    """Lazy sweep: drop finished async jobs older than 1 hour."""
    cutoff = time.time() - 3600
    with _RUN_JOBS_LOCK:
        stale = [
            jid
            for jid, j in list(_RUN_JOBS.items())
            if j.get("finished_at") is not None and j["finished_at"] < cutoff
        ]
        for jid in stale:
            _RUN_JOBS.pop(jid, None)


def _execute_run_job(job_id: str, name: str) -> None:
    _cleanup_old_run_jobs()
    with _RUN_JOBS_LOCK:
        job = _RUN_JOBS.get(job_id)
        if job is None:
            return
        job["status"] = "running"
    try:
        register_builtin_connectors()
        result = run_pipeline_by_name(name, store=_store())
        details = [
            {"passed": o.passed, "detail": o.detail} for o in result.quality_report.outcomes
        ]
        try:
            _runs().record(
                pipeline_name=result.pipeline_name,
                success=result.success,
                quality_passed=result.quality_report.all_passed,
                row_counts=result.row_counts,
                quality_details=details,
                trigger="manual-async",
                duration_seconds=result.duration_seconds,
                total_rows=result.total_rows,
                rows_per_second=result.rows_per_second,
                new_rows=result.new_rows,
                col_counts=result.col_counts,
                schema_changes=result.schema_changes,
                cursor_last_value=result.cursor_last_value,
                is_first_run=result.is_first_run,
                peak_memory_mb=result.peak_memory_mb,
            )
        except Exception:
            log.exception("run_record_failed", pipeline=name, job=job_id)
        job["status"] = "done"
        job["result"] = RunResponse(
            pipeline_name=result.pipeline_name,
            success=result.success,
            row_counts=result.row_counts,
            quality_passed=result.quality_report.all_passed,
            quality_details=details,
            duration_seconds=result.duration_seconds,
            total_rows=result.total_rows,
            rows_per_second=round(result.rows_per_second, 1),
            new_rows=result.new_rows,
            col_counts=result.col_counts,
            schema_changes=result.schema_changes,
            cursor_last_value=result.cursor_last_value,
            is_first_run=result.is_first_run,
            peak_memory_mb=result.peak_memory_mb,
        ).model_dump(mode="json")
    except PipelineAlreadyRunning as e:
        log.warning("pipeline_already_running", pipeline=name, job=job_id)
        job["status"] = "error"
        job["error"] = str(e)
    except Exception as e:
        log.exception("run_job_failed", pipeline=name, job=job_id)
        job["status"] = "error"
        try:
            from chumoli.core.demo_data import friendly_db_error

            job["error"] = friendly_db_error(e)
        except Exception:
            job["error"] = str(e)
    finally:
        job["finished_at"] = time.time()


@app.post("/api/pipelines/{name}/run/async", dependencies=[Depends(require_api_key)])
def run_pipeline_async(name: str, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Fon rejimida ishga tushiradi, darhol run_id qaytaradi (bloklamaydi).

    Katta dataset uchun: client poll qiladi; server bloklanmaydi.
    Parallel ikkinchi run → 409 (LoadPackageNotFound oldini olish).
    """
    if _store().load(name) is None:
        raise HTTPException(404, f"Pipeline '{name}' topilmadi")
    running = get_running_pipelines()
    if name in running:
        raise HTTPException(
            409,
            f"Pipeline '{name}' hozir ishga tushgan. Tugaguncha kuting.",
        )
    job_id = uuid.uuid4().hex
    with _RUN_JOBS_LOCK:
        _RUN_JOBS[job_id] = {
            "status": "queued",
            "pipeline_name": name,
            "started_at": time.time(),
            "finished_at": None,
            "result": None,
            "error": None,
        }
    background_tasks.add_task(_execute_run_job, job_id, name)
    return {"run_id": job_id, "status": "queued", "pipeline_name": name}


@app.get("/api/runs/jobs/{run_id}", dependencies=[Depends(require_api_key)])
def run_job_status(run_id: str) -> dict[str, Any]:
    with _RUN_JOBS_LOCK:
        job = _RUN_JOBS.get(run_id)
    if job is None:
        raise HTTPException(
            404,
            f"Job '{run_id}' topilmadi. Server qayta ishga tushgan bo'lishi mumkin — "
            "pipeline ro'yxati yoki Ishga tushirishlar bo'limidan statusni tekshiring.",
        )
    out = dict(job)
    # Attach live step if pipeline still running (long extracts)
    pname = job.get("pipeline_name")
    if pname and job.get("status") in ("queued", "running"):
        live = get_running_pipelines().get(pname)
        if live:
            out["step"] = live.get("step")
            out["rows_so_far"] = live.get("rows_so_far", 0)
            started = live.get("started_at") or job.get("started_at")
            if started:
                out["elapsed_seconds"] = round(time.time() - float(started), 1)
    return out


@app.get("/api/pipelines/running", dependencies=[Depends(require_api_key)])
def list_running_pipelines() -> dict[str, Any]:
    """Hozir ishlayotgan pipeline'lar (katta dataset / timeout diagnostikasi)."""
    running = get_running_pipelines()
    now = time.time()
    enriched = {}
    for name, info in running.items():
        started = float(info.get("started_at") or now)
        enriched[name] = {
            **info,
            "elapsed_seconds": round(now - started, 1),
        }
    return {"running": enriched}


@app.get("/api/pipelines/{name}/status", dependencies=[Depends(require_api_key)])
def pipeline_status(name: str) -> dict[str, Any]:
    """Pipeline ishlayaptimi va qaysi bosqichda."""
    if _store().load(name) is None:
        raise HTTPException(404, f"Pipeline '{name}' topilmadi")
    running = get_running_pipelines()
    if name in running:
        info = running[name]
        started = float(info.get("started_at") or time.time())
        return {
            "name": name,
            "running": True,
            "step": info.get("step", "run"),
            "elapsed_seconds": round(time.time() - started, 1),
            "rows_so_far": info.get("rows_so_far", 0),
        }
    recent = _runs().list_recent(limit=1, pipeline_name=name)
    last = recent[0] if recent else None
    return {
        "name": name,
        "running": False,
        "step": None,
        "elapsed_seconds": 0,
        "rows_so_far": 0,
        "last_run": last,
    }


@app.get("/api/pipelines/{name}/preview", dependencies=[Depends(require_api_key)])
def preview_pipeline_data(name: str, limit: int = 10) -> dict[str, Any]:
    """Yuklangan jadvaldan birinchi N qator."""
    if _store().load(name) is None:
        raise HTTPException(404, f"Pipeline '{name}' topilmadi")
    try:
        return get_preview_rows(name, store=_store(), limit=limit)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Preview xatosi: {e}") from e


@app.get("/")
def index() -> HTMLResponse:
    index_path = _STATIC / "index.html"
    if not index_path.is_file():
        raise HTTPException(404, "Dashboard topilmadi (static/index.html)")
    html = index_path.read_text(encoding="utf-8")
    key = _get_api_key()
    meta = f'<meta name="chumoli-api-key" content="{key}"/>'
    # Match real <meta> only — the name also appears in inline JS selectors.
    if re.search(r'<meta\s+name=["\']chumoli-api-key["\']', html):
        html = re.sub(r'<meta\s+name=["\']chumoli-api-key["\'][^>]*>', meta, html, count=1)
    else:
        html = html.replace("</head>", f"  {meta}\n</head>", 1)
    return HTMLResponse(html)


@app.get("/api/health")
def health() -> dict[str, object]:
    sched = scheduler_status()
    return {
        "status": "ok",
        "service": "chumoli",
        "version": "0.1.0",
        "scheduler_running": sched.get("running", False),
        "scheduler_jobs": sched.get("job_count", 0),
        "run_queue": sched.get("run_queue", {}),
        "runs": _runs().stats(),
    }


@app.get("/api/destinations", dependencies=[Depends(require_api_key)])
def list_destinations() -> list[dict[str, Any]]:
    return all_destinations()


class SavedDestinationBody(BaseModel):
    label: str
    connector: str
    connection: str | None = None
    dataset_name: str = "raw"
    save_as_new: bool = True  # unused on create; reserved


@app.get("/api/destinations/saved", dependencies=[Depends(require_api_key)])
def list_saved_destinations() -> list[dict[str, Any]]:
    """Named reusable destinations (no plaintext connection in list)."""
    return _store().list_saved_destinations()


@app.post("/api/destinations/saved", status_code=201, dependencies=[Depends(require_api_key)])
def create_saved_destination(body: SavedDestinationBody) -> dict[str, str]:
    dest_spec = get_destination(body.connector)
    if dest_spec is None:
        raise HTTPException(400, f"Noma'lum destination: {body.connector}")
    if not is_destination_available(body.connector):
        extra = dest_spec.dlt_extra or body.connector
        raise HTTPException(
            422,
            f"{dest_spec.label} o'rnatilmagan. "
            f'pip install "dlt[{extra}]" qiling yoki boshqa destination tanlang.',
        )
    if dest_spec.needs_connection and not (body.connection or "").strip():
        raise HTTPException(422, f"{dest_spec.label} uchun connection majburiy")
    try:
        dest_id = _store().save_destination(
            label=body.label,
            connector=body.connector,
            connection=body.connection,
            dataset_name=body.dataset_name or "raw",
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"status": "created", "id": dest_id}


@app.delete("/api/destinations/saved/{dest_id}", dependencies=[Depends(require_api_key)])
def delete_saved_destination(dest_id: str) -> dict[str, str]:
    ok = _store().delete_saved_destination(dest_id)
    if not ok:
        raise HTTPException(404, f"Saved destination '{dest_id}' topilmadi")
    return {"status": "deleted", "id": dest_id}


class SqlInspectBody(BaseModel):
    connection_string: str


@app.post("/api/connectors/sql_database/inspect", dependencies=[Depends(require_api_key)])
def inspect_sql_database(body: SqlInspectBody) -> dict[str, Any]:
    """Live DB schema scan — tables, cursor-friendly columns, database label."""
    from sqlalchemy.engine.url import make_url

    from chumoli.connectors.sql_database.connector import inspect_sql_schema

    try:
        schema = inspect_sql_schema(body.connection_string)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Inspect xatosi: {e}") from e

    tables = schema.get("tables") or []
    columns = schema.get("columns") or {}

    db_label = ""
    try:
        url = make_url(body.connection_string)
        db_label = url.database or ""
        if db_label and "/" in db_label:
            db_label = db_label.rsplit("/", 1)[-1]
    except Exception:
        pass

    return {
        "tables": tables,
        "count": len(tables),
        "database": db_label,
        "columns": columns,
    }


@app.get("/api/connectors", dependencies=[Depends(require_api_key)])
def list_connectors() -> list[dict[str, Any]]:
    out = []
    for m in registry.all_manifests():
        out.append(
            {
                "key": m.key,
                "label": m.label,
                "category": m.category.value if hasattr(m.category, "value") else str(m.category),
                "description": m.description,
                "fields": [f.model_dump(mode="json") for f in m.fields],
            }
        )
    return out


@app.get("/api/pipelines", dependencies=[Depends(require_api_key)])
def list_pipelines() -> list[dict[str, Any]]:
    items = _store().list_all()
    runs = _runs()
    out = []
    for item in items:
        recent = runs.list_recent(limit=1, pipeline_name=item["name"])
        last = recent[0] if recent else None
        item = dict(item)
        item["last_run"] = (
            {
                "success": last["success"],
                "quality_passed": last["quality_passed"],
                "finished_at": last["finished_at"],
                "trigger": last["trigger"],
                "row_counts": last["row_counts"],
                "error": last.get("error"),
                "duration_seconds": last.get("duration_seconds", 0),
                "total_rows": last.get("total_rows", 0),
                "rows_per_second": last.get("rows_per_second", 0),
                "new_rows": last.get("new_rows", 0),
                "col_counts": last.get("col_counts") or {},
                "schema_changes": last.get("schema_changes") or [],
                "cursor_last_value": last.get("cursor_last_value"),
                "is_first_run": last.get("is_first_run", True),
            }
            if last
            else None
        )
        out.append(item)
    return out


@app.get("/api/pipelines/{name}", dependencies=[Depends(require_api_key)])
def get_pipeline(name: str) -> dict[str, Any]:
    stored = _store().load(name)
    if stored is None:
        raise HTTPException(404, f"Pipeline '{name}' topilmadi")
    return {
        "name": stored.config.name,
        "connector_key": stored.config.connector_key,
        "config": stored.config.model_dump(mode="json"),
        "secret_keys": list(stored.secrets.keys()),
    }


@app.post("/api/pipelines", status_code=201, dependencies=[Depends(require_api_key)])
def create_pipeline(body: CreatePipelineBody) -> dict[str, str]:
    register_builtin_connectors()
    try:
        manifest = registry.get_manifest(body.connector_key)
    except KeyError as e:
        raise HTTPException(400, str(e)) from e

    secret_keys = set(manifest.secret_keys())
    params = dict(body.source_params)
    secrets = dict(body.secrets)
    leaked = [k for k in params if k in secret_keys]
    if leaked:
        raise HTTPException(
            422,
            f"Maxfiy maydon '{leaked[0]}' source_params ichida yuborildi — secrets orqali yuboring",
        )
    for k in secret_keys:
        secrets.setdefault(k, "")

    # Edit: empty secret means "keep existing" — do not overwrite with blank.
    existing = _store().load(body.name)
    if existing is not None:
        for k in secret_keys:
            if not secrets.get(k):
                secrets[k] = existing.secrets.get(k, "")

    errors = manifest.validate_values({**params, **secrets})
    if errors:
        raise HTTPException(422, {"validation_errors": errors})

    dest = body.destination.model_copy()
    if body.saved_destination_id:
        saved = _store().get_saved_destination(body.saved_destination_id)
        if saved is None:
            raise HTTPException(
                404, f"Saved destination '{body.saved_destination_id}' topilmadi"
            )
        dest = DestinationConfig(
            connector=saved["connector"],
            connection=saved.get("connection"),
            dataset_name=saved.get("dataset_name") or dest.dataset_name or "raw",
        )

    dest_spec = get_destination(dest.connector)
    if dest_spec is None:
        raise HTTPException(400, f"Noma'lum destination: {dest.connector}")
    if not is_destination_available(dest.connector):
        extra = dest_spec.dlt_extra or dest.connector
        raise HTTPException(
            422,
            f"{dest_spec.label} o'rnatilmagan. "
            f'pip install "dlt[{extra}]" qiling yoki boshqa destination tanlang.',
        )
    if dest_spec.needs_connection and not (dest.connection or "").strip():
        raise HTTPException(422, f"{dest_spec.label} uchun connection majburiy")

    if dest.connection:
        secrets[DEST_CONNECTION_SECRET_KEY] = dest.connection
        dest.connection = None

    quality = body.quality

    try:
        config = PipelineConfig(
            name=body.name,
            connector_key=body.connector_key,
            source_params=params,
            destination=dest,
            write_disposition=body.write_disposition,
            primary_key=body.primary_key,
            schedule=body.schedule,
            quality=quality,
            notify=body.notify,
        )
    except ValidationError as e:
        raise HTTPException(422, e.errors()) from e
    try:
        _store().save(config, secrets, manifest)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if config.schedule.kind.value == "airflow":
        raise HTTPException(
            422,
            "kind=airflow ichki scheduler tomonidan boshqarilmaydi. manual / interval / daily_at ishlating.",
        )
    # Har doim reload: interval 1→60, interval→manual, daily_at o'zgarishi —
    # eski job o'chirilishi shart. kind=manual bo'lsa ham skip qilinmasin.
    try:
        reload_jobs()
    except Exception:
        log.exception("scheduler_reload_failed", action="create", pipeline=config.name)
    return {"status": "created", "name": config.name}


@app.delete("/api/pipelines/{name}", dependencies=[Depends(require_api_key)])
def delete_pipeline(name: str) -> dict[str, str]:
    _store().delete(name)
    try:
        reload_jobs()
    except Exception:
        log.exception("scheduler_reload_failed", action="delete", pipeline=name)
    return {"status": "deleted", "name": name}


@app.post("/api/pipelines/{name}/run", dependencies=[Depends(require_api_key)])
def run_pipeline(name: str) -> RunResponse:
    register_builtin_connectors()
    try:
        result = run_pipeline_by_name(name, store=_store())
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except PipelineAlreadyRunning as e:
        raise HTTPException(409, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Run xatosi: {e}") from e

    details = [{"passed": o.passed, "detail": o.detail} for o in result.quality_report.outcomes]
    try:
        _runs().record(
            pipeline_name=result.pipeline_name,
            success=result.success,
            quality_passed=result.quality_report.all_passed,
            row_counts=result.row_counts,
            quality_details=details,
            trigger="manual",
            duration_seconds=result.duration_seconds,
            total_rows=result.total_rows,
            rows_per_second=result.rows_per_second,
            new_rows=result.new_rows,
            col_counts=result.col_counts,
            schema_changes=result.schema_changes,
            cursor_last_value=result.cursor_last_value,
            is_first_run=result.is_first_run,
            peak_memory_mb=result.peak_memory_mb,
        )
    except Exception:
        log.exception("run_record_failed", pipeline=result.pipeline_name)
    return RunResponse(
        pipeline_name=result.pipeline_name,
        success=result.success,
        row_counts=result.row_counts,
        quality_passed=result.quality_report.all_passed,
        quality_details=details,
        duration_seconds=result.duration_seconds,
        total_rows=result.total_rows,
        rows_per_second=round(result.rows_per_second, 1),
        new_rows=result.new_rows,
        col_counts=result.col_counts,
        schema_changes=result.schema_changes,
        cursor_last_value=result.cursor_last_value,
        is_first_run=result.is_first_run,
        peak_memory_mb=result.peak_memory_mb,
    )


def _record_and_demo_response(result: Any, duck_path: str, *, label: str) -> dict[str, Any]:
    details = [{"passed": o.passed, "detail": o.detail} for o in result.quality_report.outcomes]
    try:
        _runs().record(
            pipeline_name=result.pipeline_name,
            success=result.success,
            quality_passed=result.quality_report.all_passed,
            row_counts=result.row_counts,
            quality_details=details,
            trigger="demo",
            duration_seconds=result.duration_seconds,
            total_rows=result.total_rows,
            rows_per_second=result.rows_per_second,
            new_rows=result.new_rows,
            col_counts=result.col_counts,
            schema_changes=result.schema_changes,
            cursor_last_value=result.cursor_last_value,
            is_first_run=result.is_first_run,
            peak_memory_mb=result.peak_memory_mb,
        )
    except Exception:
        log.exception("run_record_failed", pipeline=result.pipeline_name, trigger="demo")
    return {
        "pipeline_name": result.pipeline_name,
        "success": result.success,
        "row_counts": result.row_counts,
        "total_rows": result.total_rows,
        "duration_seconds": round(result.duration_seconds, 3),
        "rows_per_second": round(result.rows_per_second, 1),
        "destination": duck_path,
        "quality_passed": result.quality_report.all_passed,
        "label": label,
    }


@app.post("/api/demo/volume", dependencies=[Depends(require_api_key)])
def demo_volume(row_count: int = 100000) -> dict[str, Any]:
    register_builtin_connectors()
    row_count = max(1000, min(int(row_count), 1_000_000))
    name = "demo_volume"
    manifest = registry.get_manifest("synthetic_volume")
    from chumoli.core.paths import examples_dir, ensure_runtime_dirs
    ensure_runtime_dirs()
    duck_path = str(examples_dir() / "demo_volume.duckdb")
    config = PipelineConfig(
        name=name,
        connector_key="synthetic_volume",
        source_params={"row_count": str(row_count), "batch_label": "wow"},
        destination=DestinationConfig(
            connector="duckdb", connection=duck_path, dataset_name="demo"
        ),
        write_disposition=WriteDisposition.REPLACE,
    )
    _store().save(config, {}, manifest)
    result = run_pipeline_by_name(name, store=_store())
    return _record_and_demo_response(result, duck_path, label="Synthetic volume")


@app.post("/api/demo/sql", dependencies=[Depends(require_api_key)])
def demo_sql() -> dict[str, Any]:
    """Namuna SQLite (orders+customers) → local DuckDB. Birinchi yuklash ishqalansiz."""
    from chumoli.core.demo_data import sample_sqlite_path, sample_sqlite_url

    register_builtin_connectors()
    sample_sqlite_path()  # ensure file exists
    name = "demo_sql_orders"
    manifest = registry.get_manifest("sql_database")
    from chumoli.core.paths import examples_dir, ensure_runtime_dirs
    ensure_runtime_dirs()
    duck_path = str(examples_dir() / "demo_sql.duckdb")
    config = PipelineConfig(
        name=name,
        connector_key="sql_database",
        source_params={
            "table_names": "orders, customers",
            "backend": "pyarrow",
            "chunk_size": "100000",
        },
        destination=DestinationConfig(
            connector="duckdb", connection=duck_path, dataset_name="demo"
        ),
        write_disposition=WriteDisposition.REPLACE,
    )
    _store().save(config, {"connection_string": sample_sqlite_url()}, manifest)
    try:
        result = run_pipeline_by_name(name, store=_store())
    except Exception as e:
        from chumoli.core.demo_data import friendly_db_error

        raise HTTPException(500, friendly_db_error(e)) from e
    out = _record_and_demo_response(result, duck_path, label="SQL → DuckDB (namuna)")
    out["source"] = sample_sqlite_url()
    out["tables"] = result.row_counts
    return out


@app.post("/api/demo/rest", dependencies=[Depends(require_api_key)])
def demo_rest() -> dict[str, Any]:
    """Ommaviy JSONPlaceholder API → DuckDB (~1 daqiqada)."""
    register_builtin_connectors()
    name = "demo_rest_posts"
    manifest = registry.get_manifest("rest_api")
    from chumoli.core.paths import examples_dir, ensure_runtime_dirs
    ensure_runtime_dirs()
    duck_path = str(examples_dir() / "demo_rest.duckdb")
    config = PipelineConfig(
        name=name,
        connector_key="rest_api",
        source_params={
            "base_url": "https://jsonplaceholder.typicode.com",
            "endpoint": "/posts",
            "auth_type": "none",
        },
        destination=DestinationConfig(
            connector="duckdb", connection=duck_path, dataset_name="demo"
        ),
        write_disposition=WriteDisposition.REPLACE,
    )
    _store().save(config, {"secret_value": ""}, manifest)
    try:
        result = run_pipeline_by_name(name, store=_store())
    except Exception as e:
        from chumoli.core.demo_data import friendly_db_error

        raise HTTPException(500, friendly_db_error(e)) from e
    out = _record_and_demo_response(result, duck_path, label="REST API → DuckDB")
    out["source"] = "https://jsonplaceholder.typicode.com/posts"
    out["tables"] = result.row_counts
    return out


@app.get("/api/runs", dependencies=[Depends(require_api_key)])
def list_runs(limit: int = 50, pipeline_name: str | None = None) -> list[dict[str, object]]:
    return _runs().list_recent(limit=limit, pipeline_name=pipeline_name)


@app.get("/api/runs/stats", dependencies=[Depends(require_api_key)])
def run_stats() -> dict[str, object]:
    return _runs().stats()


@app.get("/api/scheduler", dependencies=[Depends(require_api_key)])
def get_scheduler() -> dict[str, object]:
    return scheduler_status()


@app.post("/api/scheduler/start", dependencies=[Depends(require_api_key)])
def scheduler_start() -> dict[str, object]:
    return start_scheduler()


@app.post("/api/scheduler/stop", dependencies=[Depends(require_api_key)])
def scheduler_stop() -> dict[str, object]:
    return stop_scheduler()


@app.post("/api/scheduler/reload", dependencies=[Depends(require_api_key)])
def scheduler_reload() -> dict[str, object]:
    return reload_jobs()


@app.get("/api/settings/telegram", dependencies=[Depends(require_api_key)])
def get_telegram_settings() -> dict[str, Any]:
    from chumoli.core.notify import TELEGRAM_BOT_TOKEN_KEY

    token = _store().get_secret_setting(TELEGRAM_BOT_TOKEN_KEY)
    return {"configured": bool(token)}


@app.put("/api/settings/telegram", dependencies=[Depends(require_api_key)])
def put_telegram_settings(body: dict[str, Any]) -> dict[str, Any]:
    from chumoli.core.notify import TELEGRAM_BOT_TOKEN_KEY

    token = (body.get("bot_token") or "").strip()
    if not token:
        raise HTTPException(422, "bot_token majburiy")
    _store().set_secret_setting(TELEGRAM_BOT_TOKEN_KEY, token)
    return {"configured": True}


@app.get("/api/pipelines/{name}/failed-jobs", dependencies=[Depends(require_api_key)])
def api_failed_jobs(name: str) -> list[dict[str, str]]:
    try:
        return get_failed_jobs(name, store=_store())
    except KeyError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/pipelines/{name}/recover/{action}", dependencies=[Depends(require_api_key)])
def api_recover(name: str, action: str, resource: str | None = None) -> dict[str, str]:
    try:
        if action == "sync":
            return sync_from_destination(name, store=_store())
        if action == "drop-pending":
            return drop_pending_packages(name, store=_store())
        if action == "drop-resource":
            if not resource:
                raise HTTPException(422, "resource query param majburiy")
            return drop_resource(name, resource, store=_store())
        raise HTTPException(400, f"Noma'lum action: {action}")
    except KeyError as e:
        raise HTTPException(404, str(e)) from e


def main() -> None:
    import uvicorn

    uvicorn.run("chumoli.api.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
