from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from incident_investigator.adaptive_escalation import (
    build_adaptive_investigation_prompt,
    evaluate_escalation,
)
from incident_investigator.baseline import build_baseline_prompt
from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.evaluation import GroundTruthLoader
from incident_investigator.final_candidate.prompting import build_final_candidate_prompt
from incident_investigator.investigator import build_investigator_prompt
from incident_investigator.structured_investigator import build_v2_prompt
from incident_investigator.tools import CaseToolbox

EVALUATOR_ONLY_KEYS = {
    "primary_root_cause",
    "expected_evidence",
    "supported_signal_ids",
    "expected_causal_chain",
    "intentional_exceptions",
}


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _all_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _all_keys(item)}
    return set()


def test_ground_truth_never_reaches_loader_or_prompt(project_root: Path) -> None:
    loader = AgentVisibleCaseLoader(project_root / "benchmark" / "v1" / "cases")
    truth_loader = GroundTruthLoader(project_root / "benchmark" / "v1" / "ground_truth")

    for summary in loader.list_incidents():
        visible = loader.load(summary.incident_id)
        visible_payload = visible.model_dump(mode="json")
        assert not (_all_keys(visible_payload) & EVALUATOR_ONLY_KEYS)

        prompt = build_baseline_prompt(visible, project_root)
        for key in EVALUATOR_ONLY_KEYS:
            assert f'"{key}":' not in prompt.user
        truth = truth_loader.load(summary.incident_id)
        assert truth.primary_root_cause.detail not in prompt.user

        toolbox = CaseToolbox(visible)
        investigator_prompt = build_investigator_prompt(visible, toolbox, project_root, 10)
        for key in EVALUATOR_ONLY_KEYS:
            assert f'"{key}":' not in investigator_prompt.user
        assert truth.primary_root_cause.detail not in investigator_prompt.user
        for schema in investigator_prompt.tools:
            assert not (_all_keys(schema) & EVALUATOR_ONLY_KEYS)
        for schema in investigator_prompt.tools:
            result = toolbox.execute(schema["name"], _valid_tool_arguments(schema["name"], toolbox))
            assert not (_all_keys(result) & EVALUATOR_ONLY_KEYS)

        v2_prompt = build_v2_prompt(visible, toolbox, project_root, 10)
        for key in EVALUATOR_ONLY_KEYS:
            assert f'"{key}":' not in v2_prompt.user
        assert truth.primary_root_cause.detail not in v2_prompt.user
        for schema in [*v2_prompt.operational_tools, v2_prompt.ledger_tool]:
            assert not (_all_keys(schema) & EVALUATOR_ONLY_KEYS)

        final_candidate_prompt = build_final_candidate_prompt(visible, toolbox, project_root, 10)
        final_payload = json.loads(final_candidate_prompt.user)
        assert final_payload["incident"] == visible_payload
        for key in EVALUATOR_ONLY_KEYS:
            assert f'"{key}":' not in final_candidate_prompt.user
        assert truth.primary_root_cause.detail not in final_candidate_prompt.user
        for schema in [
            *final_candidate_prompt.operational_tools,
            final_candidate_prompt.ledger_tool,
        ]:
            assert not (_all_keys(schema) & EVALUATOR_ONLY_KEYS)

        adaptive_decision = evaluate_escalation(visible, diagnosis_from_visible_fixture(visible))
        assert not (_all_keys(adaptive_decision.to_dict()) & EVALUATOR_ONLY_KEYS)
        adaptive_prompt = build_adaptive_investigation_prompt(
            visible,
            diagnosis_from_visible_fixture(visible),
            toolbox,
            project_root,
            10,
        )
        for key in EVALUATOR_ONLY_KEYS:
            assert f'"{key}":' not in adaptive_prompt.user
        assert truth.primary_root_cause.detail not in adaptive_prompt.user


def test_agent_and_api_modules_do_not_import_evaluator(project_root: Path) -> None:
    protected = [
        project_root / "backend" / "src" / "incident_investigator" / "api",
        project_root / "backend" / "src" / "incident_investigator" / "presentation",
        project_root / "backend" / "src" / "incident_investigator" / "baseline" / "client.py",
        project_root / "backend" / "src" / "incident_investigator" / "baseline" / "prompting.py",
        project_root / "backend" / "src" / "incident_investigator" / "baseline" / "runner.py",
        project_root / "backend" / "src" / "incident_investigator" / "benchmark" / "loader.py",
        project_root / "backend" / "src" / "incident_investigator" / "investigator" / "client.py",
        project_root
        / "backend"
        / "src"
        / "incident_investigator"
        / "investigator"
        / "prompting.py",
        project_root / "backend" / "src" / "incident_investigator" / "investigator" / "runner.py",
        project_root / "backend" / "src" / "incident_investigator" / "tools",
        project_root / "backend" / "src" / "incident_investigator" / "hypotheses",
        project_root
        / "backend"
        / "src"
        / "incident_investigator"
        / "structured_investigator"
        / "client.py",
        project_root
        / "backend"
        / "src"
        / "incident_investigator"
        / "structured_investigator"
        / "prompting.py",
        project_root
        / "backend"
        / "src"
        / "incident_investigator"
        / "structured_investigator"
        / "runner.py",
        project_root / "backend" / "src" / "incident_investigator" / "verifier" / "client.py",
        project_root / "backend" / "src" / "incident_investigator" / "verifier" / "models.py",
        project_root / "backend" / "src" / "incident_investigator" / "verifier" / "prompting.py",
        project_root
        / "backend"
        / "src"
        / "incident_investigator"
        / "final_candidate"
        / "prompting.py",
        project_root
        / "backend"
        / "src"
        / "incident_investigator"
        / "final_candidate"
        / "__init__.py",
        project_root
        / "backend"
        / "src"
        / "incident_investigator"
        / "adaptive_escalation"
        / "__init__.py",
        project_root
        / "backend"
        / "src"
        / "incident_investigator"
        / "adaptive_escalation"
        / "gate.py",
        project_root
        / "backend"
        / "src"
        / "incident_investigator"
        / "adaptive_escalation"
        / "prompting.py",
        project_root
        / "backend"
        / "src"
        / "incident_investigator"
        / "adaptive_escalation"
        / "runner.py",
    ]
    for path in protected:
        files = path.rglob("*.py") if path.is_dir() else [path]
        for file in files:
            source = file.read_text(encoding="utf-8")
            assert "incident_investigator.evaluation" not in source
            assert "ground_truth" not in source.lower()

    check = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import incident_investigator.api; "
                "forbidden=('incident_investigator.evaluation', "
                "'incident_investigator.benchmark.definitions', "
                "'incident_investigator.benchmark.generator', "
                "'incident_investigator.benchmark.validation'); "
                "assert not any(name.startswith(forbidden) for name in sys.modules), "
                "sorted(name for name in sys.modules if name.startswith(forbidden))"
            ),
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr

    final_candidate_check = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import incident_investigator.final_candidate; "
                "assert 'incident_investigator.evaluation' not in sys.modules"
            ),
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert final_candidate_check.returncode == 0, final_candidate_check.stderr

    adaptive_check = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import incident_investigator.adaptive_escalation; "
                "assert 'incident_investigator.evaluation' not in sys.modules"
            ),
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert adaptive_check.returncode == 0, adaptive_check.stderr


def test_frozen_case_files_contain_no_evaluator_fields(project_root: Path) -> None:
    cases_root = project_root / "benchmark" / "v1" / "cases"
    for path in cases_root.rglob("*"):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for key in EVALUATOR_ONLY_KEYS:
            assert key not in content


def _valid_tool_arguments(name: str, toolbox: CaseToolbox) -> dict[str, object]:
    if name == "analyze_queue":
        return {"queue_name": toolbox.queue_names[0]}
    if name == "get_events":
        return {"time_window": "full", "scope": None}
    if name == "calculate_metric_change":
        return {"metric": "service_level_pct", "time_window": "pre_vs_post_incident"}
    return {}


def diagnosis_from_visible_fixture(visible: object) -> object:
    from incident_investigator.contracts import FinalDiagnosis

    return FinalDiagnosis.model_validate(
        {
            "incident_id": visible.incident_id,
            "investigation_status": "LIKELY",
            "primary_root_cause_category": "DEMAND_SPIKE",
            "primary_root_cause_detail": "Visible demand changed near incident onset.",
            "contributing_factors": [],
            "confidence": 0.8,
            "evidence": [
                {
                    "signal": "service_level_decline",
                    "source": "performance",
                    "finding": "Visible service level changed.",
                },
                {
                    "signal": "actual_above_forecast",
                    "source": "forecast",
                    "finding": "Visible actual demand differed from forecast.",
                },
            ],
            "rejected_hypotheses": [],
            "causal_chain": ["unexpected_demand", "service_level_degradation"],
            "recommended_actions": ["Monitor visible operating metrics."],
            "stakeholder_summary": "Visible operational data was assessed.",
        }
    )
