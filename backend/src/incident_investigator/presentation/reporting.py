from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.contracts import FinalDiagnosis, VisibleCase

DemoMode = Literal["default", "audit"]

DEMO_RUNS: dict[DemoMode, dict[str, Any]] = {
    "default": {
        "label": "Standard analysis",
        "description": "Fast, complete-context analysis for day-to-day incident triage.",
        "run_id": "02b97b0d-d68e-45f8-b678-386f7558dd02",
        "is_default": True,
    },
    "audit": {
        "label": "Deep investigation",
        "description": (
            "Deterministic drill-down with a structured hypothesis ledger and richer audit trail."
        ),
        "run_id": "d3859d8d-b252-426a-970e-89a471a5fe7c",
        "is_default": False,
    },
}


def _round(value: float, digits: int = 1) -> float:
    return round(float(value), digits)


def _weighted_average(rows: list[dict[str, Any]], value_key: str, weight_key: str) -> float | None:
    weighted_total = sum(float(row[value_key]) * float(row[weight_key]) for row in rows)
    weight_total = sum(float(row[weight_key]) for row in rows)
    return weighted_total / weight_total if weight_total else None


def _service_level(rows: list[dict[str, Any]]) -> float | None:
    numerator = sum(float(row["answered_within_threshold"]) for row in rows)
    denominator = sum(
        float(row["offered_calls"]) - float(row["short_abandoned_calls"]) for row in rows
    )
    return 100 * numerator / denominator if denominator else None


def _abandonment_rate(rows: list[dict[str, Any]]) -> float | None:
    abandoned = sum(float(row["abandoned_calls"]) for row in rows)
    offered = sum(float(row["offered_calls"]) for row in rows)
    return 100 * abandoned / offered if offered else None


def _delta(after: float | None, before: float | None) -> float | None:
    return None if after is None or before is None else after - before


def _impact_summary(case: VisibleCase) -> dict[str, Any]:
    incident_start = str(case.incident_metadata["incident_start"])
    before = [row for row in case.performance if str(row["timestamp"]) < incident_start]
    after = [row for row in case.performance if str(row["timestamp"]) >= incident_start]
    forecast_after = [row for row in case.forecast if str(row["timestamp"]) >= incident_start]
    staffing_before = [row for row in case.staffing if str(row["timestamp"]) < incident_start]
    staffing_after = [row for row in case.staffing if str(row["timestamp"]) >= incident_start]

    service_before = _service_level(before)
    service_after = _service_level(after)
    asa_before = _weighted_average(before, "asa_seconds", "answered_calls")
    asa_after = _weighted_average(after, "asa_seconds", "answered_calls")
    abandon_before = _abandonment_rate(before)
    abandon_after = _abandonment_rate(after)
    actual_volume = sum(float(row["offered_calls"]) for row in after)
    forecast_volume = sum(float(row["forecast_offered_calls"]) for row in forecast_after)
    forecast_variance = (
        100 * (actual_volume - forecast_volume) / forecast_volume if forecast_volume else None
    )
    productive_before = (
        sum(float(row["productive_agents"]) for row in staffing_before) / len(staffing_before)
        if staffing_before
        else None
    )
    productive_after = (
        sum(float(row["productive_agents"]) for row in staffing_after) / len(staffing_after)
        if staffing_after
        else None
    )
    occupancy_after = (
        sum(float(row["occupancy_pct"]) for row in staffing_after) / len(staffing_after)
        if staffing_after
        else None
    )

    queue_rows: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: {"before": [], "after": []}
    )
    for row in case.queue_performance:
        period = "before" if str(row["timestamp"]) < incident_start else "after"
        queue_rows[str(row["queue_name"])][period].append(row)

    queues: list[dict[str, Any]] = []
    for queue_name, periods in sorted(queue_rows.items()):
        pre_rows = periods["before"]
        post_rows = periods["after"]
        post_service = _weighted_average(post_rows, "service_level_pct", "offered_calls")
        pre_service = _weighted_average(pre_rows, "service_level_pct", "offered_calls")
        post_volume = sum(float(row["offered_calls"]) for row in post_rows)
        pre_average_volume = (
            sum(float(row["offered_calls"]) for row in pre_rows) / len(pre_rows)
            if pre_rows
            else None
        )
        post_average_volume = post_volume / len(post_rows) if post_rows else None
        volume_delta_pct = (
            100 * (post_average_volume - pre_average_volume) / pre_average_volume
            if post_average_volume is not None and pre_average_volume
            else None
        )
        queues.append(
            {
                "queue_name": queue_name,
                "service_level_pct": _round(post_service) if post_service is not None else None,
                "service_level_delta_pp": (
                    _round(_delta(post_service, pre_service))
                    if _delta(post_service, pre_service) is not None
                    else None
                ),
                "asa_seconds": (
                    _round(_weighted_average(post_rows, "asa_seconds", "answered_calls"))
                    if post_rows
                    else None
                ),
                "aht_seconds": (
                    _round(_weighted_average(post_rows, "aht_seconds", "answered_calls"))
                    if post_rows
                    else None
                ),
                "transfer_rate_pct": (
                    _round(_weighted_average(post_rows, "transfer_rate_pct", "answered_calls"))
                    if post_rows
                    else None
                ),
                "staffed_agents": (
                    _round(sum(float(row["staffed_agents"]) for row in post_rows) / len(post_rows))
                    if post_rows
                    else None
                ),
                "volume_delta_pct": _round(volume_delta_pct)
                if volume_delta_pct is not None
                else None,
            }
        )
    queues.sort(key=lambda queue: queue["service_level_pct"] or 1000)

    target = float(case.incident_metadata["service_level_target"])
    impacted = [
        queue["queue_name"]
        for queue in queues
        if queue["service_level_pct"] is not None and queue["service_level_pct"] < target
    ]
    if not impacted and queues:
        impacted = [queues[0]["queue_name"]]

    forecast_by_timestamp = {str(row["timestamp"]): row for row in case.forecast}
    staffing_by_timestamp = {str(row["timestamp"]): row for row in case.staffing}
    trend = []
    for row in case.performance:
        timestamp = str(row["timestamp"])
        forecast_row = forecast_by_timestamp.get(timestamp, {})
        staffing_row = staffing_by_timestamp.get(timestamp, {})
        offered = float(row["offered_calls"])
        trend.append(
            {
                "timestamp": timestamp,
                "service_level_pct": _round(float(row["service_level_pct"])),
                "asa_seconds": _round(float(row["asa_seconds"])),
                "abandonment_rate_pct": _round(
                    100 * float(row["abandoned_calls"]) / offered if offered else 0
                ),
                "offered_calls": int(offered),
                "forecast_offered_calls": int(float(forecast_row.get("forecast_offered_calls", 0))),
                "productive_agents": int(float(staffing_row.get("productive_agents", 0))),
                "is_incident_period": timestamp >= incident_start,
            }
        )

    return {
        "impacted_queues": impacted,
        "kpis": [
            {
                "id": "service_level",
                "label": "Service level",
                "value": _round(service_after) if service_after is not None else None,
                "unit": "%",
                "delta": _round(_delta(service_after, service_before))
                if _delta(service_after, service_before) is not None
                else None,
                "delta_unit": "pp",
                "context": f"Target {target:.0f}%",
                "tone": "negative"
                if service_after is not None and service_after < target
                else "positive",
            },
            {
                "id": "asa",
                "label": "Average speed of answer",
                "value": _round(asa_after) if asa_after is not None else None,
                "unit": "s",
                "delta": _round(_delta(asa_after, asa_before))
                if _delta(asa_after, asa_before) is not None
                else None,
                "delta_unit": "s",
                "context": "Weighted by answered calls",
                "tone": "negative"
                if _delta(asa_after, asa_before) and _delta(asa_after, asa_before) > 0
                else "positive",
            },
            {
                "id": "abandonment",
                "label": "Abandonment",
                "value": _round(abandon_after) if abandon_after is not None else None,
                "unit": "%",
                "delta": _round(_delta(abandon_after, abandon_before))
                if _delta(abandon_after, abandon_before) is not None
                else None,
                "delta_unit": "pp",
                "context": "All offered calls",
                "tone": "negative"
                if _delta(abandon_after, abandon_before)
                and _delta(abandon_after, abandon_before) > 0
                else "positive",
            },
            {
                "id": "forecast_variance",
                "label": "Volume vs forecast",
                "value": _round(forecast_variance) if forecast_variance is not None else None,
                "unit": "%",
                "delta": None,
                "delta_unit": None,
                "context": f"{int(actual_volume):,} actual / {int(forecast_volume):,} forecast",
                "tone": "negative" if forecast_variance and forecast_variance > 10 else "neutral",
            },
        ],
        "queues": queues,
        "trend": trend,
        "staffing_context": {
            "productive_agents": _round(productive_after) if productive_after is not None else None,
            "productive_agent_delta": _round(_delta(productive_after, productive_before))
            if _delta(productive_after, productive_before) is not None
            else None,
            "occupancy_pct": _round(occupancy_after) if occupancy_after is not None else None,
        },
        "forecast_context": {
            "actual_calls": int(actual_volume),
            "forecast_calls": int(forecast_volume),
            "variance_pct": _round(forecast_variance) if forecast_variance is not None else None,
        },
        "events": case.events,
    }


TOOL_SUMMARIES = {
    "summarize_incident_window": "Compared pre-incident and incident-window performance.",
    "get_performance_trends": "Reviewed interval-level movement across core performance metrics.",
    "compare_actual_vs_forecast": "Measured actual demand and handle time against forecast.",
    "analyze_staffing": "Checked staffing, adherence, occupancy, and training capacity.",
    "compare_queues": "Compared queue-level demand, waits, transfers, handle time, and staffing.",
    "analyze_queue": "Inspected one queue's performance and operating context.",
    "get_events": "Reviewed visible operational events and their timing.",
    "calculate_metric_change": "Calculated a deterministic pre/post metric change.",
    "recalculate_service_level": "Recalculated service level from visible call counts.",
}


def _public_trajectory(
    path: Path, mode: DemoMode
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    timeline: list[dict[str, Any]] = []
    hypotheses: list[dict[str, Any]] = []

    for event in events:
        event_type = event.get("event_type")
        item: dict[str, Any] | None = None
        if event_type in {"model_request", "investigation_started"}:
            item = {
                "type": "started",
                "title": "Investigation started",
                "summary": (
                    "Complete visible incident context was sent to the structured analyst."
                    if mode == "default"
                    else (
                        "A bounded deep investigation opened with deterministic tools "
                        "and a hypothesis ledger."
                    )
                ),
            }
        elif event_type == "model_decision":
            requested = event.get("requested_tools", [])
            tools = [
                str(request.get("name", "")) if isinstance(request, dict) else str(request)
                for request in requested
            ]
            tools = [tool for tool in tools if tool]
            item = {
                "type": "decision",
                "title": "Selected next analysis",
                "summary": str(
                    event.get("decision_summary", "Selected a deterministic analysis step.")
                ),
                "tools": tools,
            }
        elif event_type == "tool_result":
            tool = str(event.get("tool_called", "analysis tool"))
            item = {
                "type": "tool",
                "title": tool.replace("_", " ").title(),
                "summary": TOOL_SUMMARIES.get(
                    tool, "Completed a deterministic visible-data analysis."
                ),
                "tool": tool,
                "arguments": event.get("tool_arguments") or {},
            }
        elif event_type == "hypothesis_update":
            changes = [
                {
                    "category": change.get("category"),
                    "status": change.get("new_status"),
                    "confidence": change.get("new_confidence"),
                }
                for change in event.get("hypothesis_changes", [])
            ]
            item = {
                "type": "hypothesis",
                "title": "Hypotheses updated",
                "summary": str(
                    event.get("decision_summary", "Updated the structured hypothesis ledger.")
                ),
                "changes": changes,
            }
        elif event_type == "hypothesis_update_rejected":
            item = {
                "type": "guardrail",
                "title": "Ledger guardrail applied",
                "summary": (
                    "A malformed ledger update was rejected; the prior valid state was preserved."
                ),
            }
        elif event_type == "premature_completion_blocked":
            item = {
                "type": "guardrail",
                "title": "Completion held",
                "summary": (
                    "The investigation continued because the evidence threshold "
                    "was not yet satisfied."
                ),
            }
        elif event_type == "final_output":
            output = event.get("final_diagnosis") or event.get("final_output") or {}
            category = (
                str(output.get("primary_root_cause_category", "Diagnosis"))
                .replace("_", " ")
                .title()
            )
            confidence = round(float(output.get("confidence", 0)) * 100)
            item = {
                "type": "complete",
                "title": "Diagnosis finalized",
                "summary": f"{category} was returned with {confidence}% confidence.",
                "termination_reason": event.get(
                    "termination_reason", "structured_output_completed"
                ),
            }
            state = event.get("final_hypothesis_state") or {}
            for hypothesis in state.get("hypotheses", []):
                hypotheses.append(
                    {
                        "category": hypothesis.get("category"),
                        "status": hypothesis.get("status"),
                        "confidence": hypothesis.get("confidence"),
                        "evidence_for": [
                            {
                                "signal": evidence.get("signal"),
                                "finding": evidence.get("finding"),
                            }
                            for evidence in hypothesis.get("evidence_for", [])[:3]
                        ],
                        "evidence_against": [
                            {
                                "signal": evidence.get("signal"),
                                "finding": evidence.get("finding"),
                            }
                            for evidence in hypothesis.get("evidence_against", [])[:3]
                        ],
                    }
                )
        if item is not None:
            item["step"] = len(timeline) + 1
            item["timestamp"] = event.get("timestamp")
            timeline.append(item)

    return timeline, hypotheses


class DemoReportService:
    """Builds an evaluator-isolated presentation view from visible cases and curated outputs."""

    def __init__(self, project_root: Path, loader: AgentVisibleCaseLoader):
        self.project_root = project_root.resolve()
        self.loader = loader

    def build(self, incident_id: str, mode: DemoMode) -> dict[str, Any]:
        mode_details = DEMO_RUNS[mode]
        run_id = str(mode_details["run_id"])
        prediction_path = (
            self.project_root
            / "results"
            / "curated"
            / run_id
            / "predictions"
            / f"{incident_id}.json"
        )
        trajectory_path = (
            self.project_root / "trajectories" / "curated" / run_id / f"{incident_id}.jsonl"
        )
        if not prediction_path.is_file() or not trajectory_path.is_file():
            raise FileNotFoundError(f"Curated {mode} report is unavailable for {incident_id}")

        case = self.loader.load(incident_id)
        diagnosis = FinalDiagnosis.model_validate_json(prediction_path.read_text(encoding="utf-8"))
        timeline, hypotheses = _public_trajectory(trajectory_path, mode)
        return {
            "mode": {"id": mode, **mode_details},
            "incident": case.incident_metadata,
            "impact": _impact_summary(case),
            "diagnosis": diagnosis.model_dump(mode="json"),
            "trajectory": timeline,
            "hypotheses": hypotheses,
        }
