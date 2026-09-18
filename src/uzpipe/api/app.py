"""
uzpipe.api.app
================

HTML dashboard va tashqi klientlar uchun yupqa FastAPI qatlami.

Faqat uchta fundament chaqiruvini ochadi:
  - registry.all_manifests()
  - ControlStore.save / list_all / load / delete
  - run_pipeline_by_name()

Yangi biznes-mantiq yo'q — CLI bilan bir xil entry point'lar.
"""

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
from uzpipe.core.pipeline_runner import run_pipeline_by_name
from uzpipe.store.control_store import ControlStore

register_builtin_connectors()

app = FastAPI(title="UzPipe", version="0.1.0", docs_url="/api/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC = Path(__file__).resolve().parents[3] / "static"
if _STATIC.is_dir():
    app.mount("/assets", StaticFiles(directory=_STATIC), name="assets")


def _store() -> ControlStore:
    return ControlStore()


# ── request / response models ───────────────────────────────────────────────


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


# ── routes ──────────────────────────────────────────────────────────────────


@app.get("/")
def index() -> FileResponse:
    index_path = _STATIC / "index.html"
    if not index_path.is_file():
        raise HTTPException(404, "Dashboard topilmadi (static/index.html)")
    return FileResponse(index_path)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "uzpipe"}


@app.get("/api/connectors")
def list_connectors() -> list[dict[str, Any]]:
    """Manifest-driven connector katalogi — forma shu yerdan chiziladi."""
    out: list[dict[str, Any]] = []
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
    return _store().list_all()


@app.get("/api/pipelines/{name}")
def get_pipeline(name: str) -> dict[str, Any]:
    stored = _store().load(name)
    if stored is None:
        raise HTTPException(404, f"Pipeline '{name}' topilmadi")
    # secrets qaytarilmaydi
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

    # secret field'larni source_params dan ajratish
    secret_keys = set(manifest.secret_keys())
    params = dict(body.source_params)
    secrets = dict(body.secrets)
    for k in list(params.keys()):
        if k in secret_keys:
            if k not in secrets or secrets[k] is None or secrets[k] == "":
                secrets[k] = str(params.pop(k))
            else:
                params.pop(k, None)
    # optional secret maydonlar (masalan rest_api.secret_value auth=none)
    # ControlStore barcha secret_keys ni kutadi — yo'qlarini bo'sh string bilan to'ldiramiz
    for k in secret_keys:
        secrets.setdefault(k, "")

    # forma validatsiyasi (secret'siz params + secrets birga)
    combined = {**params, **secrets}
    errors = manifest.validate_values(combined)
    if errors:
        raise HTTPException(422, {"validation_errors": errors})

    config = PipelineConfig(
        name=body.name,
        connector_key=body.connector_key,
        source_params=params,
        destination=body.destination,
        write_disposition=body.write_disposition,
        primary_key=body.primary_key,
        schedule=body.schedule,
        quality=body.quality,
    )
    try:
        _store().save(config, secrets, manifest)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
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

    details = [
        {"passed": o.passed, "detail": o.detail}
        for o in result.quality_report.outcomes
    ]
    return RunResponse(
        pipeline_name=result.pipeline_name,
        success=result.success,
        row_counts=result.row_counts,
        quality_passed=result.quality_report.all_passed,
        quality_details=details,
    )


def main() -> None:
    import uvicorn

    uvicorn.run("uzpipe.api.app:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
