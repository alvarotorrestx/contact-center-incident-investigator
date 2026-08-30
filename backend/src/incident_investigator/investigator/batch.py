from __future__ import annotations

import hashlib
from importlib.metadata import version
from time import perf_counter
from typing import Any

from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.config import Settings
from incident_investigator.evaluation import (
    STAGE0_ANCHOR_RUN_ID,
    GroundTruthLoader,
    build_run_comparison,
    comparison_csv,
    comparison_markdown,
    score_benchmark,
)
from incident_investigator.persistence import (
    GPT_5_6_SOL_PRICING,
    RunStore,
    estimate_gpt_5_6_sol_cost,
)
from incident_investigator.persistence.run_store import utc_now
from incident_investigator.tools import TOOL_VERSION

from .client import InvestigatorClient, OpenAIInvestigatorClient
from .runner import ToolInvestigatorRunner, _sum_usage


def run_v1_batch(
    settings: Settings,
    client: InvestigatorClient,
) -> tuple[str, dict[str, object], dict[str, object]]:
    loader = AgentVisibleCaseLoader(settings.cases_root)
    store = RunStore(settings.project_root)
    benchmark_manifest = (
        settings.project_root / "benchmark" / settings.benchmark_version / "manifest.json"
    )
    store.create_manifest(
        {
            "system_version": "v1_tool_investigator",
            "benchmark_version": settings.benchmark_version,
            "comparison_anchor_run_id": STAGE0_ANCHOR_RUN_ID,
            "model": client.model,
            "model_configuration": {
                "sampling_parameters": "provider_defaults",
                "reasoning_effort": settings.openai_reasoning_effort,
            },
            "openai_sdk_version": version("openai"),
            "max_retries": settings.openai_max_retries,
            "prompt_version": "v1_tool_investigator_1",
            "tool_version": TOOL_VERSION,
            "maximum_tool_calls_per_case": settings.v1_max_tool_calls,
            "minimum_tool_calls_per_case": 1,
            "information_presentation": "metadata_initially; visible_tables_via_tools",
            "pricing_basis": GPT_5_6_SOL_PRICING,
            "benchmark_manifest_sha256": hashlib.sha256(
                benchmark_manifest.read_bytes()
            ).hexdigest(),
        }
    )
    runner = ToolInvestigatorRunner(
        loader,
        client,
        store,
        max_tool_calls=settings.v1_max_tool_calls,
    )
    predictions = {}
    failures = 0
    aggregate_usage: dict[str, Any] = {}
    aggregate_tool_calls = 0
    batch_started = perf_counter()
    for summary in loader.list_incidents():
        try:
            result = runner.run_case(summary.incident_id)
            predictions[summary.incident_id] = result.diagnosis
            aggregate_usage = _sum_usage(aggregate_usage, result.total_usage)
            aggregate_tool_calls += result.tool_call_count
        except Exception as exc:
            failures += 1
            predictions[summary.incident_id] = None
            store.write_error(summary.incident_id, exc)
            store.append_trajectory(
                summary.incident_id,
                {
                    "run_id": store.run_id,
                    "incident_id": summary.incident_id,
                    "system_version": "v1_tool_investigator",
                    "agent_stage": "investigator",
                    "event_type": "error",
                    "step_number": store.next_trajectory_step(summary.incident_id),
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
        duration_seconds=perf_counter() - batch_started,
        case_count=len(truths),
        failure_count=failures,
        aggregate_tool_calls=aggregate_tool_calls,
        aggregate_token_usage=aggregate_usage,
        estimated_cost_usd=estimate_gpt_5_6_sol_cost(aggregate_usage),
        scores={"rcia": scores.rcia, "root_cause_correct": scores.root_cause_correct},
    )
    comparison = build_run_comparison(settings.project_root, store.run_id)
    store.write_json(store.result_root / "comparison_to_anchor.json", comparison)
    store.write_text(store.result_root / "comparison_to_anchor.csv", comparison_csv(comparison))
    store.write_text(store.result_root / "comparison_to_anchor.md", comparison_markdown(comparison))
    return store.run_id, scores.model_dump(mode="json"), comparison


def run_live_v1(
    settings: Settings,
) -> tuple[str, dict[str, object], dict[str, object]]:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for a live V1 run")
    if settings.openai_model != "gpt-5.6-sol":
        raise ValueError("V1 comparison requires OPENAI_MODEL=gpt-5.6-sol")
    if settings.openai_reasoning_effort != "medium":
        raise ValueError("V1 comparison requires reasoning_effort=medium")
    client = OpenAIInvestigatorClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_retries=settings.openai_max_retries,
        reasoning_effort=settings.openai_reasoning_effort,
    )
    return run_v1_batch(settings, client)
