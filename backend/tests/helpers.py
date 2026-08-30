from __future__ import annotations

import json

from incident_investigator.baseline import BaselineResponse
from incident_investigator.contracts import FinalDiagnosis


class MockBaselineClient:
    model = "mock-baseline-model"

    def __init__(self, diagnosis: FinalDiagnosis):
        self.diagnosis = diagnosis

    def analyze(self, prompt: object) -> BaselineResponse:
        return BaselineResponse(
            diagnosis=self.diagnosis,
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            response_id="mock-response",
        )


class MappingMockBaselineClient:
    model = "mock-baseline-model"

    def __init__(self, diagnoses: dict[str, FinalDiagnosis]):
        self.diagnoses = diagnoses

    def analyze(self, prompt: object) -> BaselineResponse:
        payload = json.loads(prompt.user)
        incident_id = payload["incident"]["incident_metadata"]["incident_id"]
        return BaselineResponse(
            diagnosis=self.diagnoses[incident_id],
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            response_id=f"mock-{incident_id}",
        )


def diagnosis_from_truth(truth: object) -> FinalDiagnosis:
    return FinalDiagnosis.model_validate(
        {
            "incident_id": truth.incident_id,
            "investigation_status": "CONFIRMED",
            "primary_root_cause_category": truth.primary_root_cause.category,
            "primary_root_cause_detail": truth.primary_root_cause.detail,
            "contributing_factors": truth.contributing_factors,
            "confidence": 0.9,
            "evidence": [
                {"signal": signal, "source": "performance", "finding": f"Observed {signal}."}
                for signal in truth.expected_evidence
            ],
            "rejected_hypotheses": [],
            "causal_chain": truth.expected_causal_chain,
            "recommended_actions": ["Review the affected operating condition."],
            "stakeholder_summary": "A deterministic fixture diagnosis.",
        }
    )
