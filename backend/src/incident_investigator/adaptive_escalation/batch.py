from __future__ import annotations

import hashlib
from collections import Counter
from importlib.metadata import version
from time import perf_counter
from typing import Any

from incident_investigator.baseline import BaselineClient, OpenAIBaselineClient
from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.config import Settings
from incident_investigator.evaluation import (
    FINAL_CANDIDATE_RUN_ID,
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
    V2InvestigatorClient,
)
from incident_investigator.tools import TOOL_VERSION

from .gate import GATE_VERSION
from .runner import (
    INFORMATION_PRESENTATION,
    SYSTEM_VERSION,
    AdaptiveEscalationRunner,
    AdaptiveRunResult,
)


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
            candidate_label="Adaptive Escalation",
            anchor_label=anchor_label,
        ),
    )


def _analysis_markdown(analysis: dict[str, Any]) -> str:
    trigger_lines = [
        f"- `{name}`: {count}" for name, count in analysis["trigger_counts"].items()
    ] or ["- none"]
    return "\n".join(
        [
            "# Adaptive Escalation Analysis",
            "",
            f"- Cases escalated: {analysis['cases_escalated']}",
            f"- Cases finalized directly: {analysis['cases_finalized_directly']}",
            "- Diagnoses changed after escalation: "
            f"{analysis['diagnoses_changed_after_escalation']}",
            "- Categories changed after escalation: "
            f"{analysis['categories_changed_after_escalation']}",
            f"- Incorrect first passes corrected: {analysis['incorrect_first_passes_corrected']}",
            f"- Correct first passes harmed: {analysis['correct_first_passes_harmed']}",
            f"- Escalated with unchanged category: {analysis['escalated_with_unchanged_category']}",
            "- Average tool calls among escalated cases: "
            f"{analysis['average_tool_calls_among_escalated']:.6f}",
            "",
            "## Trigger counts",
            "",
            *trigger_lines,
            "",
        ]
    )


def _build_analysis(
    results: dict[str, AdaptiveRunResult],
    truths: list[Any],
) -> dict[str, Any]:
    truth_categories = {truth.incident_id: truth.primary_root_cause.category for truth in truths}
    escalated = [item for item in results.values() if item.escalation.escalate]
    trigger_counts = Counter(trigger for item in escalated for trigger in item.escalation.triggers)
    corrected: list[str] = []
    harmed: list[str] = []
    unchanged_category: list[str] = []
    changed_diagnosis: list[str] = []
    changed_category: list[str] = []
    per_case: list[dict[str, Any]] = []
    for incident_id, item in sorted(results.items()):
        expected = truth_categories[incident_id]
        first_correct = item.first_pass_diagnosis.primary_root_cause_category == expected
        final_correct = item.diagnosis.primary_root_cause_category == expected
        if item.escalation.escalate and not first_correct and final_correct:
            corrected.append(incident_id)
        if item.escalation.escalate and first_correct and not final_correct:
            harmed.append(incident_id)
        if item.escalation.escalate and not item.category_changed:
            unchanged_category.append(incident_id)
        if item.escalation.escalate and item.diagnosis_changed:
            changed_diagnosis.append(incident_id)
        if item.escalation.escalate and item.category_changed:
            changed_category.append(incident_id)
        per_case.append(
            {
                "incident_id": incident_id,
                "escalated": item.escalation.escalate,
                "triggers": list(item.escalation.triggers),
                "first_pass_category": (
                    item.first_pass_diagnosis.primary_root_cause_category.value
                ),
                "final_category": item.diagnosis.primary_root_cause_category.value,
                "first_pass_correct": first_correct,
                "final_correct": final_correct,
                "diagnosis_changed": item.diagnosis_changed,
                "category_changed": item.category_changed,
                "tool_call_count": item.tool_call_count,
                "termination_reason": item.termination_reason,
                "duration_seconds": item.duration_seconds,
                "token_usage": item.total_usage,
                "estimated_cost_usd": estimate_gpt_5_6_sol_cost(item.total_usage),
            }
        )
    return {
        "cases_escalated": len(escalated),
        "cases_finalized_directly": len(results) - len(escalated),
        "escalated_incident_ids": sorted(
            incident_id for incident_id, item in results.items() if item.escalation.escalate
        ),
        "direct_incident_ids": sorted(
            incident_id for incident_id, item in results.items() if not item.escalation.escalate
        ),
        "trigger_counts": dict(sorted(trigger_counts.items())),
        "diagnoses_changed_after_escalation": sorted(changed_diagnosis),
        "categories_changed_after_escalation": sorted(changed_category),
        "incorrect_first_passes_corrected": sorted(corrected),
        "correct_first_passes_harmed": sorted(harmed),
        "escalated_with_unchanged_category": sorted(unchanged_category),
        "average_tool_calls_among_escalated": (
            sum(item.tool_call_count for item in escalated) / len(escalated) if escalated else 0.0
        ),
        "per_case": per_case,
    }


def run_adaptive_batch(
    settings: Settings,
    first_pass_client: BaselineClient,
    deep_client: V2InvestigatorClient,
) -> tuple[str, dict[str, object], dict[str, object], dict[str, object]]:
    if first_pass_client.model != deep_client.model:
        raise ValueError("Adaptive first-pass and deep clients must use the same model")
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
        "final_candidate": FINAL_CANDIDATE_RUN_ID,
    }
    store.create_manifest(
        {
            "system_version": SYSTEM_VERSION,
            "benchmark_version": settings.benchmark_version,
            "comparison_anchor_run_ids": anchors,
            "model": first_pass_client.model,
            "model_configuration": {
                "sampling_parameters": "provider_defaults",
                "reasoning_effort": settings.openai_reasoning_effort,
            },
            "openai_sdk_version": version("openai"),
            "max_retries": settings.openai_max_retries,
            "first_pass_prompt_version": "baseline_v1",
            "deep_investigation_prompt_version": ("adaptive_escalation_deep_investigation_1"),
            "escalation_gate_version": GATE_VERSION,
            "tool_version": TOOL_VERSION,
            "hypothesis_ledger_version": LEDGER_VERSION,
            "maximum_tool_calls_per_escalated_case": settings.adaptive_max_tool_calls,
            "information_presentation": INFORMATION_PRESENTATION,
            "verifier_enabled": False,
            "maximum_verifier_driven_revisions_per_case": 0,
            "pricing_basis": GPT_5_6_SOL_PRICING,
            "benchmark_manifest_sha256": hashlib.sha256(
                benchmark_manifest.read_bytes()
            ).hexdigest(),
        }
    )
    runner = AdaptiveEscalationRunner(
        loader,
        first_pass_client,
        deep_client,
        store,
        max_tool_calls=settings.adaptive_max_tool_calls,
    )
    predictions: dict[str, Any] = {}
    results: dict[str, AdaptiveRunResult] = {}
    failures = 0
    aggregate_usage: dict[str, Any] = {}
    batch_started = perf_counter()
    for summary in loader.list_incidents():
        try:
            result = runner.run_case(summary.incident_id)
            results[summary.incident_id] = result
            predictions[summary.incident_id] = result.diagnosis
            aggregate_usage = _sum_usage(aggregate_usage, result.total_usage)
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
                    "agent_stage": "adaptive_escalation",
                    "event_type": "error",
                    "step_number": store.next_trajectory_step(summary.incident_id),
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
            )

    truths = GroundTruthLoader(settings.ground_truth_root).load_all()
    scores = score_benchmark(predictions, truths)
    analysis = _build_analysis(results, truths)
    store.write_json(store.result_root / "scores.json", scores.model_dump(mode="json"))
    store.write_text(store.result_root / "comparison.csv", scores.to_csv())
    store.write_text(store.result_root / "scores.md", scores.to_markdown())
    store.write_json(store.result_root / "adaptive_analysis.json", analysis)
    store.write_text(store.result_root / "adaptive_analysis.md", _analysis_markdown(analysis))
    store.update_manifest(
        status="COMPLETED" if failures == 0 else "COMPLETED_WITH_ERRORS",
        completed_at=utc_now(),
        duration_seconds=perf_counter() - batch_started,
        case_count=len(truths),
        failure_count=failures,
        cases_escalated=analysis["cases_escalated"],
        cases_finalized_directly=analysis["cases_finalized_directly"],
        escalation_trigger_counts=analysis["trigger_counts"],
        aggregate_tool_calls=sum(item.tool_call_count for item in results.values()),
        average_tool_calls_among_escalated=analysis["average_tool_calls_among_escalated"],
        aggregate_hypothesis_updates=sum(item.hypothesis_update_count for item in results.values()),
        aggregate_premature_completion_attempts=sum(
            item.premature_completion_attempts for item in results.values()
        ),
        aggregate_verifier_calls=0,
        aggregate_revisions=0,
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
        (
            "final_candidate",
            FINAL_CANDIDATE_RUN_ID,
            "Complete-Context Agentic Candidate",
        ),
    ]:
        comparison = build_run_comparison(settings.project_root, store.run_id, anchor_id)
        comparisons[key] = comparison
        _write_comparison(
            store,
            comparison,
            stem=f"comparison_to_{key}",
            anchor_label=anchor_label,
        )
    return store.run_id, scores.model_dump(mode="json"), comparisons, analysis


def run_live_adaptive(
    settings: Settings,
) -> tuple[str, dict[str, object], dict[str, object], dict[str, object]]:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for a live adaptive run")
    if settings.openai_model != "gpt-5.6-sol":
        raise ValueError("Adaptive comparison requires OPENAI_MODEL=gpt-5.6-sol")
    if settings.openai_reasoning_effort != "medium":
        raise ValueError("Adaptive comparison requires reasoning_effort=medium")
    first_pass_client = OpenAIBaselineClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_retries=settings.openai_max_retries,
        reasoning_effort=settings.openai_reasoning_effort,
    )
    deep_client = OpenAIV2InvestigatorClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_retries=settings.openai_max_retries,
        reasoning_effort=settings.openai_reasoning_effort,
    )
    return run_adaptive_batch(settings, first_pass_client, deep_client)
