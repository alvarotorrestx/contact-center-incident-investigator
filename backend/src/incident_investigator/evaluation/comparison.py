from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from incident_investigator.persistence.pricing import estimate_gpt_5_6_sol_cost

STAGE0_ANCHOR_RUN_ID = "02b97b0d-d68e-45f8-b678-386f7558dd02"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def _run_root(project_root: Path, run_id: str, *, prefer_curated: bool) -> Path:
    UUID(run_id)
    candidates = (
        [project_root / "results" / "curated" / run_id, project_root / "results" / "local" / run_id]
        if prefer_curated
        else [project_root / "results" / "local" / run_id]
    )
    for candidate in candidates:
        if (candidate / "manifest.json").is_file():
            return candidate
    raise FileNotFoundError(f"Run artifacts not found: {run_id}")


def _trajectory_root(project_root: Path, run_id: str, *, prefer_curated: bool) -> Path:
    candidates = (
        [
            project_root / "trajectories" / "curated" / run_id,
            project_root / "trajectories" / "local" / run_id,
        ]
        if prefer_curated
        else [project_root / "trajectories" / "local" / run_id]
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"Trajectory artifacts not found: {run_id}")


def _sum_numeric(total: dict[str, Any], addition: dict[str, Any]) -> dict[str, Any]:
    merged = dict(total)
    for key, value in addition.items():
        if isinstance(value, dict):
            merged[key] = _sum_numeric(
                merged.get(key, {}) if isinstance(merged.get(key), dict) else {}, value
            )
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            merged[key] = merged.get(key, 0) + value
    return merged


def _trajectory_summary(root: Path) -> dict[str, Any]:
    usage: dict[str, Any] = {}
    case_duration_seconds = 0.0
    estimated_cost_values: list[float] = []
    for path in sorted(root.glob("CC-*.jsonl")):
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        final_events = [event for event in events if event.get("event_type") == "final_output"]
        if not final_events:
            continue
        final = final_events[-1]
        case_usage = final.get("total_token_usage") or final.get("token_usage") or {}
        if isinstance(case_usage, dict):
            usage = _sum_numeric(usage, case_usage)
        duration = final.get("total_duration_seconds", final.get("duration_seconds", 0))
        if isinstance(duration, (int, float)):
            case_duration_seconds += float(duration)
        cost = final.get("estimated_cost_usd")
        if isinstance(cost, (int, float)):
            estimated_cost_values.append(float(cost))
    return {
        "token_usage": usage,
        "summed_case_duration_seconds": round(case_duration_seconds, 6),
        "estimated_cost_usd": (
            round(sum(estimated_cost_values), 8)
            if estimated_cost_values
            else estimate_gpt_5_6_sol_cost(usage)
        ),
    }


def _wall_duration(manifest: dict[str, Any]) -> float | None:
    created = manifest.get("created_at")
    completed = manifest.get("completed_at")
    if not isinstance(created, str) or not isinstance(completed, str):
        return None
    return round(
        (datetime.fromisoformat(completed) - datetime.fromisoformat(created)).total_seconds(), 6
    )


def _prediction_categories(root: Path) -> dict[str, str]:
    categories = {}
    for path in sorted((root / "predictions").glob("CC-*.json")):
        prediction = _load_json(path)
        categories[path.stem] = str(prediction["primary_root_cause_category"])
    return categories


def build_run_comparison(
    project_root: Path,
    candidate_run_id: str,
    anchor_run_id: str = STAGE0_ANCHOR_RUN_ID,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    anchor_root = _run_root(project_root, anchor_run_id, prefer_curated=True)
    candidate_root = _run_root(project_root, candidate_run_id, prefer_curated=False)
    anchor_scores = _load_json(anchor_root / "scores.json")
    candidate_scores = _load_json(candidate_root / "scores.json")
    anchor_manifest = _load_json(anchor_root / "manifest.json")
    candidate_manifest = _load_json(candidate_root / "manifest.json")

    if anchor_manifest.get("benchmark_manifest_sha256") != candidate_manifest.get(
        "benchmark_manifest_sha256"
    ):
        raise ValueError("Anchor and candidate benchmark manifests do not match")
    if anchor_manifest.get("model") != candidate_manifest.get("model"):
        raise ValueError("Anchor and candidate models do not match")
    if anchor_manifest.get("model_configuration") != candidate_manifest.get("model_configuration"):
        raise ValueError("Anchor and candidate model configurations do not match")

    metric_names = [
        "rcia",
        "evidence_coverage",
        "non_allowlisted_evidence_rate",
        "contributing_exact_accuracy",
        "contributing_precision",
        "contributing_recall",
        "contributing_f1",
        "causal_reasoning_average",
    ]
    metrics = {
        name: {
            "anchor": anchor_scores[name],
            "candidate": candidate_scores[name],
            "delta": round(float(candidate_scores[name]) - float(anchor_scores[name]), 12),
        }
        for name in metric_names
    }
    anchor_cases = {item["incident_id"]: item for item in anchor_scores["per_case"]}
    candidate_cases = {item["incident_id"]: item for item in candidate_scores["per_case"]}
    improved: list[str] = []
    regressed: list[str] = []
    unchanged: list[str] = []
    for incident_id in sorted(anchor_cases):
        anchor_correct = bool(anchor_cases[incident_id]["root_cause_correct"])
        candidate_correct = bool(candidate_cases[incident_id]["root_cause_correct"])
        if candidate_correct and not anchor_correct:
            improved.append(incident_id)
        elif anchor_correct and not candidate_correct:
            regressed.append(incident_id)
        else:
            unchanged.append(incident_id)

    anchor_categories = _prediction_categories(anchor_root)
    candidate_categories = _prediction_categories(candidate_root)
    anchor_trajectory = _trajectory_summary(
        _trajectory_root(project_root, anchor_run_id, prefer_curated=True)
    )
    candidate_trajectory = _trajectory_summary(
        _trajectory_root(project_root, candidate_run_id, prefer_curated=False)
    )
    return {
        "anchor_run_id": anchor_run_id,
        "candidate_run_id": candidate_run_id,
        "benchmark_version": candidate_manifest["benchmark_version"],
        "benchmark_manifest_sha256": candidate_manifest["benchmark_manifest_sha256"],
        "model": candidate_manifest["model"],
        "model_configuration": candidate_manifest["model_configuration"],
        "metrics": metrics,
        "execution_failures": {
            "anchor": anchor_manifest.get("failure_count", 0),
            "candidate": candidate_manifest.get("failure_count", 0),
        },
        "runtime": {
            "anchor_wall_seconds": _wall_duration(anchor_manifest),
            "candidate_wall_seconds": _wall_duration(candidate_manifest),
            "anchor_summed_case_seconds": anchor_trajectory["summed_case_duration_seconds"],
            "candidate_summed_case_seconds": candidate_trajectory["summed_case_duration_seconds"],
        },
        "usage": {
            "anchor": anchor_trajectory["token_usage"],
            "candidate": candidate_trajectory["token_usage"],
        },
        "estimated_cost_usd": {
            "anchor": anchor_trajectory["estimated_cost_usd"],
            "candidate": candidate_trajectory["estimated_cost_usd"],
        },
        "cases_improved": improved,
        "cases_regressed": regressed,
        "cases_unchanged": unchanged,
        "cc005": {
            "anchor_category": anchor_categories.get("CC-005"),
            "candidate_category": candidate_categories.get("CC-005"),
            "anchor_correct": anchor_cases["CC-005"]["root_cause_correct"],
            "candidate_correct": candidate_cases["CC-005"]["root_cause_correct"],
        },
        "information_presentation": {
            "anchor": "all visible raw tables serialized in the initial prompt",
            "candidate": (
                "incident metadata in the initial prompt; the same visible tables accessed through "
                "deterministic read-only tools selected by the investigator"
            ),
        },
    }


def comparison_csv(comparison: dict[str, Any]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=["metric", "anchor", "candidate", "delta"],
        lineterminator="\n",
    )
    writer.writeheader()
    for metric, values in comparison["metrics"].items():
        writer.writerow({"metric": metric, **values})
    return buffer.getvalue()


def comparison_markdown(comparison: dict[str, Any]) -> str:
    lines = [
        "# V1 Comparison to Pinned Stage 0 Anchor",
        "",
        f"- Anchor run: `{comparison['anchor_run_id']}`",
        f"- Candidate run: `{comparison['candidate_run_id']}`",
        f"- Model: `{comparison['model']}`",
        f"- Model configuration: `{json.dumps(comparison['model_configuration'], sort_keys=True)}`",
        "",
        "| Metric | Anchor | V1 | Delta |",
        "|---|---:|---:|---:|",
    ]
    for metric, values in comparison["metrics"].items():
        lines.append(
            f"| {metric} | {values['anchor']:.6f} | {values['candidate']:.6f} | "
            f"{values['delta']:+.6f} |"
        )
    lines.extend(
        [
            "",
            f"- Cases improved: {', '.join(comparison['cases_improved']) or 'none'}",
            f"- Cases regressed: {', '.join(comparison['cases_regressed']) or 'none'}",
            f"- Cases unchanged: {', '.join(comparison['cases_unchanged']) or 'none'}",
            f"- Execution failures: {comparison['execution_failures']}",
            f"- Runtime: {comparison['runtime']}",
            f"- Token usage: {comparison['usage']}",
            f"- Estimated cost (when available): {comparison['estimated_cost_usd']}",
            "",
        ]
    )
    return "\n".join(lines)
