from __future__ import annotations

import hashlib
import json
import math
import platform
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .definitions import BenchmarkDefinition, ScenarioDefinition, load_definition

GENERATOR_VERSION = "1.0.1"
QUEUE_PROFILES = {
    "General Service": {"offered": 32, "aht": 330, "agents": 19, "transfer": 5.0},
    "Billing": {"offered": 20, "aht": 370, "agents": 12, "transfer": 6.0},
    "Account Support": {"offered": 16, "aht": 410, "agents": 11, "transfer": 7.0},
    "Escalations": {"offered": 7, "aht": 520, "agents": 7, "transfer": 10.0},
}


def _json_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _csv_write(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format="%.4f", lineterminator="\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _event_rows(
    case: ScenarioDefinition, timestamps: list[datetime], onset: int
) -> list[dict[str, str]]:
    timestamp = timestamps[onset].isoformat()
    effect = case.effect
    if effect in {"routing_change", "adversarial_routing"}:
        return [
            {
                "timestamp": timestamp,
                "event_type": "routing_deployment",
                "scope": "all_queues",
                "description": "Routing configuration version 24.7 was deployed.",
            }
        ]
    if effect == "queue_imbalance":
        return [
            {
                "timestamp": timestamp,
                "event_type": "routing_configuration",
                "scope": "Billing",
                "description": "Billing queue skill mappings were updated.",
            }
        ]
    if effect == "platform_incident":
        return [
            {
                "timestamp": timestamp,
                "event_type": "voice_platform_degradation",
                "scope": "all_queues",
                "description": (
                    "Voice platform monitoring reported intermittent call-processing delays."
                ),
            }
        ]
    if effect == "staffing_shortfall":
        return [
            {
                "timestamp": timestamp,
                "event_type": "workforce_notice",
                "scope": "center",
                "description": "Multiple same-day absences were reported.",
            }
        ]
    return []


def _multipliers(effect: str, index: int, onset: int, queue_name: str) -> dict[str, float]:
    values = {
        "demand": 1.0,
        "logged": 1.0,
        "adherence": 1.0,
        "aht": 1.0,
        "transfer": 1.0,
        "capacity": 1.0,
        "queue_agents": 1.0,
        "queue_agent_shift": 0.0,
    }
    if index < onset:
        return values
    elapsed = index - onset
    if effect == "demand_spike":
        values["demand"] = 1.55
    elif effect == "staffing_shortfall":
        values["logged"] = max(0.68, 0.88 - elapsed * 0.04)
    elif effect == "handle_time_increase":
        values["aht"] = min(1.48, 1.25 + elapsed * 0.04)
    elif effect == "routing_change":
        values["transfer"] = 2.05
        values["aht"] = 1.36
    elif effect == "queue_imbalance":
        if queue_name == "Billing":
            values["queue_agents"] = 0.75
            values["demand"] = 1.05
        elif queue_name == "General Service":
            values["queue_agent_shift"] = 3.0
    elif effect == "adherence_drop":
        values["adherence"] = max(0.60, 0.78 - elapsed * 0.025)
    elif effect == "platform_incident":
        values["capacity"] = 0.52
    elif effect == "normal_variance" and elapsed in {1, 2}:
        values["demand"] = 1.22
    elif effect == "adversarial_routing":
        values["demand"] = 1.12
        values["transfer"] = 2.20
        values["aht"] = 1.40
    return values


def _generate_case(
    definition: BenchmarkDefinition,
    case: ScenarioDefinition,
    rng: np.random.Generator,
    case_root: Path,
    ground_truth_root: Path,
) -> None:
    start = datetime.fromisoformat(f"{case.date}T08:00:00")
    timestamps = [
        start + timedelta(minutes=definition.interval_minutes * i)
        for i in range(definition.interval_count)
    ]
    onset = 7 if case.effect == "normal_variance" else 5
    incident_start = timestamps[onset]

    queue_rows: list[dict[str, Any]] = []
    performance_rows: list[dict[str, Any]] = []
    staffing_rows: list[dict[str, Any]] = []
    forecast_rows: list[dict[str, Any]] = []

    for index, timestamp in enumerate(timestamps):
        diurnal = 1.0 + 0.07 * math.sin((index - 2) * math.pi / 10)
        interval_queues: list[dict[str, Any]] = []
        interval_counts: list[dict[str, int]] = []
        scheduled_total = 0
        logged_total = 0
        productive_total = 0
        forecast_offered_total = 0
        forecast_workload = 0.0

        for queue_name, profile in QUEUE_PROFILES.items():
            effect = _multipliers(case.effect, index, onset, queue_name)
            forecast_offered = max(1, round(profile["offered"] * diurnal))
            forecast_aht = float(profile["aht"] * (1 + rng.normal(0, 0.012)))
            actual_mean = forecast_offered * effect["demand"]
            offered = max(1, int(rng.poisson(actual_mean)))

            scheduled = int(profile["agents"])
            queue_staffed = max(
                1,
                round(
                    scheduled * effect["logged"] * effect["queue_agents"]
                    + effect["queue_agent_shift"]
                ),
            )
            adherence = float(
                np.clip(0.93 * effect["adherence"] + rng.normal(0, 0.012), 0.45, 0.99)
            )
            productive = max(1, round(queue_staffed * adherence))
            aht = float(profile["aht"] * effect["aht"] * (1 + rng.normal(0, 0.025)))
            transfer_rate = float(
                np.clip(profile["transfer"] * effect["transfer"] + rng.normal(0, 0.35), 0, 40)
            )

            capacity = productive * 900 / aht * 0.88 * effect["capacity"]
            capacity = max(1.0, capacity + rng.normal(0, 0.8))
            potential_answered = min(offered, max(0, int(math.floor(capacity))))
            abandoned = max(0, offered - potential_answered)
            short_abandoned = min(abandoned, max(0, round(abandoned * 0.16)))
            answered = potential_answered
            denominator = max(1, offered - short_abandoned)
            load = offered / max(capacity, 1)
            within_rate = float(np.clip(0.96 - max(0.0, load - 0.78) * 0.65, 0.08, 0.96))
            answered_within = min(answered, max(0, round(answered * within_rate)))
            service_level = answered_within / denominator * 100
            asa = float(np.clip(11 + max(0.0, load - 0.68) * 105 + rng.normal(0, 2.0), 5, 240))

            interval_queues.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "queue_name": queue_name,
                    "offered_calls": offered,
                    "answered_calls": answered,
                    "service_level_pct": service_level,
                    "asa_seconds": asa,
                    "aht_seconds": aht,
                    "transfer_rate_pct": transfer_rate,
                    "staffed_agents": queue_staffed,
                }
            )
            interval_counts.append(
                {
                    "offered": offered,
                    "answered": answered,
                    "within": answered_within,
                    "abandoned": abandoned,
                    "short": short_abandoned,
                }
            )
            scheduled_total += scheduled
            logged_total += queue_staffed
            productive_total += productive
            forecast_offered_total += forecast_offered
            forecast_workload += forecast_offered * forecast_aht

        queue_rows.extend(interval_queues)
        offered_total = sum(row["offered"] for row in interval_counts)
        answered_total = sum(row["answered"] for row in interval_counts)
        within_total = sum(row["within"] for row in interval_counts)
        abandoned_total = sum(row["abandoned"] for row in interval_counts)
        short_total = sum(row["short"] for row in interval_counts)
        sl_denominator = max(1, offered_total - short_total)
        weighted_aht = sum(
            row["answered_calls"] * row["aht_seconds"] for row in interval_queues
        ) / max(1, answered_total)
        weighted_asa = sum(
            row["offered_calls"] * row["asa_seconds"] for row in interval_queues
        ) / max(1, offered_total)
        weighted_transfer = sum(
            row["answered_calls"] * row["transfer_rate_pct"] for row in interval_queues
        ) / max(1, answered_total)

        performance_rows.append(
            {
                "timestamp": timestamp.isoformat(),
                "offered_calls": offered_total,
                "answered_calls": answered_total,
                "answered_within_threshold": within_total,
                "abandoned_calls": abandoned_total,
                "short_abandoned_calls": short_total,
                "service_level_pct": within_total / sl_denominator * 100,
                "asa_seconds": weighted_asa,
                "aht_seconds": weighted_aht,
                "transfer_rate_pct": weighted_transfer,
            }
        )
        adherence_pct = productive_total / max(1, logged_total) * 100
        actual_workload = offered_total * weighted_aht
        occupancy_pct = float(
            np.clip(actual_workload / max(1, productive_total * 900) * 100, 45, 100)
        )
        staffing_rows.append(
            {
                "timestamp": timestamp.isoformat(),
                "scheduled_agents": scheduled_total,
                "logged_in_agents": logged_total,
                "productive_agents": productive_total,
                "adherence_pct": adherence_pct,
                "occupancy_pct": occupancy_pct,
                "agents_in_training": 0,
            }
        )
        forecast_rows.append(
            {
                "timestamp": timestamp.isoformat(),
                "forecast_offered_calls": forecast_offered_total,
                "forecast_aht_seconds": forecast_workload / max(1, forecast_offered_total),
                "required_agents": math.ceil(forecast_workload / (900 * 0.85)),
            }
        )

    if case.effect == "data_quality":
        for index in range(onset, definition.interval_count):
            performance_rows[index]["service_level_pct"] = max(
                0.0, float(performance_rows[index]["service_level_pct"]) - 26.0
            )
            performance_rows[index]["answered_calls"] = (
                int(performance_rows[index]["answered_calls"]) + 3
            )

    alert = (
        "Dashboard service level is below target; validate the reported metric."
        if case.effect == "data_quality"
        else "Service level fell below the 80% target during the evaluation window."
    )
    metadata = {
        "incident_id": case.incident_id,
        "date": case.date,
        "window_start": timestamps[0].isoformat(),
        "window_end": timestamps[-1].isoformat(),
        "incident_start": incident_start.isoformat(),
        "alert": alert,
        "service_level_target": 80.0,
        "service_level_seconds": 30,
    }

    _json_write(case_root / "incident_metadata.json", metadata)
    _json_write(case_root / "events.json", _event_rows(case, timestamps, onset))
    _csv_write(case_root / "performance.csv", pd.DataFrame(performance_rows))
    _csv_write(case_root / "staffing.csv", pd.DataFrame(staffing_rows))
    _csv_write(case_root / "forecast.csv", pd.DataFrame(forecast_rows))
    _csv_write(case_root / "queue_performance.csv", pd.DataFrame(queue_rows))

    ground_truth = {
        "incident_id": case.incident_id,
        "primary_root_cause": {
            "category": case.primary_root_cause.value,
            "detail": case.primary_detail,
        },
        "contributing_factors": [item.value for item in case.contributing_factors],
        "expected_evidence": [item.value for item in case.expected_evidence],
        "supported_signal_ids": [item.value for item in case.supported_signals],
        "expected_causal_chain": [item.value for item in case.expected_causal_chain],
        "intentional_exceptions": (
            ["service_level_recalculation_mismatch", "count_conservation_mismatch"]
            if case.effect == "data_quality"
            else []
        ),
    }
    _json_write(ground_truth_root / f"{case.incident_id}.json", ground_truth)


def generate_benchmark(project_root: Path, output_root: Path | None = None) -> dict[str, Any]:
    project_root = project_root.resolve()
    definition_path = project_root / "benchmark" / "definitions" / "v1.json"
    definition = load_definition(definition_path)
    target_root = (
        output_root or project_root / "benchmark" / definition.benchmark_version
    ).resolve()
    if output_root is None:
        staging_root = project_root / "benchmark" / ".staging" / definition.benchmark_version
    else:
        staging_root = target_root

    if staging_root.exists():
        shutil.rmtree(staging_root)
    (staging_root / "cases").mkdir(parents=True)
    (staging_root / "ground_truth").mkdir(parents=True)

    seed_sequence = np.random.SeedSequence(definition.seed)
    child_seeds = seed_sequence.spawn(len(definition.cases))
    for case, child_seed in zip(definition.cases, child_seeds, strict=True):
        rng = np.random.default_rng(child_seed)
        _generate_case(
            definition,
            case,
            rng,
            staging_root / "cases" / case.incident_id,
            staging_root / "ground_truth",
        )

    file_hashes = {
        path.relative_to(staging_root).as_posix(): _sha256(path)
        for path in sorted(staging_root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }
    manifest = {
        "benchmark_version": definition.benchmark_version,
        "generator_version": GENERATOR_VERSION,
        "seed": definition.seed,
        "rng": "numpy.random.PCG64 via SeedSequence children",
        "interval_minutes": definition.interval_minutes,
        "interval_count": definition.interval_count,
        "case_ids": [case.incident_id for case in definition.cases],
        "file_hashes": file_hashes,
        "generation_runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
    }
    _json_write(staging_root / "manifest.json", manifest)

    if output_root is None:
        if target_root.exists():
            shutil.rmtree(target_root)
        target_root.parent.mkdir(parents=True, exist_ok=True)
        staging_root.replace(target_root)
    return manifest
