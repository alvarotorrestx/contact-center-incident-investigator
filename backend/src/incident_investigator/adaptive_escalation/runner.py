from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from incident_investigator.baseline import BaselineClient, build_baseline_prompt
from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.contracts import FinalDiagnosis, VisibleCase
from incident_investigator.investigator.runner import _sum_usage
from incident_investigator.persistence import RunStore, estimate_gpt_5_6_sol_cost
from incident_investigator.structured_investigator import (
    StructuredHypothesisRunner,
    V2InvestigatorClient,
)
from incident_investigator.structured_investigator.prompting import V2Prompt
from incident_investigator.tools import CaseToolbox

from .gate import EscalationDecision, evaluate_escalation
from .prompting import build_adaptive_investigation_prompt

SYSTEM_VERSION = "adaptive_escalation"
INFORMATION_PRESENTATION = (
    "all_visible_tables_initially; baseline_first_pass; selective_v2_deep_investigation"
)


@dataclass(frozen=True)
class AdaptiveRunResult:
    first_pass_diagnosis: FinalDiagnosis
    diagnosis: FinalDiagnosis
    escalation: EscalationDecision
    tool_call_count: int
    hypothesis_update_count: int
    premature_completion_attempts: int
    termination_reason: str
    duration_seconds: float
    total_usage: dict[str, Any]

    @property
    def diagnosis_changed(self) -> bool:
        return self.first_pass_diagnosis != self.diagnosis

    @property
    def category_changed(self) -> bool:
        return (
            self.first_pass_diagnosis.primary_root_cause_category
            != self.diagnosis.primary_root_cause_category
        )


class AdaptiveEscalationRunner:
    def __init__(
        self,
        loader: AgentVisibleCaseLoader,
        first_pass_client: BaselineClient,
        deep_client: V2InvestigatorClient,
        store: RunStore,
        *,
        max_tool_calls: int = 10,
        gate: Callable[[VisibleCase, FinalDiagnosis], EscalationDecision] = evaluate_escalation,
    ):
        if first_pass_client.model != deep_client.model:
            raise ValueError("Adaptive first-pass and deep clients must use the same model")
        self.loader = loader
        self.first_pass_client = first_pass_client
        self.deep_client = deep_client
        self.store = store
        self.max_tool_calls = max_tool_calls
        self.gate = gate

    def _append_final(
        self,
        incident_id: str,
        *,
        result: FinalDiagnosis,
        first_pass: FinalDiagnosis,
        escalation: EscalationDecision,
        usage: dict[str, Any],
        duration_seconds: float,
        tool_call_count: int,
        hypothesis_update_count: int,
        premature_completion_attempts: int,
        termination_reason: str,
    ) -> None:
        self.store.append_trajectory(
            incident_id,
            {
                "run_id": self.store.run_id,
                "incident_id": incident_id,
                "system_version": SYSTEM_VERSION,
                "agent_stage": "adaptive_finalization",
                "event_type": "final_output",
                "step_number": self.store.next_trajectory_step(incident_id),
                "model": self.first_pass_client.model,
                "escalated": escalation.escalate,
                "escalation_triggers": list(escalation.triggers),
                "first_pass_diagnosis_changed": first_pass != result,
                "first_pass_category_changed": (
                    first_pass.primary_root_cause_category != result.primary_root_cause_category
                ),
                "first_pass_category": first_pass.primary_root_cause_category.value,
                "final_category": result.primary_root_cause_category.value,
                "tool_call_count": tool_call_count,
                "hypothesis_update_count": hypothesis_update_count,
                "premature_completion_attempts": premature_completion_attempts,
                "verifier_call_count": 0,
                "revision_count": 0,
                "termination_reason": termination_reason,
                "total_duration_seconds": duration_seconds,
                "total_token_usage": usage,
                "estimated_cost_usd": estimate_gpt_5_6_sol_cost(usage),
                "final_diagnosis": result.model_dump(mode="json"),
            },
        )

    def run_case(self, incident_id: str) -> AdaptiveRunResult:
        started = perf_counter()
        case = self.loader.load(incident_id)
        first_pass_prompt = build_baseline_prompt(case, self.store.project_root)
        self.store.append_trajectory(
            incident_id,
            {
                "run_id": self.store.run_id,
                "incident_id": incident_id,
                "system_version": SYSTEM_VERSION,
                "agent_stage": "first_pass",
                "event_type": "model_request",
                "step_number": 1,
                "model": self.first_pass_client.model,
                "prompt_version": first_pass_prompt.version,
                "prompt_sha256": first_pass_prompt.sha256,
                "information_presentation": "all_visible_tables_in_initial_prompt",
            },
        )
        first_started = perf_counter()
        first_response = self.first_pass_client.analyze(first_pass_prompt)
        first_duration = perf_counter() - first_started
        first_pass = first_response.diagnosis
        if first_pass.incident_id != incident_id:
            raise ValueError(
                f"Diagnosis incident_id {first_pass.incident_id} does not match {incident_id}"
            )
        self.store.write_json(
            self.store.result_root / "first_pass_predictions" / f"{incident_id}.json",
            first_pass.model_dump(mode="json"),
        )
        self.store.append_trajectory(
            incident_id,
            {
                "run_id": self.store.run_id,
                "incident_id": incident_id,
                "system_version": SYSTEM_VERSION,
                "agent_stage": "first_pass",
                "event_type": "first_pass_output",
                "step_number": 2,
                "model": self.first_pass_client.model,
                "response_id": first_response.response_id,
                "duration_seconds": first_duration,
                "token_usage": first_response.usage,
                "diagnosis": first_pass.model_dump(mode="json"),
            },
        )

        escalation = self.gate(case, first_pass)
        self.store.append_trajectory(
            incident_id,
            {
                "run_id": self.store.run_id,
                "incident_id": incident_id,
                "system_version": SYSTEM_VERSION,
                "agent_stage": "escalation_gate",
                "event_type": "escalation_decision",
                "step_number": 3,
                **escalation.to_dict(),
            },
        )

        if not escalation.escalate:
            duration = perf_counter() - started
            self.store.write_prediction(first_pass)
            termination_reason = "first_pass_finalized"
            self._append_final(
                incident_id,
                result=first_pass,
                first_pass=first_pass,
                escalation=escalation,
                usage=first_response.usage,
                duration_seconds=duration,
                tool_call_count=0,
                hypothesis_update_count=0,
                premature_completion_attempts=0,
                termination_reason=termination_reason,
            )
            return AdaptiveRunResult(
                first_pass_diagnosis=first_pass,
                diagnosis=first_pass,
                escalation=escalation,
                tool_call_count=0,
                hypothesis_update_count=0,
                premature_completion_attempts=0,
                termination_reason=termination_reason,
                duration_seconds=duration,
                total_usage=first_response.usage,
            )

        def prompt_builder(
            prompt_case: VisibleCase,
            toolbox: CaseToolbox,
            project_root: Any,
            max_tool_calls: int,
        ) -> V2Prompt:
            return build_adaptive_investigation_prompt(
                prompt_case,
                first_pass,
                toolbox,
                project_root,
                max_tool_calls,
            )

        deep_runner = StructuredHypothesisRunner(
            self.loader,
            self.deep_client,
            self.store,
            max_tool_calls=self.max_tool_calls,
            system_version=SYSTEM_VERSION,
            prompt_builder=prompt_builder,
            information_presentation=INFORMATION_PRESENTATION,
            trajectory_step_offset=3,
        )
        deep_result = deep_runner.run_case(incident_id)
        duration = perf_counter() - started
        usage = _sum_usage(first_response.usage, deep_result.total_usage)
        termination_reason = f"escalated:{deep_result.termination_reason}"
        self._append_final(
            incident_id,
            result=deep_result.diagnosis,
            first_pass=first_pass,
            escalation=escalation,
            usage=usage,
            duration_seconds=duration,
            tool_call_count=deep_result.tool_call_count,
            hypothesis_update_count=deep_result.hypothesis_update_count,
            premature_completion_attempts=deep_result.premature_completion_attempts,
            termination_reason=termination_reason,
        )
        return AdaptiveRunResult(
            first_pass_diagnosis=first_pass,
            diagnosis=deep_result.diagnosis,
            escalation=escalation,
            tool_call_count=deep_result.tool_call_count,
            hypothesis_update_count=deep_result.hypothesis_update_count,
            premature_completion_attempts=deep_result.premature_completion_attempts,
            termination_reason=termination_reason,
            duration_seconds=duration,
            total_usage=usage,
        )
