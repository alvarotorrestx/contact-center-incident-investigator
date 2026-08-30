from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .definitions import BenchmarkDefinition, ScenarioDefinition, load_definition
from .loader import AgentVisibleCaseLoader


class BenchmarkValidationError(ValueError):
    pass


EXPECTED_COLUMNS = {
    "performance.csv": [
        "timestamp",
        "offered_calls",
        "answered_calls",
        "answered_within_threshold",
        "abandoned_calls",
        "short_abandoned_calls",
        "service_level_pct",
        "asa_seconds",
        "aht_seconds",
        "transfer_rate_pct",
    ],
    "staffing.csv": [
        "timestamp",
        "scheduled_agents",
        "logged_in_agents",
        "productive_agents",
        "adherence_pct",
        "occupancy_pct",
        "agents_in_training",
    ],
    "forecast.csv": [
        "timestamp",
        "forecast_offered_calls",
        "forecast_aht_seconds",
        "required_agents",
    ],
    "queue_performance.csv": [
        "timestamp",
        "queue_name",
        "offered_calls",
        "answered_calls",
        "service_level_pct",
        "asa_seconds",
        "aht_seconds",
        "transfer_rate_pct",
        "staffed_agents",
    ],
}


def _ratio(frame: pd.DataFrame, metric: str, incident_start: str) -> float:
    before = frame.loc[frame["timestamp"] < incident_start, metric].mean()
    after = frame.loc[frame["timestamp"] >= incident_start, metric].mean()
    return float(after / before) if before else 0.0


def _validate_scenario(case_root: Path, case: ScenarioDefinition) -> list[str]:
    errors: list[str] = []
    metadata = json.loads((case_root / "incident_metadata.json").read_text(encoding="utf-8"))
    performance = pd.read_csv(case_root / "performance.csv")
    staffing = pd.read_csv(case_root / "staffing.csv")
    queues = pd.read_csv(case_root / "queue_performance.csv")
    events = json.loads((case_root / "events.json").read_text(encoding="utf-8"))
    incident_start = metadata["incident_start"]

    checks: dict[str, bool] = {
        "demand_spike": _ratio(performance, "offered_calls", incident_start) > 1.30,
        "staffing_shortfall": _ratio(staffing, "logged_in_agents", incident_start) < 0.82,
        "handle_time_increase": _ratio(performance, "aht_seconds", incident_start) > 1.22,
        "routing_change": (
            _ratio(performance, "transfer_rate_pct", incident_start) > 1.55
            and any(event["event_type"] == "routing_deployment" for event in events)
        ),
        "queue_imbalance": (
            queues.loc[queues["timestamp"] >= incident_start]
            .groupby("queue_name")["service_level_pct"]
            .mean()
            .agg(lambda values: values.max() - values.min())
            > 20
        ),
        "adherence_drop": _ratio(staffing, "adherence_pct", incident_start) < 0.82,
        "platform_incident": any(
            event["event_type"] == "voice_platform_degradation" for event in events
        ),
        "data_quality": bool(
            (
                performance["service_level_pct"]
                - performance["answered_within_threshold"]
                / (performance["offered_calls"] - performance["short_abandoned_calls"])
                * 100
            )
            .abs()
            .gt(0.05)
            .any()
        ),
        "normal_variance": len(events) == 0
        and _ratio(performance, "offered_calls", incident_start) < 1.12,
        "adversarial_routing": (
            _ratio(performance, "transfer_rate_pct", incident_start) > 1.65
            and 1.04 < _ratio(performance, "offered_calls", incident_start) < 1.30
        ),
    }
    if not checks.get(case.effect, False):
        errors.append(f"{case.incident_id}: scenario signature failed for {case.effect}")
    return errors


def validate_benchmark(project_root: Path, benchmark_root: Path | None = None) -> list[str]:
    project_root = project_root.resolve()
    definition: BenchmarkDefinition = load_definition(
        project_root / "benchmark" / "definitions" / "v1.json"
    )
    root = (benchmark_root or project_root / "benchmark" / definition.benchmark_version).resolve()
    errors: list[str] = []
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("case_ids") != [case.incident_id for case in definition.cases]:
        errors.append("Manifest case catalog does not match the v1 definition")
    manifest_hashes = manifest.get("file_hashes", {})
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual_paths != set(manifest_hashes):
        errors.append("Frozen benchmark file catalog does not match its manifest")
    for relative_path, expected_hash in manifest_hashes.items():
        path = (root / relative_path).resolve()
        if root not in path.parents or not path.is_file():
            errors.append(f"Manifest path is missing or escapes benchmark root: {relative_path}")
            continue
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            errors.append(f"Manifest checksum mismatch: {relative_path}")
    loader = AgentVisibleCaseLoader(root / "cases")
    summaries = loader.list_incidents()
    if [item.incident_id for item in summaries] != [case.incident_id for case in definition.cases]:
        errors.append("Visible case catalog does not match the v1 definition")

    for case in definition.cases:
        case_root = root / "cases" / case.incident_id
        for filename, columns in EXPECTED_COLUMNS.items():
            frame = pd.read_csv(case_root / filename)
            if list(frame.columns) != columns:
                errors.append(f"{case.incident_id}/{filename}: unexpected columns")
            expected_rows = definition.interval_count * (
                4 if filename == "queue_performance.csv" else 1
            )
            if len(frame) != expected_rows:
                errors.append(f"{case.incident_id}/{filename}: expected {expected_rows} rows")

        performance = pd.read_csv(case_root / "performance.csv")
        queues = pd.read_csv(case_root / "queue_performance.csv")
        metadata = json.loads((case_root / "incident_metadata.json").read_text(encoding="utf-8"))
        pre_incident = performance.loc[
            performance["timestamp"] < metadata["incident_start"], "service_level_pct"
        ]
        if pre_incident.mean() < metadata["service_level_target"]:
            errors.append(f"{case.incident_id}: pre-incident service level misses target")
        if case.effect == "queue_imbalance":
            post_incident = performance.loc[
                performance["timestamp"] >= metadata["incident_start"], "service_level_pct"
            ]
            if post_incident.mean() < metadata["service_level_target"] - 5:
                errors.append(
                    f"{case.incident_id}: center average no longer masks the queue failure"
                )
        aggregate = queues.groupby("timestamp", as_index=False)[
            ["offered_calls", "answered_calls"]
        ].sum()
        merged = performance.merge(aggregate, on="timestamp", suffixes=("_center", "_queues"))
        offered_mismatch = (merged["offered_calls_center"] != merged["offered_calls_queues"]).any()
        answered_mismatch = (
            merged["answered_calls_center"] != merged["answered_calls_queues"]
        ).any()
        if offered_mismatch:
            errors.append(f"{case.incident_id}: offered calls do not aggregate from queues")
        if answered_mismatch and case.effect != "data_quality":
            errors.append(f"{case.incident_id}: answered calls do not aggregate from queues")

        denominator = performance["offered_calls"] - performance["short_abandoned_calls"]
        recalculated = performance["answered_within_threshold"] / denominator * 100
        mismatch = (performance["service_level_pct"] - recalculated).abs().gt(0.05).any()
        if mismatch != (case.effect == "data_quality"):
            errors.append(f"{case.incident_id}: service-level consistency policy mismatch")

        errors.extend(_validate_scenario(case_root, case))

    if errors:
        raise BenchmarkValidationError("\n".join(errors))
    return [case.incident_id for case in definition.cases]
