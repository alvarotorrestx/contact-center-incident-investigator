from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from helpers import diagnosis_from_truth

from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.evaluation import GroundTruthLoader
from incident_investigator.investigator import (
    InvestigatorPrompt,
    InvestigatorTurn,
    OpenAIInvestigatorClient,
    RequestedToolCall,
    ToolInvestigatorRunner,
    ToolOutput,
)
from incident_investigator.persistence import RunStore


class OneToolThenDiagnosisClient:
    model = "gpt-5.6-sol"
    reasoning_effort = "medium"

    def __init__(self, diagnosis: object):
        self.diagnosis = diagnosis
        self.calls = 0

    def respond(
        self,
        prompt: InvestigatorPrompt,
        *,
        previous_response_id: str | None = None,
        tool_outputs: list[object] | None = None,
        allow_tools: bool = True,
    ) -> InvestigatorTurn:
        self.calls += 1
        if self.calls == 1:
            return InvestigatorTurn(
                response_id="response-1",
                tool_calls=[RequestedToolCall("call-1", "analyze_staffing", {})],
                decision_summary="Inspect staffing capacity around the incident boundary.",
                usage={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
            )
        assert previous_response_id == "response-1"
        assert tool_outputs and tool_outputs[0].output["ok"]
        return InvestigatorTurn(
            response_id="response-2",
            diagnosis=self.diagnosis,
            usage={"input_tokens": 80, "output_tokens": 40, "total_tokens": 120},
        )


class UntilBoundClient:
    model = "gpt-5.6-sol"
    reasoning_effort = "medium"

    def __init__(self, diagnosis: object):
        self.diagnosis = diagnosis
        self.tool_turns = 0

    def respond(
        self,
        prompt: InvestigatorPrompt,
        *,
        previous_response_id: str | None = None,
        tool_outputs: list[object] | None = None,
        allow_tools: bool = True,
    ) -> InvestigatorTurn:
        if not allow_tools:
            return InvestigatorTurn(response_id="final", diagnosis=self.diagnosis)
        self.tool_turns += 1
        return InvestigatorTurn(
            response_id=f"response-{self.tool_turns}",
            tool_calls=[
                RequestedToolCall(f"call-{self.tool_turns}", "summarize_incident_window", {})
            ],
        )


def _runner(
    isolated_project: Path,
    client: object,
    max_tool_calls: int = 10,
) -> tuple[ToolInvestigatorRunner, RunStore]:
    store = RunStore(isolated_project)
    return (
        ToolInvestigatorRunner(
            AgentVisibleCaseLoader(isolated_project / "benchmark" / "v1" / "cases"),
            client,
            store,
            max_tool_calls=max_tool_calls,
        ),
        store,
    )


def test_mocked_tool_flow_persists_ordered_auditable_trajectory(
    isolated_project: Path,
) -> None:
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    client = OneToolThenDiagnosisClient(diagnosis_from_truth(truth))
    runner, store = _runner(isolated_project, client)

    result = runner.run_case("CC-001")

    events = [
        json.loads(line)
        for line in (store.trajectory_root / "CC-001.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [event["step_number"] for event in events] == [1, 2, 3, 4]
    assert [event["event_type"] for event in events] == [
        "investigation_started",
        "model_decision",
        "tool_result",
        "final_output",
    ]
    assert events[2]["tool_called"] == "analyze_staffing"
    assert events[3]["total_token_usage"]["total_tokens"] == 240
    assert result.termination_reason == "diagnosis_complete"


def test_tool_call_bound_forces_final_diagnosis(isolated_project: Path) -> None:
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    client = UntilBoundClient(diagnosis_from_truth(truth))
    runner, _ = _runner(isolated_project, client, max_tool_calls=2)

    result = runner.run_case("CC-001")

    assert result.tool_call_count == 2
    assert result.termination_reason == "tool_limit_reached"
    assert client.tool_turns == 2


def test_runner_rejects_unbounded_configuration(isolated_project: Path) -> None:
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    client = OneToolThenDiagnosisClient(diagnosis_from_truth(truth))

    try:
        _runner(isolated_project, client, max_tool_calls=13)
    except ValueError as exc:
        assert "between 1 and 12" in str(exc)
    else:
        raise AssertionError("Expected an invalid tool-call bound to fail")


def test_openai_investigator_request_pins_transport_and_tool_configuration(
    isolated_project: Path,
) -> None:
    captured: list[dict[str, object]] = []
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    diagnosis = diagnosis_from_truth(truth)

    class FakeResponses:
        def parse(self, **kwargs: object) -> object:
            captured.append(kwargs)
            if kwargs.get("previous_response_id") is not None:
                return SimpleNamespace(
                    id="response-2",
                    output=[],
                    output_parsed=diagnosis,
                    output_text="",
                    usage=None,
                )
            return SimpleNamespace(
                id="response-1",
                output=[
                    SimpleNamespace(
                        type="function_call",
                        call_id="call-1",
                        name="analyze_staffing",
                        arguments="{}",
                        parsed_arguments={},
                    )
                ],
                output_parsed=None,
                output_text="Inspect staffing around the incident boundary.",
                usage=None,
            )

    client = OpenAIInvestigatorClient(
        api_key="test-only-placeholder",
        model="gpt-5.6-sol",
        reasoning_effort="medium",
    )
    client._client = SimpleNamespace(responses=FakeResponses())
    prompt = InvestigatorPrompt(
        system="system",
        user="user",
        tools=[
            {
                "type": "function",
                "name": "analyze_staffing",
                "description": "Analyze staffing.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                "strict": True,
            }
        ],
        version="test",
    )

    turn = client.respond(prompt)
    final_turn = client.respond(
        prompt,
        previous_response_id=turn.response_id,
        tool_outputs=[ToolOutput(call_id="call-1", output={"ok": True})],
    )

    assert turn.tool_calls[0].name == "analyze_staffing"
    assert final_turn.diagnosis == diagnosis
    assert captured[0]["model"] == "gpt-5.6-sol"
    assert captured[0]["reasoning"] == {"effort": "medium"}
    assert captured[0]["parallel_tool_calls"] is False
    assert captured[0]["tool_choice"] == "required"
    assert "text_format" not in captured[0]
    assert captured[1]["tool_choice"] == "auto"
    assert captured[1]["text_format"].__name__ == "FinalDiagnosis"
    assert "test-only-placeholder" not in str(captured)
