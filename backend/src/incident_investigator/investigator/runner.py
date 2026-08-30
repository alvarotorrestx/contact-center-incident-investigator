from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.contracts import FinalDiagnosis
from incident_investigator.persistence import RunStore, estimate_gpt_5_6_sol_cost
from incident_investigator.tools import CaseToolbox

from .client import InvestigatorClient, ToolOutput
from .prompting import build_investigator_prompt


@dataclass(frozen=True)
class InvestigatorRunResult:
    diagnosis: FinalDiagnosis
    tool_call_count: int
    termination_reason: str
    duration_seconds: float
    total_usage: dict[str, Any]


def _sum_usage(total: dict[str, Any], addition: dict[str, Any]) -> dict[str, Any]:
    merged = dict(total)
    for key, value in addition.items():
        if isinstance(value, dict):
            merged[key] = _sum_usage(
                merged.get(key, {}) if isinstance(merged.get(key), dict) else {}, value
            )
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            merged[key] = merged.get(key, 0) + value
    return merged


class ToolInvestigatorRunner:
    def __init__(
        self,
        loader: AgentVisibleCaseLoader,
        client: InvestigatorClient,
        store: RunStore,
        *,
        max_tool_calls: int = 10,
    ):
        if not 1 <= max_tool_calls <= 12:
            raise ValueError("max_tool_calls must be between 1 and 12")
        self.loader = loader
        self.client = client
        self.store = store
        self.max_tool_calls = max_tool_calls

    def run_case(self, incident_id: str) -> InvestigatorRunResult:
        started = perf_counter()
        case = self.loader.load(incident_id)
        toolbox = CaseToolbox(case)
        prompt = build_investigator_prompt(
            case, toolbox, self.store.project_root, self.max_tool_calls
        )
        step_number = 1
        self.store.append_trajectory(
            incident_id,
            {
                "run_id": self.store.run_id,
                "incident_id": incident_id,
                "system_version": "v1_tool_investigator",
                "agent_stage": "investigator",
                "event_type": "investigation_started",
                "step_number": step_number,
                "model": self.client.model,
                "model_configuration": {
                    "reasoning_effort": self.client.reasoning_effort,
                    "sampling_parameters": "provider_defaults",
                },
                "prompt_version": prompt.version,
                "prompt_sha256": prompt.sha256,
                "maximum_tool_calls": self.max_tool_calls,
                "information_presentation": "metadata_initially; visible_tables_via_tools",
            },
        )

        total_usage: dict[str, Any] = {}
        tool_call_count = 0
        previous_response_id: str | None = None
        tool_outputs: list[ToolOutput] | None = None
        force_final = False

        while True:
            turn = self.client.respond(
                prompt,
                previous_response_id=previous_response_id,
                tool_outputs=tool_outputs,
                allow_tools=not force_final,
            )
            total_usage = _sum_usage(total_usage, turn.usage)
            step_number += 1

            if turn.diagnosis is not None:
                if tool_call_count == 0:
                    raise ValueError(
                        "V1 investigator finalized before the required initial tool call"
                    )
                if turn.diagnosis.incident_id != incident_id:
                    raise ValueError(
                        "Diagnosis incident_id "
                        f"{turn.diagnosis.incident_id} does not match {incident_id}"
                    )
                termination_reason = "tool_limit_reached" if force_final else "diagnosis_complete"
                duration = perf_counter() - started
                estimated_cost = estimate_gpt_5_6_sol_cost(total_usage)
                self.store.write_prediction(turn.diagnosis)
                self.store.append_trajectory(
                    incident_id,
                    {
                        "run_id": self.store.run_id,
                        "incident_id": incident_id,
                        "system_version": "v1_tool_investigator",
                        "agent_stage": "investigator",
                        "event_type": "final_output",
                        "step_number": step_number,
                        "model": self.client.model,
                        "response_id": turn.response_id,
                        "model_usage": turn.usage,
                        "total_token_usage": total_usage,
                        "tool_call_count": tool_call_count,
                        "termination_reason": termination_reason,
                        "total_duration_seconds": duration,
                        "estimated_cost_usd": estimated_cost,
                        "final_diagnosis": turn.diagnosis.model_dump(mode="json"),
                    },
                )
                return InvestigatorRunResult(
                    diagnosis=turn.diagnosis,
                    tool_call_count=tool_call_count,
                    termination_reason=termination_reason,
                    duration_seconds=duration,
                    total_usage=total_usage,
                )

            if not turn.tool_calls:
                raise ValueError("Investigator returned neither tool calls nor a diagnosis")

            decision_summary = turn.decision_summary or (
                "Selected deterministic operational analysis tool(s): "
                + ", ".join(call.name for call in turn.tool_calls)
            )
            self.store.append_trajectory(
                incident_id,
                {
                    "run_id": self.store.run_id,
                    "incident_id": incident_id,
                    "system_version": "v1_tool_investigator",
                    "agent_stage": "investigator",
                    "event_type": "model_decision",
                    "step_number": step_number,
                    "model": self.client.model,
                    "response_id": turn.response_id,
                    "decision_summary": decision_summary[:1000],
                    "requested_tools": [call.name for call in turn.tool_calls],
                    "model_usage": turn.usage,
                },
            )

            outputs: list[ToolOutput] = []
            for call in turn.tool_calls:
                if tool_call_count >= self.max_tool_calls:
                    outputs.append(
                        ToolOutput(
                            call_id=call.call_id,
                            output={"error": "tool_call_limit_reached"},
                        )
                    )
                    continue
                tool_started = perf_counter()
                try:
                    result = toolbox.execute(call.name, call.arguments)
                    output = {"ok": True, "result": result}
                except (ValueError, ValidationError) as exc:
                    output = {
                        "ok": False,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                tool_duration = perf_counter() - tool_started
                tool_call_count += 1
                step_number += 1
                self.store.append_trajectory(
                    incident_id,
                    {
                        "run_id": self.store.run_id,
                        "incident_id": incident_id,
                        "system_version": "v1_tool_investigator",
                        "agent_stage": "investigator",
                        "event_type": "tool_result",
                        "step_number": step_number,
                        "model": self.client.model,
                        "tool_called": call.name,
                        "tool_arguments": call.arguments,
                        "tool_result": output,
                        "tool_duration_seconds": tool_duration,
                    },
                )
                outputs.append(ToolOutput(call_id=call.call_id, output=output))

            previous_response_id = turn.response_id
            tool_outputs = outputs
            force_final = tool_call_count >= self.max_tool_calls
