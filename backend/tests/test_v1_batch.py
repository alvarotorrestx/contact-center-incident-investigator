from __future__ import annotations

import json
import shutil
from pathlib import Path

from helpers import diagnosis_from_truth

from incident_investigator.config import get_settings
from incident_investigator.evaluation import STAGE0_ANCHOR_RUN_ID, GroundTruthLoader
from incident_investigator.investigator import (
    InvestigatorPrompt,
    InvestigatorTurn,
    RequestedToolCall,
)
from incident_investigator.investigator.batch import run_v1_batch


class MappingImmediateInvestigatorClient:
    model = "gpt-5.6-sol"
    reasoning_effort = "medium"

    def __init__(self, diagnoses: dict[str, object]):
        self.diagnoses = diagnoses
        self.started: set[str] = set()

    def respond(
        self,
        prompt: InvestigatorPrompt,
        *,
        previous_response_id: str | None = None,
        tool_outputs: list[object] | None = None,
        allow_tools: bool = True,
    ) -> InvestigatorTurn:
        incident_id = json.loads(prompt.user)["incident_metadata"]["incident_id"]
        if incident_id not in self.started:
            self.started.add(incident_id)
            return InvestigatorTurn(
                response_id=f"tool-{incident_id}",
                tool_calls=[
                    RequestedToolCall(
                        call_id=f"call-{incident_id}",
                        name="summarize_incident_window",
                        arguments={},
                    )
                ],
                usage={"input_tokens": 50, "output_tokens": 10, "total_tokens": 60},
            )
        return InvestigatorTurn(
            response_id=f"mock-{incident_id}",
            diagnosis=self.diagnoses[incident_id],
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )


def test_v1_batch_scores_and_compares_against_pinned_anchor(
    isolated_project: Path,
    project_root: Path,
) -> None:
    shutil.copytree(
        project_root / "results" / "curated" / STAGE0_ANCHOR_RUN_ID,
        isolated_project / "results" / "curated" / STAGE0_ANCHOR_RUN_ID,
    )
    shutil.copytree(
        project_root / "trajectories" / "curated" / STAGE0_ANCHOR_RUN_ID,
        isolated_project / "trajectories" / "curated" / STAGE0_ANCHOR_RUN_ID,
    )
    truths = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load_all()
    client = MappingImmediateInvestigatorClient(
        {truth.incident_id: diagnosis_from_truth(truth) for truth in truths}
    )

    run_id, scores, comparison = run_v1_batch(get_settings(isolated_project), client)

    assert scores["rcia"] == 1.0
    assert comparison["anchor_run_id"] == STAGE0_ANCHOR_RUN_ID
    assert comparison["candidate_run_id"] == run_id
    assert comparison["cases_improved"] == ["CC-005"]
    assert comparison["cases_regressed"] == []
    result_root = isolated_project / "results" / "local" / run_id
    assert (result_root / "comparison_to_anchor.json").is_file()
    assert (result_root / "comparison_to_anchor.csv").is_file()
    assert (result_root / "comparison_to_anchor.md").is_file()
    manifest = json.loads((result_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["system_version"] == "v1_tool_investigator"
    assert manifest["failure_count"] == 0
    assert manifest["maximum_tool_calls_per_case"] == 10
    assert manifest["minimum_tool_calls_per_case"] == 1
