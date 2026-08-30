from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.contracts import FinalDiagnosis
from incident_investigator.hypotheses import (
    HypothesisLedger,
    HypothesisLedgerUpdate,
    assess_termination,
)
from incident_investigator.hypotheses.models import LEDGER_TOOL_NAME
from incident_investigator.investigator.client import ToolOutput
from incident_investigator.investigator.runner import _sum_usage
from incident_investigator.persistence import RunStore, estimate_gpt_5_6_sol_cost
from incident_investigator.tools import CaseToolbox

from .client import V2InvestigatorClient, V2TurnMode
from .prompting import build_v2_prompt


@dataclass(frozen=True)
class V2RunResult:
    diagnosis: FinalDiagnosis
    tool_call_count: int
    hypothesis_update_count: int
    premature_completion_attempts: int
    termination_reason: str
    duration_seconds: float
    total_usage: dict[str, Any]


class StructuredHypothesisRunner:
    def __init__(
        self,
        loader: AgentVisibleCaseLoader,
        client: V2InvestigatorClient,
        store: RunStore,
        *,
        max_tool_calls: int = 10,
        max_invalid_state_attempts: int = 3,
        max_premature_completion_attempts: int = 3,
    ):
        if not 1 <= max_tool_calls <= 12:
            raise ValueError("max_tool_calls must be between 1 and 12")
        if max_invalid_state_attempts < 1 or max_premature_completion_attempts < 1:
            raise ValueError("V2 retry bounds must be positive")
        self.loader = loader
        self.client = client
        self.store = store
        self.max_tool_calls = max_tool_calls
        self.max_invalid_state_attempts = max_invalid_state_attempts
        self.max_premature_completion_attempts = max_premature_completion_attempts

    def run_case(self, incident_id: str) -> V2RunResult:
        started = perf_counter()
        case = self.loader.load(incident_id)
        toolbox = CaseToolbox(case)
        prompt = build_v2_prompt(case, toolbox, self.store.project_root, self.max_tool_calls)
        ledger = HypothesisLedger()
        step_number = 1
        self.store.append_trajectory(
            incident_id,
            {
                "run_id": self.store.run_id,
                "incident_id": incident_id,
                "system_version": "v2_structured_hypothesis_investigator",
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
                "maximum_operational_tool_calls": self.max_tool_calls,
                "minimum_distinct_supporting_tools_for_completion": 2,
                "information_presentation": "metadata_initially; visible_tables_via_tools",
            },
        )

        total_usage: dict[str, Any] = {}
        tool_call_count = 0
        hypothesis_update_count = 0
        premature_completion_attempts = 0
        invalid_state_attempts = 0
        previous_response_id: str | None = None
        tool_outputs: list[ToolOutput] | None = None
        instruction: str | None = None
        mode: V2TurnMode = "initialize_ledger"
        executed_tools: set[str] = set()

        while True:
            if mode == "force_final" and instruction is None:
                instruction = (
                    "The operational tool-call limit has been reached. Return the best-supported "
                    "final diagnosis now. If the normal completion criteria remain unmet, the "
                    "investigation_status must be INCONCLUSIVE."
                )
            turn = self.client.respond(
                prompt,
                mode=mode,
                previous_response_id=previous_response_id,
                tool_outputs=tool_outputs,
                instruction=instruction,
            )
            total_usage = _sum_usage(total_usage, turn.usage)
            step_number += 1
            tool_outputs = None
            instruction = None

            if turn.diagnosis is not None:
                if mode not in {"investigate", "force_final"}:
                    raise ValueError("V2 investigator diagnosed when a ledger update was required")
                if turn.diagnosis.incident_id != incident_id:
                    raise ValueError(
                        "Diagnosis incident_id "
                        f"{turn.diagnosis.incident_id} does not match {incident_id}"
                    )
                assessment = assess_termination(
                    turn.diagnosis,
                    ledger.snapshot,
                    tool_limit_reached=tool_call_count >= self.max_tool_calls,
                )
                if not assessment.allowed:
                    premature_completion_attempts += 1
                    self.store.append_trajectory(
                        incident_id,
                        {
                            "run_id": self.store.run_id,
                            "incident_id": incident_id,
                            "system_version": "v2_structured_hypothesis_investigator",
                            "agent_stage": "investigator",
                            "event_type": "premature_completion_blocked",
                            "step_number": step_number,
                            "model": self.client.model,
                            "response_id": turn.response_id,
                            "unmet_termination_criteria": assessment.unmet_criteria,
                            "hypothesis_state": (
                                ledger.snapshot.model_dump(mode="json") if ledger.snapshot else None
                            ),
                            "model_usage": turn.usage,
                        },
                    )
                    if mode == "force_final" or (
                        premature_completion_attempts >= self.max_premature_completion_attempts
                    ):
                        raise ValueError(
                            "V2 investigator repeatedly violated termination criteria: "
                            + "; ".join(assessment.unmet_criteria)
                        )
                    previous_response_id = turn.response_id
                    mode = "investigate"
                    instruction = (
                        "Finalization was blocked by the application because these public "
                        "criteria remain unmet: "
                        + "; ".join(assessment.unmet_criteria)
                        + ". Continue the investigation with an available operational tool."
                    )
                    continue

                termination_reason = assessment.reason
                duration = perf_counter() - started
                estimated_cost = estimate_gpt_5_6_sol_cost(total_usage)
                self.store.write_prediction(turn.diagnosis)
                self.store.append_trajectory(
                    incident_id,
                    {
                        "run_id": self.store.run_id,
                        "incident_id": incident_id,
                        "system_version": "v2_structured_hypothesis_investigator",
                        "agent_stage": "investigator",
                        "event_type": "final_output",
                        "step_number": step_number,
                        "model": self.client.model,
                        "response_id": turn.response_id,
                        "model_usage": turn.usage,
                        "total_token_usage": total_usage,
                        "tool_call_count": tool_call_count,
                        "hypothesis_update_count": hypothesis_update_count,
                        "premature_completion_attempts": premature_completion_attempts,
                        "termination_reason": termination_reason,
                        "total_duration_seconds": duration,
                        "estimated_cost_usd": estimated_cost,
                        "final_hypothesis_state": ledger.snapshot.model_dump(mode="json"),
                        "final_diagnosis": turn.diagnosis.model_dump(mode="json"),
                    },
                )
                return V2RunResult(
                    diagnosis=turn.diagnosis,
                    tool_call_count=tool_call_count,
                    hypothesis_update_count=hypothesis_update_count,
                    premature_completion_attempts=premature_completion_attempts,
                    termination_reason=termination_reason,
                    duration_seconds=duration,
                    total_usage=total_usage,
                )

            if not turn.tool_calls:
                raise ValueError("V2 investigator returned neither tool calls nor a diagnosis")

            if mode in {"initialize_ledger", "update_ledger"}:
                if len(turn.tool_calls) != 1 or turn.tool_calls[0].name != LEDGER_TOOL_NAME:
                    raise ValueError("Exactly one hypothesis-ledger update was required")
                call = turn.tool_calls[0]
                before = ledger.snapshot.model_dump(mode="json") if ledger.snapshot else None
                try:
                    update = HypothesisLedgerUpdate.model_validate(call.arguments)
                    changes = ledger.apply(update, executed_tools=executed_tools)
                    output = {
                        "ok": True,
                        "message": (
                            "Hypothesis ledger accepted. Select the next discriminating "
                            "operational tool or finalize only if every criterion is met."
                        ),
                    }
                    invalid_state_attempts = 0
                    hypothesis_update_count += 1
                    event_type = "hypothesis_update"
                    event_payload: dict[str, Any] = {
                        "decision_summary": update.decision_summary,
                        "hypothesis_state_before": before,
                        "hypothesis_state_after": ledger.snapshot.model_dump(mode="json"),
                        "hypothesis_changes": [item.model_dump(mode="json") for item in changes],
                    }
                except (ValueError, ValidationError) as exc:
                    invalid_state_attempts += 1
                    output = {
                        "ok": False,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                    event_type = "hypothesis_update_rejected"
                    event_payload = {
                        "decision_summary": turn.decision_summary,
                        "hypothesis_state_before": before,
                        "hypothesis_state_after": before,
                        "proposed_hypothesis_update": call.arguments,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }

                self.store.append_trajectory(
                    incident_id,
                    {
                        "run_id": self.store.run_id,
                        "incident_id": incident_id,
                        "system_version": "v2_structured_hypothesis_investigator",
                        "agent_stage": "hypothesis_ledger",
                        "event_type": event_type,
                        "step_number": step_number,
                        "model": self.client.model,
                        "response_id": turn.response_id,
                        "model_usage": turn.usage,
                        **event_payload,
                    },
                )
                if not output["ok"] and (invalid_state_attempts >= self.max_invalid_state_attempts):
                    raise ValueError("V2 investigator repeatedly returned invalid hypothesis state")
                previous_response_id = turn.response_id
                tool_outputs = [ToolOutput(call_id=call.call_id, output=output)]
                if output["ok"]:
                    mode = (
                        "force_final" if tool_call_count >= self.max_tool_calls else "investigate"
                    )
                else:
                    mode = "update_ledger"
                continue

            if mode == "force_final":
                raise ValueError("V2 investigator requested tools after the tool-call limit")

            decision_summary = turn.decision_summary or (
                "Selected deterministic operational analysis tool(s): "
                + ", ".join(call.name for call in turn.tool_calls)
            )
            self.store.append_trajectory(
                incident_id,
                {
                    "run_id": self.store.run_id,
                    "incident_id": incident_id,
                    "system_version": "v2_structured_hypothesis_investigator",
                    "agent_stage": "investigator",
                    "event_type": "model_decision",
                    "step_number": step_number,
                    "model": self.client.model,
                    "response_id": turn.response_id,
                    "decision_summary": decision_summary[:1000],
                    "requested_tools": [call.name for call in turn.tool_calls],
                    "hypothesis_state": (
                        ledger.snapshot.model_dump(mode="json") if ledger.snapshot else None
                    ),
                    "model_usage": turn.usage,
                },
            )

            outputs: list[ToolOutput] = []
            for call in turn.tool_calls:
                if tool_call_count >= self.max_tool_calls:
                    outputs.append(
                        ToolOutput(
                            call_id=call.call_id,
                            output={"ok": False, "error": "tool_call_limit_reached"},
                        )
                    )
                    continue
                tool_started = perf_counter()
                try:
                    result = toolbox.execute(call.name, call.arguments)
                    output = {"ok": True, "result": result}
                    executed_tools.add(call.name)
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
                        "system_version": "v2_structured_hypothesis_investigator",
                        "agent_stage": "investigator",
                        "event_type": "tool_result",
                        "step_number": step_number,
                        "model": self.client.model,
                        "tool_called": call.name,
                        "tool_arguments": call.arguments,
                        "tool_result": output,
                        "hypothesis_state_before_update": (
                            ledger.snapshot.model_dump(mode="json") if ledger.snapshot else None
                        ),
                        "tool_duration_seconds": tool_duration,
                    },
                )
                outputs.append(ToolOutput(call_id=call.call_id, output=output))

            previous_response_id = turn.response_id
            tool_outputs = outputs
            mode = "update_ledger"
