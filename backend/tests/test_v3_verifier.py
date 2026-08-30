from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from helpers import diagnosis_from_truth
from pydantic import ValidationError
from test_v2_investigator import MultiStepV2Client, OneToolInconclusiveClient, _ledger_call

from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.contracts import InvestigationStatus
from incident_investigator.evaluation import GroundTruthLoader
from incident_investigator.hypotheses import HypothesisLedgerUpdate
from incident_investigator.persistence import RunStore
from incident_investigator.structured_investigator import StructuredHypothesisRunner
from incident_investigator.verifier import (
    OpenAIVerifierClient,
    VerificationCheck,
    VerificationFinding,
    VerificationResult,
    VerificationStatus,
    VerifierPrompt,
    VerifierResponse,
    build_verifier_prompt,
)


def _verified(summary: str = "The proposal survives the challenge.") -> VerificationResult:
    return VerificationResult(
        verification_status=VerificationStatus.VERIFIED,
        critical_contradictions=[],
        unsupported_or_weak_claims=[],
        stronger_alternative_if_any=None,
        recommended_revision=None,
        verification_summary=summary,
    )


def _revise() -> VerificationResult:
    return VerificationResult(
        verification_status=VerificationStatus.REVISE,
        critical_contradictions=[
            VerificationFinding(
                check=VerificationCheck.CONTRADICTORY_EVIDENCE,
                finding="A visible trend conflicts with the claimed magnitude.",
                evidence_signal=None,
                source_tool=None,
            )
        ],
        unsupported_or_weak_claims=[],
        stronger_alternative_if_any=None,
        recommended_revision="Reconcile the magnitude conflict or lower confidence.",
        verification_summary="A material contradiction needs resolution.",
    )


class SequencedVerifier:
    model = "gpt-5.6-sol"
    reasoning_effort = "medium"

    def __init__(self, *results: VerificationResult):
        self.results = list(results)
        self.prompts: list[VerifierPrompt] = []

    def verify(self, prompt: VerifierPrompt) -> VerifierResponse:
        self.prompts.append(prompt)
        result = self.results.pop(0)
        return VerifierResponse(
            result=result,
            response_id=f"verifier-{len(self.prompts)}",
            usage={"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
        )


def _runner(
    isolated_project: Path,
    investigator: object,
    verifier: SequencedVerifier,
    *,
    max_tool_calls: int = 10,
) -> tuple[StructuredHypothesisRunner, RunStore]:
    store = RunStore(isolated_project)
    runner = StructuredHypothesisRunner(
        AgentVisibleCaseLoader(isolated_project / "benchmark" / "v1" / "cases"),
        investigator,
        store,
        max_tool_calls=max_tool_calls,
        verifier_client=verifier,
        max_revisions=2,
        system_version="v3_adversarial_verification",
    )
    return runner, store


def test_verifier_schema_enforces_status_consistency() -> None:
    assert _verified().verification_status is VerificationStatus.VERIFIED
    verified_with_minor_recommendation = VerificationResult(
        verification_status="VERIFIED",
        critical_contradictions=[],
        unsupported_or_weak_claims=[],
        stronger_alternative_if_any=None,
        recommended_revision="Clarify one non-material sentence.",
        verification_summary="The proposal survives the material challenge.",
    )
    assert verified_with_minor_recommendation.verification_status is VerificationStatus.VERIFIED
    with pytest.raises(ValidationError, match="VERIFIED cannot include"):
        VerificationResult(
            verification_status="VERIFIED",
            critical_contradictions=_revise().critical_contradictions,
            unsupported_or_weak_claims=[],
            stronger_alternative_if_any=None,
            recommended_revision=None,
            verification_summary="Invalid.",
        )
    with pytest.raises(ValidationError, match="REVISE requires"):
        VerificationResult(
            verification_status="REVISE",
            critical_contradictions=[],
            unsupported_or_weak_claims=[],
            stronger_alternative_if_any=None,
            recommended_revision=None,
            verification_summary="Invalid.",
        )


def test_verified_path_finalizes_without_revision(isolated_project: Path) -> None:
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    investigator = MultiStepV2Client(diagnosis_from_truth(truth))
    verifier = SequencedVerifier(_verified())
    runner, _ = _runner(isolated_project, investigator, verifier)

    result = runner.run_case("CC-001")

    assert result.verifier_call_count == 1
    assert result.revision_count == 0
    assert result.termination_reason == "verifier_verified"
    assert len(result.proposed_diagnoses) == 1


def test_revise_then_verify_can_preserve_the_diagnosis(isolated_project: Path) -> None:
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    diagnosis = diagnosis_from_truth(truth)
    investigator = MultiStepV2Client(diagnosis)
    verifier = SequencedVerifier(_revise(), _verified("The contradiction was addressed."))
    runner, store = _runner(isolated_project, investigator, verifier)

    result = runner.run_case("CC-001")
    events = [
        json.loads(line)
        for line in (store.trajectory_root / "CC-001.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    event_types = [event["event_type"] for event in events]

    assert result.diagnosis == diagnosis
    assert result.verifier_call_count == 2
    assert result.revision_count == 1
    assert len(result.proposed_diagnoses) == 2
    assert investigator.modes[-1] == "revise"
    expected = [
        "proposed_diagnosis",
        "verifier_invocation",
        "verifier_result",
        "revision_requested",
        "proposed_diagnosis",
        "verifier_invocation",
        "verifier_result",
        "final_output",
    ]
    positions: list[int] = []
    for name in expected:
        positions.append(event_types.index(name, positions[-1] + 1 if positions else 0))
    assert positions == sorted(positions)
    assert events[-1]["final_hypothesis_state"]


def test_revision_limit_allows_only_two_revisions(isolated_project: Path) -> None:
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    investigator = MultiStepV2Client(diagnosis_from_truth(truth))
    verifier = SequencedVerifier(_revise(), _revise(), _revise())
    runner, _ = _runner(isolated_project, investigator, verifier)

    result = runner.run_case("CC-001")

    assert result.revision_count == 2
    assert result.verifier_call_count == 3
    assert len(result.proposed_diagnoses) == 3
    assert result.termination_reason == "revision_limit_reached"


def test_insufficient_evidence_can_finish_inconclusive(isolated_project: Path) -> None:
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    diagnosis = diagnosis_from_truth(truth).model_copy(
        update={"investigation_status": InvestigationStatus.INCONCLUSIVE}
    )
    investigator = OneToolInconclusiveClient(diagnosis)
    verifier = SequencedVerifier(_verified("Inconclusive is appropriately restrained."))
    runner, _ = _runner(
        isolated_project,
        investigator,
        verifier,
        max_tool_calls=1,
    )

    result = runner.run_case("CC-001")

    assert result.diagnosis.investigation_status is InvestigationStatus.INCONCLUSIVE
    assert result.verifier_call_count == 1
    assert result.revision_count == 0


def test_verifier_prompt_is_generic_and_contains_no_evaluator_fields(
    isolated_project: Path,
) -> None:
    loader = AgentVisibleCaseLoader(isolated_project / "benchmark" / "v1" / "cases")
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    case = loader.load("CC-001")
    ledger = HypothesisLedgerUpdate.model_validate(
        _ledger_call("ledger", state="ready").arguments
    ).ledger
    prompt = build_verifier_prompt(
        incident_metadata=case.incident_metadata,
        proposed_diagnosis=diagnosis_from_truth(truth),
        hypothesis_state=ledger,
        tool_evidence=[{"tool_name": "get_performance_trends", "output": {"ok": True}}],
        project_root=isolated_project,
        revision_number=0,
    )

    assert "material" in prompt.system.lower()
    assert "contradict" in prompt.system.lower()
    assert not any(f"CC-{number:03d}" in prompt.system for number in range(1, 1000))
    for key in [
        "primary_root_cause",
        "expected_evidence",
        "supported_signal_ids",
        "expected_causal_chain",
        "intentional_exceptions",
    ]:
        assert f'"{key}":' not in prompt.user


def test_openai_verifier_transport_is_tool_free_and_structured() -> None:
    captured: list[dict[str, object]] = []

    class FakeResponses:
        def parse(self, **kwargs: object) -> object:
            captured.append(kwargs)
            return SimpleNamespace(
                id="verification-1",
                output_parsed=_verified(),
                usage=SimpleNamespace(model_dump=lambda **_: {"total_tokens": 12}),
            )

    client = OpenAIVerifierClient(
        api_key="test-only-placeholder",
        model="gpt-5.6-sol",
        reasoning_effort="medium",
    )
    client._client = SimpleNamespace(responses=FakeResponses())
    response = client.verify(VerifierPrompt(system="system", user="visible", version="test"))

    assert response.result.verification_status is VerificationStatus.VERIFIED
    assert captured[0]["tools"] == []
    assert captured[0]["tool_choice"] == "none"
    assert captured[0]["parallel_tool_calls"] is False
    assert captured[0]["reasoning"] == {"effort": "medium"}
    assert captured[0]["text_format"] is VerificationResult
    assert "test-only-placeholder" not in str(captured)
