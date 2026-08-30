from __future__ import annotations

import json
import shutil
from pathlib import Path

from helpers import diagnosis_from_truth

from incident_investigator.config import get_settings
from incident_investigator.evaluation import (
    STAGE0_ANCHOR_RUN_ID,
    V1_RUN_ID,
    GroundTruthLoader,
)
from incident_investigator.investigator import InvestigatorTurn, RequestedToolCall
from incident_investigator.structured_investigator import V2Prompt
from incident_investigator.structured_investigator.batch import run_v2_batch


class MappingV2Client:
    model = "gpt-5.6-sol"
    reasoning_effort = "medium"

    def __init__(self, diagnoses: dict[str, object]):
        self.diagnoses = diagnoses
        self.turns: dict[str, int] = {}

    @staticmethod
    def _ledger_call(
        incident_id: str,
        diagnosis: object,
        *,
        state: str,
    ) -> RequestedToolCall:
        primary = diagnosis.primary_root_cause_category.value
        alternatives = [
            item
            for item in ["DEMAND_SPIKE", "STAFFING_SHORTFALL", "HANDLE_TIME_INCREASE"]
            if item != primary
        ][:2]
        while len(alternatives) < 2:
            alternatives.append("DATA_QUALITY")
        initial = state == "initial"
        ready = state == "ready"
        first_signal = diagnosis.evidence[0].signal.value
        second_signal = (
            diagnosis.evidence[1].signal.value
            if len(diagnosis.evidence) > 1
            else "service_level_decline"
        )
        leader_evidence = []
        if not initial:
            leader_evidence.append(
                {
                    "signal": first_signal,
                    "source_tool": "get_performance_trends",
                    "finding": f"Observed {first_signal}.",
                }
            )
        if ready:
            leader_evidence.append(
                {
                    "signal": second_signal,
                    "source_tool": "compare_actual_vs_forecast",
                    "finding": f"Observed {second_signal}.",
                }
            )
        hypotheses = [
            {
                "category": primary,
                "status": "LIKELY" if ready else "POSSIBLE",
                "confidence": 0.85 if ready else 0.45,
                "evidence_for": leader_evidence,
                "evidence_against": [],
            }
        ]
        for index, category in enumerate(alternatives):
            hypotheses.append(
                {
                    "category": category,
                    "status": "UNLIKELY" if ready else "UNTESTED",
                    "confidence": 0.1 - index * 0.02 if ready else 0.25,
                    "evidence_for": [],
                    "evidence_against": (
                        [
                            {
                                "signal": first_signal,
                                "source_tool": "get_performance_trends",
                                "finding": "Observed pattern favors the leading alternative.",
                            }
                        ]
                        if ready
                        else []
                    ),
                }
            )
        return RequestedToolCall(
            call_id=f"ledger-{incident_id}-{state}",
            name="record_hypothesis_ledger",
            arguments={
                "decision_summary": f"Record {state} hypotheses.",
                "ledger": {
                    "hypotheses": hypotheses,
                    "leading_hypothesis": primary if ready else None,
                    "causal_timing_supported": ready,
                    "unresolved_critical_contradictions": [],
                    "investigation_summary": f"{state.title()} hypothesis state.",
                },
            },
        )

    def respond(self, prompt: V2Prompt, *, mode: str, **kwargs: object) -> InvestigatorTurn:
        payload = json.loads(prompt.user)
        metadata = payload.get("incident_metadata") or payload["incident"]["incident_metadata"]
        incident_id = metadata["incident_id"]
        self.turns[incident_id] = self.turns.get(incident_id, 0) + 1
        turn = self.turns[incident_id]
        diagnosis = self.diagnoses[incident_id]
        if turn == 1:
            call = self._ledger_call(incident_id, diagnosis, state="initial")
        elif turn == 2:
            call = RequestedToolCall(f"performance-{incident_id}", "get_performance_trends", {})
        elif turn == 3:
            call = self._ledger_call(incident_id, diagnosis, state="partial")
        elif turn == 4:
            call = RequestedToolCall(f"forecast-{incident_id}", "compare_actual_vs_forecast", {})
        elif turn == 5:
            call = self._ledger_call(incident_id, diagnosis, state="ready")
        else:
            return InvestigatorTurn(response_id=f"final-{incident_id}", diagnosis=diagnosis)
        return InvestigatorTurn(response_id=f"turn-{incident_id}-{turn}", tool_calls=[call])


def test_v2_batch_scores_and_compares_against_stage0_and_v1(
    isolated_project: Path,
    project_root: Path,
) -> None:
    for run_id in [STAGE0_ANCHOR_RUN_ID, V1_RUN_ID]:
        shutil.copytree(
            project_root / "results" / "curated" / run_id,
            isolated_project / "results" / "curated" / run_id,
        )
        shutil.copytree(
            project_root / "trajectories" / "curated" / run_id,
            isolated_project / "trajectories" / "curated" / run_id,
        )
    truths = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load_all()
    client = MappingV2Client({truth.incident_id: diagnosis_from_truth(truth) for truth in truths})

    run_id, scores, comparisons = run_v2_batch(get_settings(isolated_project), client)

    assert scores["rcia"] == 1.0
    assert comparisons["stage0"]["anchor_run_id"] == STAGE0_ANCHOR_RUN_ID
    assert comparisons["v1"]["anchor_run_id"] == V1_RUN_ID
    assert comparisons["v1"]["cases_regressed"] == []
    result_root = isolated_project / "results" / "local" / run_id
    for stem in ["comparison_to_stage0", "comparison_to_v1"]:
        assert (result_root / f"{stem}.json").is_file()
        assert (result_root / f"{stem}.csv").is_file()
        assert (result_root / f"{stem}.md").is_file()
    manifest = json.loads((result_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["system_version"] == "v2_structured_hypothesis_investigator"
    assert manifest["failure_count"] == 0
    assert manifest["maximum_tool_calls_per_case"] == 10
    assert manifest["aggregate_tool_calls"] == 20
    assert manifest["aggregate_hypothesis_updates"] == 30
