from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException

from incident_investigator import __version__
from incident_investigator.baseline import BaselineClient, BaselineRunner, OpenAIBaselineClient
from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.config import Settings, get_settings
from incident_investigator.contracts import InvestigationRequest
from incident_investigator.persistence import RunStore
from incident_investigator.persistence.run_store import utc_now
from incident_investigator.presentation import DemoReportService

ClientFactory = Callable[[Settings], BaselineClient]


def _default_client_factory(settings: Settings) -> BaselineClient:
    if not settings.openai_api_key or not settings.openai_model:
        raise RuntimeError("OPENAI_API_KEY and OPENAI_MODEL are required")
    return OpenAIBaselineClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_retries=settings.openai_max_retries,
        reasoning_effort=settings.openai_reasoning_effort,
    )


def create_app(
    project_root: Path | None = None,
    client_factory: ClientFactory | None = None,
) -> FastAPI:
    settings = get_settings(project_root)
    loader = AgentVisibleCaseLoader(settings.cases_root)
    report_service = DemoReportService(settings.project_root, loader)
    factory = client_factory or _default_client_factory
    application = FastAPI(title="Contact Center Incident Investigator", version=__version__)

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @application.get("/api/incidents")
    def list_incidents() -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in loader.list_incidents()]

    @application.get("/api/incidents/{incident_id}")
    def get_incident(incident_id: str) -> dict[str, Any]:
        try:
            return loader.load(incident_id).model_dump(mode="json")
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.get("/api/demo/incidents/{incident_id}/report")
    def get_demo_report(
        incident_id: str, mode: Literal["default", "audit"] = "default"
    ) -> dict[str, Any]:
        try:
            return report_service.build(incident_id, mode)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.post("/api/investigations")
    def investigate(request: InvestigationRequest) -> dict[str, Any]:
        try:
            client = factory(settings)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        store = RunStore(settings.project_root)
        benchmark_manifest = (
            settings.project_root / "benchmark" / settings.benchmark_version / "manifest.json"
        )
        store.create_manifest(
            {
                "system_version": request.system_version,
                "benchmark_version": settings.benchmark_version,
                "model": client.model,
                "scope": "single_case_api",
                "model_configuration": {
                    "sampling_parameters": "provider_defaults",
                    "reasoning_effort": settings.openai_reasoning_effort,
                },
                "openai_sdk_version": version("openai"),
                "max_retries": settings.openai_max_retries,
                "prompt_version": "baseline_v1",
                "benchmark_manifest_sha256": hashlib.sha256(
                    benchmark_manifest.read_bytes()
                ).hexdigest(),
            }
        )
        runner = BaselineRunner(loader, client, store)
        try:
            diagnosis = runner.run_case(request.incident_id)
        except (FileNotFoundError, ValueError) as exc:
            store.write_error(request.incident_id, exc)
            store.update_manifest(status="FAILED", completed_at=utc_now())
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        store.update_manifest(status="COMPLETED", completed_at=utc_now(), case_count=1)
        return {
            "run_id": store.run_id,
            "status": "COMPLETED",
            "result": diagnosis.model_dump(mode="json"),
        }

    @application.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        try:
            UUID(run_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Unknown run") from exc
        store = RunStore(settings.project_root, run_id=run_id)
        if not store.manifest_path.is_file():
            raise HTTPException(status_code=404, detail="Unknown run")
        predictions = {}
        prediction_root = store.result_root / "predictions"
        if prediction_root.is_dir():
            for path in sorted(prediction_root.glob("CC-*.json")):
                predictions[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        return {"manifest": store.read_json(store.manifest_path), "predictions": predictions}

    return application


app = create_app()
