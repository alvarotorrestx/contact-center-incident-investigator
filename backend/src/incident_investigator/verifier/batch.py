from __future__ import annotations

import hashlib
import json
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Any

from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.config import Settings
from incident_investigator.evaluation import (
    STAGE0_ANCHOR_RUN_ID,
    V1_RUN_ID,
    V2_RUN_ID,
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
from incident_investigator.structured_investigator.runner import V2RunResult
from incident_investigator.tools import TOOL_VERSION

from .client import OpenAIVerifierClient, VerifierClient
from .models import VerificationStatus

SYSTEM_VERSION = "v3_adversarial_verification"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


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
            candidate_label="V3",
            anchor_label=anchor_label,
        ),
    )


def _verification_analysis(
    project_root: Path,
    run_results: dict[str, V2RunResult],
    truths: list[Any],
) -> dict[str, Any]:
    truth_by_case = {truth.incident_id: truth for truth in truths}
    v2_scores = _load_json(project_root / "results" / "curated" / V2_RUN_ID / "scores.json")
    v2_case_scores = {item["incident_id"]: item for item in v2_scores["per_case"]}
    finding_patterns: Counter[str] = Counter()
    per_case: list[dict[str, Any]] = []
    corrected_initial: list[str] = []
    harmed_initial: list[str] = []
    verified_correct_without_revision: list[str] = []
    verified_incorrect_without_revision: list[str] = []
    unchanged_after_revision: list[str] = []

    for incident_id in sorted(truth_by_case):
        result = run_results.get(incident_id)
        if result is None:
            per_case.append({"incident_id": incident_id, "execution_failure": True})
            continue
        truth = truth_by_case[incident_id]
        initial = result.proposed_diagnoses[0]
        final = result.diagnosis
        initial_correct = initial.primary_root_cause_category == truth.primary_root_cause.category
        final_correct = final.primary_root_cause_category == truth.primary_root_cause.category
        statuses = [item.verification_status.value for item in result.verification_results]
        for verification in result.verification_results:
            for finding in [
                *verification.critical_contradictions,
                *verification.unsupported_or_weak_claims,
            ]:
                finding_patterns[finding.check.value] += 1
        if result.revision_count and not initial_correct and final_correct:
            corrected_initial.append(incident_id)
        if result.revision_count and initial_correct and not final_correct:
            harmed_initial.append(incident_id)
        if not result.revision_count and statuses == [VerificationStatus.VERIFIED.value]:
            target = (
                verified_correct_without_revision
                if final_correct
                else verified_incorrect_without_revision
            )
            target.append(incident_id)
        if (
            result.revision_count
            and statuses[-1] == VerificationStatus.VERIFIED.value
            and initial.primary_root_cause_category == final.primary_root_cause_category
        ):
            unchanged_after_revision.append(incident_id)
        per_case.append(
            {
                "incident_id": incident_id,
                "execution_failure": False,
                "v2_category": _load_json(
                    project_root
                    / "results"
                    / "curated"
                    / V2_RUN_ID
                    / "predictions"
                    / f"{incident_id}.json"
                )["primary_root_cause_category"],
                "v2_correct": bool(v2_case_scores[incident_id]["root_cause_correct"]),
                "initial_v3_category": initial.primary_root_cause_category.value,
                "initial_v3_correct": initial_correct,
                "final_v3_category": final.primary_root_cause_category.value,
                "final_v3_correct": final_correct,
                "verification_statuses": statuses,
                "verification_rounds": [
                    item.model_dump(mode="json") for item in result.verification_results
                ],
                "verifier_calls": result.verifier_call_count,
                "revisions": result.revision_count,
                "diagnosis_category_changed": (
                    initial.primary_root_cause_category != final.primary_root_cause_category
                ),
                "tool_calls": result.tool_call_count,
                "termination_reason": result.termination_reason,
            }
        )
    return {
        "v2_run_id": V2_RUN_ID,
        "verifier_corrected_initial_proposal": corrected_initial,
        "verifier_harmed_initial_proposal": harmed_initial,
        "verified_correct_without_revision": verified_correct_without_revision,
        "verified_incorrect_without_revision": verified_incorrect_without_revision,
        "diagnosis_category_unchanged_after_successful_revision": unchanged_after_revision,
        "finding_patterns": dict(sorted(finding_patterns.items())),
        "per_case": per_case,
    }


def _analysis_markdown(analysis: dict[str, Any]) -> str:
    corrected = analysis["verifier_corrected_initial_proposal"]
    harmed = analysis["verifier_harmed_initial_proposal"]
    verified_correct = analysis["verified_correct_without_revision"]
    verified_incorrect = analysis["verified_incorrect_without_revision"]
    lines = [
        "# V3 Verification Analysis",
        "",
        f"- Verifier-corrected initial proposals: {corrected}",
        f"- Verifier-harmed initial proposals: {harmed}",
        f"- Correct diagnoses verified without revision: {verified_correct}",
        f"- Incorrect diagnoses verified without revision: {verified_incorrect}",
        (
            "- Category unchanged after a successful revision: "
            f"{analysis['diagnosis_category_unchanged_after_successful_revision']}"
        ),
        f"- Finding patterns: {analysis['finding_patterns']}",
        "",
        "| Case | V2 | Initial V3 | Final V3 | Verifications | Revisions | Tools |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for item in analysis["per_case"]:
        if item.get("execution_failure"):
            lines.append(f"| {item['incident_id']} | - | ERROR | ERROR | 0 | 0 | 0 |")
            continue
        lines.append(
            f"| {item['incident_id']} | {item['v2_category']} | "
            f"{item['initial_v3_category']} | {item['final_v3_category']} | "
            f"{item['verifier_calls']} | {item['revisions']} | {item['tool_calls']} |"
        )
    lines.append("")
    return "\n".join(lines)


def run_v3_batch(
    settings: Settings,
    investigator_client: V2InvestigatorClient,
    verifier_client: VerifierClient,
) -> tuple[str, dict[str, object], dict[str, object], dict[str, object]]:
    loader = AgentVisibleCaseLoader(settings.cases_root)
    store = RunStore(settings.project_root)
    benchmark_manifest = (
        settings.project_root / "benchmark" / settings.benchmark_version / "manifest.json"
    )
    store.create_manifest(
        {
            "system_version": SYSTEM_VERSION,
            "benchmark_version": settings.benchmark_version,
            "comparison_anchor_run_ids": {
                "stage0": STAGE0_ANCHOR_RUN_ID,
                "v1": V1_RUN_ID,
                "v2": V2_RUN_ID,
            },
            "model": investigator_client.model,
            "model_configuration": {
                "sampling_parameters": "provider_defaults",
                "reasoning_effort": settings.openai_reasoning_effort,
            },
            "openai_sdk_version": version("openai"),
            "max_retries": settings.openai_max_retries,
            "investigator_prompt_version": "v2_hypothesis_investigator_1",
            "verifier_prompt_version": "v3_adversarial_verifier_2",
            "tool_version": TOOL_VERSION,
            "hypothesis_ledger_version": LEDGER_VERSION,
            "maximum_tool_calls_per_case": settings.v3_max_tool_calls,
            "maximum_verifier_driven_revisions_per_case": settings.v3_max_revisions,
            "maximum_verifier_calls_per_case": settings.v3_max_revisions + 1,
            "information_presentation": (
                "metadata initially; visible tables via tools; verifier receives accumulated "
                "visible evidence"
            ),
            "pricing_basis": GPT_5_6_SOL_PRICING,
            "benchmark_manifest_sha256": hashlib.sha256(
                benchmark_manifest.read_bytes()
            ).hexdigest(),
        }
    )
    runner = StructuredHypothesisRunner(
        loader,
        investigator_client,
        store,
        max_tool_calls=settings.v3_max_tool_calls,
        verifier_client=verifier_client,
        max_revisions=settings.v3_max_revisions,
        system_version=SYSTEM_VERSION,
    )
    predictions = {}
    run_results: dict[str, V2RunResult] = {}
    failures = 0
    aggregate_usage: dict[str, Any] = {}
    aggregate_tool_calls = 0
    aggregate_verifier_calls = 0
    aggregate_revisions = 0
    aggregate_hypothesis_updates = 0
    batch_started = perf_counter()
    for summary in loader.list_incidents():
        try:
            result = runner.run_case(summary.incident_id)
            predictions[summary.incident_id] = result.diagnosis
            run_results[summary.incident_id] = result
            aggregate_usage = _sum_usage(aggregate_usage, result.total_usage)
            aggregate_tool_calls += result.tool_call_count
            aggregate_verifier_calls += result.verifier_call_count
            aggregate_revisions += result.revision_count
            aggregate_hypothesis_updates += result.hypothesis_update_count
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
                    "agent_stage": "orchestrator",
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
        aggregate_verifier_calls=aggregate_verifier_calls,
        average_verifier_calls_per_case=aggregate_verifier_calls / len(truths),
        aggregate_revisions=aggregate_revisions,
        average_revisions_per_case=aggregate_revisions / len(truths),
        aggregate_token_usage=aggregate_usage,
        estimated_cost_usd=estimate_gpt_5_6_sol_cost(aggregate_usage),
        scores={"rcia": scores.rcia, "root_cause_correct": scores.root_cause_correct},
    )

    comparisons: dict[str, Any] = {}
    for key, anchor_id, label in [
        ("stage0", STAGE0_ANCHOR_RUN_ID, "Pinned Stage 0 Anchor"),
        ("v1", V1_RUN_ID, "V1"),
        ("v2", V2_RUN_ID, "V2"),
    ]:
        comparison = build_run_comparison(settings.project_root, store.run_id, anchor_id)
        comparisons[key] = comparison
        _write_comparison(
            store,
            comparison,
            stem=f"comparison_to_{key}",
            anchor_label=label,
        )
    analysis = _verification_analysis(settings.project_root, run_results, truths)
    store.write_json(store.result_root / "verification_analysis.json", analysis)
    store.write_text(store.result_root / "verification_analysis.md", _analysis_markdown(analysis))
    return store.run_id, scores.model_dump(mode="json"), comparisons, analysis


def run_live_v3(
    settings: Settings,
) -> tuple[str, dict[str, object], dict[str, object], dict[str, object]]:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for a live V3 run")
    if settings.openai_model != "gpt-5.6-sol":
        raise ValueError("V3 comparison requires OPENAI_MODEL=gpt-5.6-sol")
    if settings.openai_reasoning_effort != "medium":
        raise ValueError("V3 comparison requires reasoning_effort=medium")
    investigator = OpenAIV2InvestigatorClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_retries=settings.openai_max_retries,
        reasoning_effort=settings.openai_reasoning_effort,
    )
    verifier = OpenAIVerifierClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        max_retries=settings.openai_max_retries,
        reasoning_effort=settings.openai_reasoning_effort,
    )
    return run_v3_batch(settings, investigator, verifier)
