"""uzpipe.api.app — FastAPI: registry, ControlStore, RunStore, scheduler, demo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from uzpipe.connectors import register_builtin_connectors
from uzpipe.connectors.base import registry
from uzpipe.core.config import (
    DestinationConfig,
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
from uzpipe.core.pipeline_runner import run_pipeline_by_name
from uzpipe.core.scheduler import (
    reload_jobs,
    start_scheduler,
    status as scheduler_status,
    stop_scheduler,
)
from uzpipe.store.control_store import ControlStore
from uzpipe.store.run_store import RunStore

register_builtin_connectors()

app = FastAPI(title="UzPipe", version="0.1.0", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


def _static_dir() -> Path:
    """Resolve static/ for Docker (/app/static), repo checkout, or cwd."""
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


@app.on_event("startup")
def _startup() -> None:
    try:
        start_scheduler()
    except Exception:
        pass


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


class RunResponse(BaseModel):
    pipeline_name: str
    success: bool
    row_counts: dict[str, int]
    quality_passed: bool
    quality_details: list[dict[str, Any]]
    duration_seconds: float = 0.0
    total_rows: int = 0
    rows_per_second: float = 0.0


@app.get("/")
def index() -> FileResponse:
    index_path = _STATIC / "index.html"
    if not index_path.is_file():
        raise HTTPException(404, "Dashboard topilmadi (static/index.html)")
    return FileResponse(index_path)


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


@app.get("/api/destinations")
def list_destinations() -> list[dict[str, Any]]:
    return all_destinations()


@app.get("/api/connectors")
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


@app.get("/api/pipelines")
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


@app.get("/api/pipelines/{name}")
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


@app.post("/api/pipelines", status_code=201)
def create_pipeline(body: CreatePipelineBody) -> dict[str, str]:
    register_builtin_connectors()
    try:
        manifest = registry.get_manifest(body.connector_key)
    except KeyError as e:
        raise HTTPException(400, str(e)) from e

    secret_keys = set(manifest.secret_keys())
    params = dict(body.source_params)
    secrets = dict(body.secrets)
    for k in list(params.keys()):
        if k in secret_keys:
            if k not in secrets or secrets[k] is None or secrets[k] == "":
                secrets[k] = str(params.pop(k))
            else:
                params.pop(k, None)
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

    config = PipelineConfig(
        name=body.name,
        connector_key=body.connector_key,
        source_params=params,
        destination=dest,
        write_disposition=body.write_disposition,
        primary_key=body.primary_key,
        schedule=body.schedule,
        quality=body.quality,
    )
    try:
        _store().save(config, secrets, manifest)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if config.schedule.kind.value == "interval":
        try:
            reload_jobs()
        except Exception:
            pass
    return {"status": "created", "name": config.name}


@app.delete("/api/pipelines/{name}")
def delete_pipeline(name: str) -> dict[str, str]:
    _store().delete(name)
    return {"status": "deleted", "name": name}


@app.post("/api/pipelines/{name}/run")
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
        pass
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


@app.post("/api/demo/volume")
def demo_volume(row_count: int = 100000) -> dict[str, Any]:
    """1-click volume demo: synthetic → DuckDB."""
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
        pass
    return {
        "pipeline_name": result.pipeline_name,
        "success": result.success,
        "row_counts": result.row_counts,
        "total_rows": result.total_rows,
        "duration_seconds": result.duration_seconds,
        "rows_per_second": round(result.rows_per_second, 1),
        "destination": duck_path,
        "quality_passed": result.quality_report.all_passed,
    }


@app.get("/api/runs")
def list_runs(limit: int = 50, pipeline_name: str | None = None) -> list[dict[str, object]]:
    return _runs().list_recent(limit=limit, pipeline_name=pipeline_name)


@app.get("/api/runs/stats")
def run_stats() -> dict[str, object]:
    return _runs().stats()


@app.get("/api/scheduler")
def get_scheduler() -> dict[str, object]:
    return scheduler_status()


@app.post("/api/scheduler/start")
def scheduler_start() -> dict[str, object]:
    return start_scheduler()


@app.post("/api/scheduler/stop")
def scheduler_stop() -> dict[str, object]:
    return stop_scheduler()


@app.post("/api/scheduler/reload")
def scheduler_reload() -> dict[str, object]:
    return reload_jobs()


def main() -> None:
    import uvicorn

    uvicorn.run("uzpipe.api.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
