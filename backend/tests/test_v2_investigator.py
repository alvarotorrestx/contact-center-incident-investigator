from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from helpers import diagnosis_from_truth

from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.contracts import InvestigationStatus
from incident_investigator.evaluation import GroundTruthLoader
from incident_investigator.investigator import InvestigatorTurn, RequestedToolCall, ToolOutput
from incident_investigator.persistence import RunStore
from incident_investigator.structured_investigator import (
    OpenAIV2InvestigatorClient,
    StructuredHypothesisRunner,
    V2Prompt,
)


def _evidence(signal: str, source_tool: str) -> dict[str, str]:
    return {
        "signal": signal,
        "source_tool": source_tool,
        "finding": f"Observed {signal}.",
    }


def _ledger_call(call_id: str, *, state: str) -> RequestedToolCall:
    ready = state == "ready"
    partial = state == "partial"
    return RequestedToolCall(
        call_id=call_id,
        name="record_hypothesis_ledger",
        arguments={
            "decision_summary": "Update competing explanations.",
            "ledger": {
                "hypotheses": [
                    {
                        "category": "DEMAND_SPIKE",
                        "status": "LIKELY" if ready else "POSSIBLE",
                        "confidence": 0.85 if ready else (0.5 if partial else 0.4),
                        "evidence_for": (
                            [
                                _evidence("demand_surge", "compare_actual_vs_forecast"),
                                _evidence("service_level_decline", "get_performance_trends"),
                            ]
                            if ready
                            else (
                                [_evidence("service_level_decline", "get_performance_trends")]
                                if partial
                                else []
                            )
                        ),
                        "evidence_against": [],
                    },
                    {
                        "category": "STAFFING_SHORTFALL",
                        "status": "UNLIKELY" if ready else "UNTESTED",
                        "confidence": 0.1 if ready else 0.3,
                        "evidence_for": [],
                        "evidence_against": (
                            [_evidence("stable_staffing", "get_performance_trends")]
                            if ready
                            else []
                        ),
                    },
                    {
                        "category": "HANDLE_TIME_INCREASE",
                        "status": "UNLIKELY" if ready else "UNTESTED",
                        "confidence": 0.05 if ready else 0.3,
                        "evidence_for": [],
                        "evidence_against": (
                            [_evidence("actual_above_forecast", "compare_actual_vs_forecast")]
                            if ready
                            else []
                        ),
                    },
                ],
                "leading_hypothesis": "DEMAND_SPIKE" if ready else None,
                "causal_timing_supported": ready,
                "unresolved_critical_contradictions": [],
                "investigation_summary": "Demand leads." if ready else "Alternatives initialized.",
            },
        },
    )


class MultiStepV2Client:
    model = "gpt-5.6-sol"
    reasoning_effort = "medium"

    def __init__(self, diagnosis: object, *, premature: bool = False):
        self.diagnosis = diagnosis
        self.premature = premature
        self.turn = 0
        self.modes: list[str] = []

    def respond(
        self,
        prompt: V2Prompt,
        *,
        mode: str,
        previous_response_id: str | None = None,
        tool_outputs: list[ToolOutput] | None = None,
        instruction: str | None = None,
    ) -> InvestigatorTurn:
        self.turn += 1
        self.modes.append(mode)
        if self.turn == 1:
            return InvestigatorTurn(
                response_id="r1", tool_calls=[_ledger_call("l1", state="initial")]
            )
        if self.turn == 2:
            return InvestigatorTurn(
                response_id="r2",
                tool_calls=[RequestedToolCall("t1", "get_performance_trends", {})],
            )
        if self.turn == 3:
            return InvestigatorTurn(
                response_id="r3", tool_calls=[_ledger_call("l2", state="partial")]
            )
        if self.turn == 4 and self.premature:
            return InvestigatorTurn(response_id="premature", diagnosis=self.diagnosis)
        operational_turn = 5 if self.premature else 4
        if self.turn == operational_turn:
            assert not self.premature or instruction and "blocked" in instruction
            return InvestigatorTurn(
                response_id="r4",
                tool_calls=[RequestedToolCall("t2", "compare_actual_vs_forecast", {})],
            )
        if self.turn == operational_turn + 1:
            return InvestigatorTurn(
                response_id="r5", tool_calls=[_ledger_call("l3", state="ready")]
            )
        return InvestigatorTurn(
            response_id="final",
            diagnosis=self.diagnosis,
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )


class OneToolInconclusiveClient:
    model = "gpt-5.6-sol"
    reasoning_effort = "medium"

    def __init__(self, diagnosis: object):
        self.diagnosis = diagnosis
        self.turn = 0

    def respond(self, prompt: V2Prompt, *, mode: str, **kwargs: object) -> InvestigatorTurn:
        self.turn += 1
        if self.turn == 1:
            return InvestigatorTurn(
                response_id="r1", tool_calls=[_ledger_call("l1", state="initial")]
            )
        if self.turn == 2:
            return InvestigatorTurn(
                response_id="r2",
                tool_calls=[RequestedToolCall("t1", "get_performance_trends", {})],
            )
        if self.turn == 3:
            return InvestigatorTurn(
                response_id="r3", tool_calls=[_ledger_call("l2", state="partial")]
            )
        assert mode == "force_final"
        return InvestigatorTurn(response_id="final", diagnosis=self.diagnosis)


class InvalidLedgerClient:
    model = "gpt-5.6-sol"
    reasoning_effort = "medium"

    def __init__(self) -> None:
        self.turn = 0

    def respond(self, prompt: V2Prompt, *, mode: str, **kwargs: object) -> InvestigatorTurn:
        self.turn += 1
        return InvestigatorTurn(
            response_id=f"invalid-{self.turn}",
            tool_calls=[_ledger_call(f"invalid-{self.turn}", state="ready")],
        )


def _runner(
    isolated_project: Path,
    client: object,
    *,
    max_tool_calls: int = 10,
) -> tuple[StructuredHypothesisRunner, RunStore]:
    store = RunStore(isolated_project)
    return (
        StructuredHypothesisRunner(
            AgentVisibleCaseLoader(isolated_project / "benchmark" / "v1" / "cases"),
            client,
            store,
            max_tool_calls=max_tool_calls,
        ),
        store,
    )


def test_mocked_multistep_investigation_records_hypothesis_snapshots(
    isolated_project: Path,
) -> None:
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    client = MultiStepV2Client(diagnosis_from_truth(truth))
    runner, store = _runner(isolated_project, client)

    result = runner.run_case("CC-001")
    events = [
        json.loads(line)
        for line in (store.trajectory_root / "CC-001.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]

    assert result.tool_call_count == 2
    assert result.hypothesis_update_count == 3
    assert result.termination_reason == "criteria_satisfied"
    snapshots = [item for item in events if item["event_type"] == "hypothesis_update"]
    assert len(snapshots) == 3
    assert snapshots[-1]["hypothesis_state_before"]
    assert snapshots[-1]["hypothesis_state_after"]["leading_hypothesis"] == "DEMAND_SPIKE"
    assert events[-1]["final_hypothesis_state"] == snapshots[-1]["hypothesis_state_after"]
    assert [item["step_number"] for item in events] == sorted(
        item["step_number"] for item in events
    )


def test_premature_completion_is_blocked_until_alternatives_are_evaluated(
    isolated_project: Path,
) -> None:
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    client = MultiStepV2Client(diagnosis_from_truth(truth), premature=True)
    runner, store = _runner(isolated_project, client)

    result = runner.run_case("CC-001")
    trajectory = (store.trajectory_root / "CC-001.jsonl").read_text(encoding="utf-8")

    assert result.premature_completion_attempts == 1
    assert "premature_completion_blocked" in trajectory
    assert result.tool_call_count == 2


def test_tool_bound_allows_only_inconclusive_when_criteria_remain_unmet(
    isolated_project: Path,
) -> None:
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    inconclusive = diagnosis_from_truth(truth).model_copy(
        update={"investigation_status": InvestigationStatus.INCONCLUSIVE}
    )
    client = OneToolInconclusiveClient(inconclusive)
    runner, _ = _runner(isolated_project, client, max_tool_calls=1)

    result = runner.run_case("CC-001")

    assert result.tool_call_count == 1
    assert result.termination_reason == "tool_limit_inconclusive"


def test_every_rejected_ledger_attempt_is_preserved_before_retry_bound(
    isolated_project: Path,
) -> None:
    client = InvalidLedgerClient()
    runner, store = _runner(isolated_project, client)

    with pytest.raises(ValueError, match="repeatedly returned invalid"):
        runner.run_case("CC-001")

    events = [
        json.loads(line)
        for line in (store.trajectory_root / "CC-001.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    rejected = [item for item in events if item["event_type"] == "hypothesis_update_rejected"]
    assert len(rejected) == 3
    assert all(item["proposed_hypothesis_update"] for item in rejected)


def test_openai_v2_transport_forces_ledger_updates_and_preserves_structured_final(
    isolated_project: Path,
) -> None:
    captured: list[dict[str, object]] = []
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    diagnosis = diagnosis_from_truth(truth)

    class FakeResponses:
        def parse(self, **kwargs: object) -> object:
            captured.append(kwargs)
            if kwargs["tool_choice"] == "none":
                return SimpleNamespace(
                    id="final",
                    output=[],
                    output_parsed=diagnosis,
                    output_text="",
                    usage=None,
                )
            tool = kwargs["tools"][0]
            return SimpleNamespace(
                id=f"response-{len(captured)}",
                output=[
                    SimpleNamespace(
                        type="function_call",
                        call_id=f"call-{len(captured)}",
                        name=tool["name"],
                        arguments="{}",
                        parsed_arguments={},
                    )
                ],
                output_parsed=None,
                output_text="",
                usage=None,
            )

    client = OpenAIV2InvestigatorClient(
        api_key="test-only-placeholder",
        model="gpt-5.6-sol",
        reasoning_effort="medium",
    )
    client._client = SimpleNamespace(responses=FakeResponses())
    prompt = V2Prompt(
        system="system",
        user="user",
        operational_tools=[
            {
                "type": "function",
                "name": "get_performance_trends",
                "description": "Trends.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                "strict": True,
            }
        ],
        ledger_tool={
            "type": "function",
            "name": "record_hypothesis_ledger",
            "description": "Ledger.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "strict": True,
        },
        version="test",
    )

    client.respond(prompt, mode="initialize_ledger")
    client.respond(
        prompt,
        mode="investigate",
        previous_response_id="response-1",
        tool_outputs=[ToolOutput("call-1", {"ok": True})],
    )
    final = client.respond(
        prompt,
        mode="force_final",
        previous_response_id="response-2",
        instruction="Return final.",
    )

    assert captured[0]["tool_choice"] == "required"
    assert captured[0]["tools"][0]["name"] == "record_hypothesis_ledger"
    assert "text_format" not in captured[0]
    assert captured[1]["tool_choice"] == "auto"
    assert captured[1]["tools"][0]["name"] == "get_performance_trends"
    assert captured[1]["text_format"].__name__ == "FinalDiagnosis"
    assert captured[2]["tools"] == []
    assert captured[2]["tool_choice"] == "none"
    assert captured[2]["reasoning"] == {"effort": "medium"}
    assert final.diagnosis == diagnosis
    assert "test-only-placeholder" not in str(captured)
