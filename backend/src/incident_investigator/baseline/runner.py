from __future__ import annotations

from time import perf_counter

from incident_investigator.benchmark.loader import AgentVisibleCaseLoader
from incident_investigator.contracts import FinalDiagnosis
from incident_investigator.persistence import RunStore

from .client import BaselineClient
from .prompting import build_baseline_prompt


class BaselineRunner:
    def __init__(self, loader: AgentVisibleCaseLoader, client: BaselineClient, store: RunStore):
        self.loader = loader
        self.client = client
        self.store = store

    def run_case(self, incident_id: str) -> FinalDiagnosis:
        case = self.loader.load(incident_id)
        prompt = build_baseline_prompt(case, self.store.project_root)
        self.store.append_trajectory(
            incident_id,
            {
                "step_number": 1,
                "agent_stage": "baseline",
                "event_type": "model_request",
                "model": self.client.model,
                "prompt_version": prompt.version,
                "prompt_sha256": prompt.sha256,
            },
        )
        started = perf_counter()
        response = self.client.analyze(prompt)
        duration = perf_counter() - started
        if response.diagnosis.incident_id != incident_id:
            raise ValueError(
                "Diagnosis incident_id "
                f"{response.diagnosis.incident_id} does not match {incident_id}"
            )
        self.store.write_prediction(response.diagnosis)
        self.store.append_trajectory(
            incident_id,
            {
                "step_number": 2,
                "agent_stage": "baseline",
                "event_type": "final_output",
                "model": self.client.model,
                "duration_seconds": duration,
                "token_usage": response.usage,
                "response_id": response.response_id,
                "final_output": response.diagnosis.model_dump(mode="json"),
            },
        )
        return response.diagnosis
