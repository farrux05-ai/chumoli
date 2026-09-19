"""uzpipe.api.app — FastAPI: auth, pipelines, runs, scheduler, demo, recovery, async run."""
from __future__ import annotations

import logging
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

from uzpipe.connectors import register_builtin_connectors
from uzpipe.connectors.base import registry
from uzpipe.core.config import (
    DestinationConfig,
    NotifyConfig,
    PipelineConfig,
    QualityConfig,
    ScheduleConfig,
    WriteDisposition,
)
from uzpipe.core.destinations import (
    DEST_CONNECTION_SECRET_KEY,
    all_destinations,
    get_destination,
)
from uzpipe.core.pipeline_runner import (
    drop_pending_packages,
    drop_resource,
    get_failed_jobs,
    run_pipeline_by_name,
    sync_from_destination,
)
from uzpipe.core.scheduler import (
    reload_jobs,
    start_scheduler,
    status as scheduler_status,
    stop_scheduler,
)
from uzpipe.security.api_key import keys_match, load_or_create_api_key
from uzpipe.store.control_store import ControlStore
from uzpipe.store.run_store import RunStore

register_builtin_connectors()

log = logging.getLogger("uzpipe.api")


def _cors_origins() -> list[str]:
    raw = os.environ.get("UZPIPE_CORS_ORIGINS", "").strip()
    if not raw:
        return ["http://127.0.0.1:8000", "http://localhost:8000"]
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(title="UzPipe", version="0.1.0", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def _static_dir() -> Path:
    candidates = [
        Path("/app/static"),
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


# Background run jobs (in-memory; single uvicorn process). See review notes.
_RUN_JOBS: dict[str, dict[str, Any]] = {}


def _cleanup_old_run_jobs() -> None:
    """Lazy sweep: drop finished async jobs older than 1 hour."""
    cutoff = time.time() - 3600
    stale = [
        jid
        for jid, j in list(_RUN_JOBS.items())
        if j.get("finished_at") is not None and j["finished_at"] < cutoff
    ]
    for jid in stale:
        _RUN_JOBS.pop(jid, None)


def _execute_run_job(job_id: str, name: str) -> None:
    _cleanup_old_run_jobs()
    job = _RUN_JOBS[job_id]
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
            )
        except Exception:
            log.exception("run_record_failed pipeline=%s job=%s", name, job_id)
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
        ).model_dump(mode="json")
    except Exception as e:
        log.exception("run_job_failed pipeline=%s job=%s", name, job_id)
        job["status"] = "error"
        try:
            from uzpipe.core.demo_data import friendly_db_error

            job["error"] = friendly_db_error(e)
        except Exception:
            job["error"] = str(e)
    finally:
        job["finished_at"] = time.time()


@app.post("/api/pipelines/{name}/run/async", dependencies=[Depends(require_api_key)])
def run_pipeline_async(name: str, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Fon rejimida ishga tushiradi, darhol run_id qaytaradi (bloklamaydi)."""
    if _store().load(name) is None:
        raise HTTPException(404, f"Pipeline '{name}' topilmadi")
    job_id = uuid.uuid4().hex
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
    job = _RUN_JOBS.get(run_id)
    if job is None:
        raise HTTPException(404, f"Job '{run_id}' topilmadi")
    return job


@app.get("/")
def index() -> HTMLResponse:
    index_path = _STATIC / "index.html"
    if not index_path.is_file():
        raise HTTPException(404, "Dashboard topilmadi (static/index.html)")
    html = index_path.read_text(encoding="utf-8")
    key = _get_api_key()
    meta = f'<meta name="uzpipe-api-key" content="{key}"/>'
    # Match real <meta> only — the name also appears in inline JS selectors.
    if re.search(r'<meta\s+name=["\']uzpipe-api-key["\']', html):
        html = re.sub(r'<meta\s+name=["\']uzpipe-api-key["\'][^>]*>', meta, html, count=1)
    else:
        html = html.replace("</head>", f"  {meta}\n</head>", 1)
    return HTMLResponse(html)


@app.get("/api/health")
def health() -> dict[str, object]:
    sched = scheduler_status()
    return {
        "status": "ok",
        "service": "uzpipe",
        "version": "0.1.0",
        "scheduler_running": sched.get("running", False),
        "scheduler_jobs": sched.get("job_count", 0),
        "runs": _runs().stats(),
    }


@app.get("/api/destinations", dependencies=[Depends(require_api_key)])
def list_destinations() -> list[dict[str, Any]]:
    return all_destinations()


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

    errors = manifest.validate_values({**params, **secrets})
    if errors:
        raise HTTPException(422, {"validation_errors": errors})

    dest_spec = get_destination(body.destination.connector)
    if dest_spec is None:
        raise HTTPException(400, f"Noma'lum destination: {body.destination.connector}")
    if dest_spec.needs_connection and not (body.destination.connection or "").strip():
        raise HTTPException(422, f"{dest_spec.label} uchun connection majburiy")

    dest = body.destination.model_copy()
    if dest.connection:
        secrets[DEST_CONNECTION_SECRET_KEY] = dest.connection
        dest.connection = None

    try:
        config = PipelineConfig(
            name=body.name,
            connector_key=body.connector_key,
            source_params=params,
            destination=dest,
            write_disposition=body.write_disposition,
            primary_key=body.primary_key,
            schedule=body.schedule,
            quality=body.quality,
            notify=body.notify,
        )
    except ValidationError as e:
        raise HTTPException(422, e.errors()) from e
    try:
        _store().save(config, secrets, manifest)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if config.schedule.kind.value == "interval":
        try:
            reload_jobs()
        except Exception:
            log.exception("scheduler_reload_failed after create name=%s", config.name)
    return {"status": "created", "name": config.name}


@app.delete("/api/pipelines/{name}", dependencies=[Depends(require_api_key)])
def delete_pipeline(name: str) -> dict[str, str]:
    _store().delete(name)
    try:
        reload_jobs()
    except Exception:
        log.exception("scheduler_reload_failed after delete name=%s", name)
    return {"status": "deleted", "name": name}


@app.post("/api/pipelines/{name}/run", dependencies=[Depends(require_api_key)])
def run_pipeline(name: str) -> RunResponse:
    register_builtin_connectors()
    try:
        result = run_pipeline_by_name(name, store=_store())
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
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
        )
    except Exception:
        log.exception("run_record_failed pipeline=%s", result.pipeline_name)
    return RunResponse(
        pipeline_name=result.pipeline_name,
        success=result.success,
        row_counts=result.row_counts,
        quality_passed=result.quality_report.all_passed,
        quality_details=details,
        duration_seconds=result.duration_seconds,
        total_rows=result.total_rows,
        rows_per_second=round(result.rows_per_second, 1),
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
        )
    except Exception:
        log.exception("run_record_failed pipeline=%s trigger=demo", result.pipeline_name)
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
    duck_path = str(Path("/tmp") / "uzpipe_volume_demo.duckdb")
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
    from uzpipe.core.demo_data import sample_sqlite_path, sample_sqlite_url

    register_builtin_connectors()
    sample_sqlite_path()  # ensure file exists
    name = "demo_sql_orders"
    manifest = registry.get_manifest("sql_database")
    duck_path = str(Path.home() / ".uzpipe" / "examples" / "demo_sql.duckdb")
    config = PipelineConfig(
        name=name,
        connector_key="sql_database",
        source_params={"table_names": "orders, customers"},
        destination=DestinationConfig(
            connector="duckdb", connection=duck_path, dataset_name="demo"
        ),
        write_disposition=WriteDisposition.REPLACE,
    )
    _store().save(config, {"connection_string": sample_sqlite_url()}, manifest)
    try:
        result = run_pipeline_by_name(name, store=_store())
    except Exception as e:
        from uzpipe.core.demo_data import friendly_db_error

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
    duck_path = str(Path.home() / ".uzpipe" / "examples" / "demo_rest.duckdb")
    config = PipelineConfig(
        name=name,
        connector_key="rest_api",
        source_params={
            "base_url": "https://jsonplaceholder.typicode.com",
            "endpoint": "/posts",
            "auth_type": "none",
            "auth_key_name": "Authorization",
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
        from uzpipe.core.demo_data import friendly_db_error

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
    from uzpipe.core.notify import TELEGRAM_BOT_TOKEN_KEY

    token = _store().get_secret_setting(TELEGRAM_BOT_TOKEN_KEY)
    return {"configured": bool(token)}


@app.put("/api/settings/telegram", dependencies=[Depends(require_api_key)])
def put_telegram_settings(body: dict[str, Any]) -> dict[str, Any]:
    from uzpipe.core.notify import TELEGRAM_BOT_TOKEN_KEY

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

    uvicorn.run("uzpipe.api.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
