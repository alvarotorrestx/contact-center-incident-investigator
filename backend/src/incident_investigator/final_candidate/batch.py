from __future__ import annotations

import hashlib
from importlib.metadata import version
from time import perf_counter
from typing import Any

from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.config import Settings
from incident_investigator.evaluation import (
    STAGE0_ANCHOR_RUN_ID,
    V1_RUN_ID,
    V2_RUN_ID,
    V3_RUN_ID,
    GroundTruthLoader,
    build_run_comparison,
    comparison_csv,
    comparison_markdown,
    score_benchmark,
)
from incident_investigator.hypotheses.models import LEDGER_VERSION
from incident_investigator.investigator.runner import _sum_usage
from incident_investigator.persistence import (
    GPT_5_6_SOL_PRICING,
    RunStore,
    estimate_gpt_5_6_sol_cost,
)
from incident_investigator.persistence.run_store import utc_now
from incident_investigator.structured_investigator import (
    OpenAIV2InvestigatorClient,
    StructuredHypothesisRunner,
    V2InvestigatorClient,
)
from incident_investigator.tools import TOOL_VERSION

from .prompting import build_final_candidate_prompt

SYSTEM_VERSION = "final_candidate"
INFORMATION_PRESENTATION = "all_visible_tables_initially; deterministic_tools_for_analysis"


def _write_comparison(
    store: RunStore,
    comparison: dict[str, Any],
    *,
    stem: str,
    anchor_label: str,
) -> None:
    store.write_json(store.result_root / f"{stem}.json", comparison)
    store.write_text(store.result_root / f"{stem}.csv", comparison_csv(comparison))
    store.write_text(
        store.result_root / f"{stem}.md",
        comparison_markdown(
            comparison,
            candidate_label="Final Candidate",
            anchor_label=anchor_label,
        ),
    )


def run_final_candidate_batch(
    settings: Settings,
    client: V2InvestigatorClient,
) -> tuple[str, dict[str, object], dict[str, object]]:
    loader = AgentVisibleCaseLoader(settings.cases_root)
    store = RunStore(settings.project_root)
    benchmark_manifest = (
        settings.project_root / "benchmark" / settings.benchmark_version / "manifest.json"
    )
    anchors = {
        "stage0": STAGE0_ANCHOR_RUN_ID,
        "v1": V1_RUN_ID,
        "v2": V2_RUN_ID,
        "v3": V3_RUN_ID,
    }
    store.create_manifest(
        {
            "system_version": SYSTEM_VERSION,
            "benchmark_version": settings.benchmark_version,
            "comparison_anchor_run_ids": anchors,
            "model": client.model,
            "model_configuration": {
                "sampling_parameters": "provider_defaults",
                "reasoning_effort": settings.openai_reasoning_effort,
            },
            "openai_sdk_version": version("openai"),
            "max_retries": settings.openai_max_retries,
            "prompt_version": "final_candidate_full_context_1",
            "tool_version": TOOL_VERSION,
            "hypothesis_ledger_version": LEDGER_VERSION,
            "maximum_tool_calls_per_case": settings.final_candidate_max_tool_calls,
            "minimum_distinct_supporting_tools_for_completion": 2,
            "minimum_tracked_hypotheses": 3,
            "information_presentation": INFORMATION_PRESENTATION,
            "verifier_enabled": False,
            "maximum_verifier_driven_revisions_per_case": 0,
            "pricing_basis": GPT_5_6_SOL_PRICING,
            "benchmark_manifest_sha256": hashlib.sha256(
                benchmark_manifest.read_bytes()
            ).hexdigest(),
        }
    )
    runner = StructuredHypothesisRunner(
        loader,
        client,
        store,
        max_tool_calls=settings.final_candidate_max_tool_calls,
        system_version=SYSTEM_VERSION,
        prompt_builder=build_final_candidate_prompt,
        information_presentation=INFORMATION_PRESENTATION,
    )
    predictions = {}
    failures = 0
    aggregate_usage: dict[str, Any] = {}
    aggregate_tool_calls = 0
    aggregate_hypothesis_updates = 0
    aggregate_premature_attempts = 0
    termination_reasons: dict[str, int] = {}
    batch_started = perf_counter()
    for summary in loader.list_incidents():
        try:
            result = runner.run_case(summary.incident_id)
            predictions[summary.incident_id] = result.diagnosis
            aggregate_usage = _sum_usage(aggregate_usage, result.total_usage)
            aggregate_tool_calls += result.tool_call_count
            aggregate_hypothesis_updates += result.hypothesis_update_count
            aggregate_premature_attempts += result.premature_completion_attempts
            termination_reasons[result.termination_reason] = (
                termination_reasons.get(result.termination_reason, 0) + 1
            )
        except Exception as exc:
            failures += 1
            predictions[summary.incident_id] = None
            store.write_error(summary.incident_id, exc)
            store.append_trajectory(
                summary.incident_id,
                {
                    "run_id": store.run_id,
                    "incident_id": summary.incident_id,
                    "system_version": SYSTEM_VERSION,
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
        average_tool_calls_per_case=aggregate_tool_calls / len(truths),
        aggregate_hypothesis_updates=aggregate_hypothesis_updates,
        aggregate_premature_completion_attempts=aggregate_premature_attempts,
        aggregate_verifier_calls=0,
        aggregate_revisions=0,
        termination_reasons=termination_reasons,
        aggregate_token_usage=aggregate_usage,
        estimated_cost_usd=estimate_gpt_5_6_sol_cost(aggregate_usage),
        scores={"rcia": scores.rcia, "root_cause_correct": scores.root_cause_correct},
    )

    comparisons: dict[str, Any] = {}
    for key, anchor_id, anchor_label in [
        ("stage0", STAGE0_ANCHOR_RUN_ID, "Pinned Stage 0 Anchor"),
        ("v1", V1_RUN_ID, "V1"),
        ("v2", V2_RUN_ID, "V2"),
        ("v3", V3_RUN_ID, "V3"),
    ]:
        comparison = build_run_comparison(settings.project_root, store.run_id, anchor_id)
        comparisons[key] = comparison
        _write_comparison(
            store,
            comparison,
            stem=f"comparison_to_{key}",
            anchor_label=anchor_label,
        )
    return store.run_id, scores.model_dump(mode="json"), comparisons


def run_live_final_candidate(
    settings: Settings,
) -> tuple[str, dict[str, object], dict[str, object]]:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for a live final-candidate run")
    if settings.openai_model != "gpt-5.6-sol":
        raise ValueError("Final-candidate comparison requires OPENAI_MODEL=gpt-5.6-sol")
    if settings.openai_reasoning_effort != "medium":
        raise ValueError("Final-candidate comparison requires reasoning_effort=medium")
    client = OpenAIV2InvestigatorClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_retries=settings.openai_max_retries,
        reasoning_effort=settings.openai_reasoning_effort,
    )
    return run_final_candidate_batch(settings, client)
