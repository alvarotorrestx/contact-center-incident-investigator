from __future__ import annotations

import inspect
import json
import shutil
from pathlib import Path

import pytest
from helpers import MappingMockBaselineClient, MockBaselineClient, diagnosis_from_truth
from test_v2_batch import MappingV2Client

from incident_investigator.adaptive_escalation import (
    AdaptiveEscalationRunner,
    EscalationCheck,
    EscalationDecision,
    build_adaptive_investigation_prompt,
    evaluate_escalation,
)
from incident_investigator.adaptive_escalation.batch import (
    run_adaptive_batch,
    run_live_adaptive,
)
from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.config import get_settings
from incident_investigator.contracts import FinalDiagnosis, VisibleCase
from incident_investigator.evaluation import (
    FINAL_CANDIDATE_RUN_ID,
    STAGE0_ANCHOR_RUN_ID,
    V1_RUN_ID,
    V2_RUN_ID,
    V3_RUN_ID,
    GroundTruthLoader,
)
from incident_investigator.persistence import RunStore
from incident_investigator.tools import CaseToolbox


def _supported_diagnosis(project_root: Path, incident_id: str = "CC-001") -> FinalDiagnosis:
    truth = GroundTruthLoader(project_root / "benchmark" / "v1" / "ground_truth").load(incident_id)
    payload = diagnosis_from_truth(truth).model_dump(mode="json")
    payload["evidence"] = [
        {
            "signal": "service_level_decline",
            "source": "performance",
            "finding": "Service level declined after incident onset.",
        },
        {
            "signal": "actual_above_forecast",
            "source": "forecast",
            "finding": "Actual demand exceeded the independently generated forecast.",
        },
    ]
    return FinalDiagnosis.model_validate(payload)


def test_generic_gate_direct_path_and_no_incident_specific_logic(project_root: Path) -> None:
    case = AgentVisibleCaseLoader(project_root / "benchmark" / "v1" / "cases").load("CC-001")
    decision = evaluate_escalation(case, _supported_diagnosis(project_root))

    assert decision.escalate is False
    assert decision.triggers == ()
    assert [check.check_id for check in decision.checks] == [
        "first_pass_inconclusive",
        "low_first_pass_confidence",
        "insufficient_independent_evidence",
        "visible_metric_consistency_failure",
        "event_claim_temporal_conflict",
    ]
    assert "CC-" not in inspect.getsource(evaluate_escalation)
    assert "incident_id ==" not in inspect.getsource(evaluate_escalation)


def test_gate_rejects_mismatched_visible_case_and_diagnosis(project_root: Path) -> None:
    case = AgentVisibleCaseLoader(project_root / "benchmark" / "v1" / "cases").load("CC-002")
    with pytest.raises(ValueError, match="does not match"):
        evaluate_escalation(case, _supported_diagnosis(project_root, "CC-001"))


def test_gate_escalates_uncertainty_insufficient_support_and_visible_inconsistency(
    project_root: Path,
) -> None:
    case = AgentVisibleCaseLoader(project_root / "benchmark" / "v1" / "cases").load("CC-001")
    payload = _supported_diagnosis(project_root).model_dump(mode="json")
    payload["investigation_status"] = "INCONCLUSIVE"
    payload["confidence"] = 0.5
    payload["evidence"] = [payload["evidence"][0]]
    uncertain = FinalDiagnosis.model_validate(payload)
    decision = evaluate_escalation(case, uncertain)
    assert set(decision.triggers) == {
        "first_pass_inconclusive",
        "low_first_pass_confidence",
        "insufficient_independent_evidence",
    }

    visible_payload = case.model_dump(mode="json")
    visible_payload["performance"][0]["service_level_pct"] += 20
    inconsistent = VisibleCase.model_validate(visible_payload)
    inconsistency_decision = evaluate_escalation(inconsistent, _supported_diagnosis(project_root))
    assert "visible_metric_consistency_failure" in inconsistency_decision.triggers


def test_gate_escalates_event_dependent_claim_without_timely_event(project_root: Path) -> None:
    case = AgentVisibleCaseLoader(project_root / "benchmark" / "v1" / "cases").load("CC-001")
    payload = _supported_diagnosis(project_root).model_dump(mode="json")
    payload["primary_root_cause_category"] = "ROUTING_CHANGE"
    payload["evidence"][1] = {
        "signal": "routing_change_event",
        "source": "events",
        "finding": "A routing event was claimed.",
    }
    decision = evaluate_escalation(case, FinalDiagnosis.model_validate(payload))
    assert decision.triggers == ("event_claim_temporal_conflict",)


def test_adaptive_prompt_contains_visible_case_and_unverified_first_pass(
    project_root: Path,
) -> None:
    case = AgentVisibleCaseLoader(project_root / "benchmark" / "v1" / "cases").load("CC-001")
    diagnosis = _supported_diagnosis(project_root)
    prompt = build_adaptive_investigation_prompt(
        case,
        diagnosis,
        CaseToolbox(case),
        project_root,
        10,
    )
    payload = json.loads(prompt.user)
    assert payload["experiment"] == "adaptive_escalation"
    assert payload["incident"] == case.model_dump(mode="json")
    assert payload["first_pass_diagnosis"] == diagnosis.model_dump(mode="json")
    assert "unverified starting hypothesis" in payload["first_pass_instruction"]
    assert "correct or incorrect" in payload["first_pass_instruction"]
    assert prompt.version == "adaptive_escalation_deep_investigation_1"
    assert len(prompt.operational_tools) == 9


class _NeverDeepClient:
    model = "gpt-5.6-sol"
    reasoning_effort = "medium"

    def respond(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("Deep investigation must not run without escalation")


class _DifferentModelDeepClient(_NeverDeepClient):
    model = "different-model"


def test_adaptive_runner_requires_same_model(project_root: Path) -> None:
    diagnosis = _supported_diagnosis(project_root)
    first_client = MockBaselineClient(diagnosis)
    first_client.model = "gpt-5.6-sol"
    with pytest.raises(ValueError, match="same model"):
        AdaptiveEscalationRunner(
            AgentVisibleCaseLoader(project_root / "benchmark" / "v1" / "cases"),
            first_client,
            _DifferentModelDeepClient(),
            RunStore(project_root),
        )


def test_live_adaptive_rejects_missing_key_and_wrong_model(project_root: Path) -> None:
    settings = get_settings(project_root)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        run_live_adaptive(settings.model_copy(update={"openai_api_key": None}))
    with pytest.raises(ValueError, match="OPENAI_MODEL=gpt-5.6-sol"):
        run_live_adaptive(
            settings.model_copy(
                update={"openai_api_key": "test-placeholder", "openai_model": "wrong-model"}
            )
        )


def test_no_escalation_preserves_first_pass_and_never_invokes_v2(project_root: Path) -> None:
    diagnosis = _supported_diagnosis(project_root)
    first_client = MockBaselineClient(diagnosis)
    first_client.model = "gpt-5.6-sol"
    store = RunStore(project_root)
    runner = AdaptiveEscalationRunner(
        AgentVisibleCaseLoader(project_root / "benchmark" / "v1" / "cases"),
        first_client,
        _NeverDeepClient(),
        store,
    )

    result = runner.run_case("CC-001")

    assert result.escalation.escalate is False
    assert result.diagnosis == diagnosis
    assert result.tool_call_count == 0
    prediction = json.loads(
        (store.result_root / "predictions" / "CC-001.json").read_text(encoding="utf-8")
    )
    assert prediction == diagnosis.model_dump(mode="json")
    events = [
        json.loads(line)
        for line in (store.trajectory_root / "CC-001.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [event["step_number"] for event in events] == [1, 2, 3, 4]
    assert events[-1]["termination_reason"] == "first_pass_finalized"


def test_escalation_invokes_bounded_v2_after_gate_and_orders_trajectory(
    project_root: Path,
) -> None:
    truth = GroundTruthLoader(project_root / "benchmark" / "v1" / "ground_truth").load("CC-001")
    first_pass = _supported_diagnosis(project_root)
    final = diagnosis_from_truth(truth)
    first_client = MockBaselineClient(first_pass)
    first_client.model = "gpt-5.6-sol"
    deep_client = MappingV2Client({"CC-001": final})
    store = RunStore(project_root)
    forced = EscalationDecision(
        escalate=True,
        triggers=("test_generic_trigger",),
        checks=(
            EscalationCheck(
                check_id="test_generic_trigger",
                triggered=True,
                summary="Test-only deterministic trigger.",
                observed={},
            ),
        ),
    )
    runner = AdaptiveEscalationRunner(
        AgentVisibleCaseLoader(project_root / "benchmark" / "v1" / "cases"),
        first_client,
        deep_client,
        store,
        max_tool_calls=10,
        gate=lambda case, diagnosis: forced,
    )

    result = runner.run_case("CC-001")

    assert result.escalation.escalate is True
    assert result.tool_call_count == 2
    assert result.hypothesis_update_count == 3
    events = [
        json.loads(line)
        for line in (store.trajectory_root / "CC-001.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    steps = [event["step_number"] for event in events]
    assert steps == sorted(steps)
    assert len(steps) == len(set(steps))
    assert events[2]["event_type"] == "escalation_decision"
    assert any(event["event_type"] == "hypothesis_update" for event in events[3:])
    assert events[-1]["event_type"] == "final_output"
    assert events[-1]["tool_call_count"] <= 10
    assert not any(event["agent_stage"] == "verifier" for event in events)


def test_adaptive_batch_persists_analysis_and_compares_all_anchors(
    isolated_project: Path,
    project_root: Path,
) -> None:
    anchor_ids = [
        STAGE0_ANCHOR_RUN_ID,
        V1_RUN_ID,
        V2_RUN_ID,
        V3_RUN_ID,
        FINAL_CANDIDATE_RUN_ID,
    ]
    for run_id in anchor_ids:
        shutil.copytree(
            project_root / "results" / "curated" / run_id,
            isolated_project / "results" / "curated" / run_id,
        )
        shutil.copytree(
            project_root / "trajectories" / "curated" / run_id,
            isolated_project / "trajectories" / "curated" / run_id,
        )
    truths = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load_all()
    diagnoses = {truth.incident_id: diagnosis_from_truth(truth) for truth in truths}
    first_client = MappingMockBaselineClient(diagnoses)
    first_client.model = "gpt-5.6-sol"
    deep_client = MappingV2Client(diagnoses)

    run_id, scores, comparisons, analysis = run_adaptive_batch(
        get_settings(isolated_project), first_client, deep_client
    )

    assert scores["rcia"] == 1.0
    assert set(comparisons) == {"stage0", "v1", "v2", "v3", "final_candidate"}
    assert analysis["cases_escalated"] == 10
    assert analysis["cases_finalized_directly"] == 0
    result_root = isolated_project / "results" / "local" / run_id
    manifest = json.loads((result_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["system_version"] == "adaptive_escalation"
    assert manifest["escalation_gate_version"] == "adaptive_gate_1"
    assert manifest["failure_count"] == 0
    assert manifest["aggregate_verifier_calls"] == 0
    assert manifest["aggregate_revisions"] == 0
    assert (result_root / "adaptive_analysis.json").is_file()
    assert (result_root / "adaptive_analysis.md").is_file()
    assert len(list((result_root / "first_pass_predictions").glob("CC-*.json"))) == 10
    for key in comparisons:
        for suffix in ["json", "csv", "md"]:
            assert (result_root / f"comparison_to_{key}.{suffix}").is_file()
