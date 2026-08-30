from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.tools import CaseToolbox


def _toolbox(project_root: Path, incident_id: str = "CC-005") -> CaseToolbox:
    case = AgentVisibleCaseLoader(project_root / "benchmark" / "v1" / "cases").load(incident_id)
    return CaseToolbox(case)


def test_tools_are_deterministic_and_queue_comparison_is_localized(project_root: Path) -> None:
    toolbox = _toolbox(project_root)

    first = toolbox.execute("compare_queues", {})
    second = toolbox.execute("compare_queues", {})

    assert first == second
    queues = first["queues_ranked_by_post_incident_service_level_ascending"]
    assert queues[0]["queue_name"] == "Billing"
    assert queues[0]["metrics"]["staffed_agents"]["absolute_change"] == -3
    general = next(item for item in queues if item["queue_name"] == "General Service")
    assert general["metrics"]["staffed_agents"]["absolute_change"] == 3


def test_staffing_and_forecast_calculations(project_root: Path) -> None:
    toolbox = _toolbox(project_root)

    staffing = toolbox.execute("analyze_staffing", {})
    forecast = toolbox.execute("compare_actual_vs_forecast", {})

    assert staffing["summary"]["scheduled_agents"]["absolute_change"] == 0
    assert staffing["summary"]["logged_in_agents"]["absolute_change"] == 0
    assert forecast["summary"]["offered_variance"]["pre_incident_mean"] == 1
    assert forecast["summary"]["offered_variance"]["incident_and_after_mean"] == 1.5455


def test_service_level_recalculation_detects_declared_data_quality_case(
    project_root: Path,
) -> None:
    consistent = _toolbox(project_root).execute("recalculate_service_level", {})
    inconsistent = _toolbox(project_root, "CC-012").execute("recalculate_service_level", {})

    assert consistent["mismatch_intervals_over_0_01_points"] == 0
    assert inconsistent["mismatch_intervals_over_0_01_points"] > 0


def test_tool_arguments_and_queue_names_are_strictly_validated(project_root: Path) -> None:
    toolbox = _toolbox(project_root)

    with pytest.raises(ValueError, match="Unknown queue"):
        toolbox.execute("analyze_queue", {"queue_name": "Not A Queue"})
    with pytest.raises(ValidationError):
        toolbox.execute("analyze_staffing", {"unexpected": True})
    with pytest.raises(ValidationError):
        toolbox.execute("calculate_metric_change", {"metric": "root_cause"})


def test_event_filters_are_visible_case_only(project_root: Path) -> None:
    toolbox = _toolbox(project_root)

    events = toolbox.execute(
        "get_events", {"time_window": "incident_and_after", "scope": "billing"}
    )

    assert len(events["events"]) == 1
    assert events["events"][0]["event_type"] == "routing_configuration"


def test_openai_tool_schemas_are_strict_and_require_every_property(project_root: Path) -> None:
    toolbox = _toolbox(project_root)

    for schema in toolbox.schemas:
        parameters = schema["parameters"]
        assert schema["strict"] is True
        assert set(parameters.get("required", [])) == set(parameters.get("properties", {}))
