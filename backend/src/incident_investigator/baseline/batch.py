from __future__ import annotations

import hashlib
from importlib.metadata import version

from incident_investigator.benchmark.loader import AgentVisibleCaseLoader
from incident_investigator.config import Settings
from incident_investigator.evaluation import GroundTruthLoader, score_benchmark
from incident_investigator.persistence import RunStore
from incident_investigator.persistence.run_store import utc_now

from .client import BaselineClient, OpenAIBaselineClient
from .runner import BaselineRunner


def run_baseline_batch(
    settings: Settings,
    client: BaselineClient,
) -> tuple[str, dict[str, object]]:
    loader = AgentVisibleCaseLoader(settings.cases_root)
    store = RunStore(settings.project_root)
    benchmark_manifest = (
        settings.project_root / "benchmark" / settings.benchmark_version / "manifest.json"
    )
    store.create_manifest(
        {
            "system_version": "baseline",
            "benchmark_version": settings.benchmark_version,
            "model": client.model,
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
    predictions = {}
    failures = 0
    for summary in loader.list_incidents():
        try:
            predictions[summary.incident_id] = runner.run_case(summary.incident_id)
        except Exception as exc:
            failures += 1
            predictions[summary.incident_id] = None
            store.write_error(summary.incident_id, exc)
            store.append_trajectory(
                summary.incident_id,
                {
                    "step_number": 99,
                    "agent_stage": "baseline",
                    "event_type": "error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
            )

    truths = GroundTruthLoader(settings.ground_truth_root).load_all()
    scores = score_benchmark(predictions, truths)
    store.write_json(store.result_root / "scores.json", scores.model_dump(mode="json"))
    store.write_text(store.result_root / "comparison.csv", scores.to_csv())
    store.write_text(store.result_root / "scores.md", scores.to_markdown())
    store.update_manifest(
        status="COMPLETED" if failures == 0 else "COMPLETED_WITH_ERRORS",
        completed_at=utc_now(),
        case_count=len(truths),
        failure_count=failures,
        scores={"rcia": scores.rcia, "root_cause_correct": scores.root_cause_correct},
    )
    return store.run_id, scores.model_dump(mode="json")


def run_live_baseline(settings: Settings) -> tuple[str, dict[str, object]]:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for a live baseline run")
    if not settings.openai_model:
        raise ValueError("OPENAI_MODEL is required for a live baseline run")
    client = OpenAIBaselineClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_retries=settings.openai_max_retries,
        reasoning_effort=settings.openai_reasoning_effort,
    )
    return run_baseline_batch(settings, client)
