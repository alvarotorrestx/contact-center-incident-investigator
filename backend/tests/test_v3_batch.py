from __future__ import annotations

import json
import shutil
from pathlib import Path

from helpers import diagnosis_from_truth
from test_v2_batch import MappingV2Client

from incident_investigator.config import get_settings
from incident_investigator.evaluation import (
    STAGE0_ANCHOR_RUN_ID,
    V1_RUN_ID,
    V2_RUN_ID,
    GroundTruthLoader,
)
from incident_investigator.verifier import (
    VerificationResult,
    VerificationStatus,
    VerifierPrompt,
    VerifierResponse,
)
from incident_investigator.verifier.batch import run_v3_batch


class AlwaysVerifiedClient:
    model = "gpt-5.6-sol"
    reasoning_effort = "medium"

    def __init__(self) -> None:
        self.call_count = 0

    def verify(self, prompt: VerifierPrompt) -> VerifierResponse:
        self.call_count += 1
        return VerifierResponse(
            result=VerificationResult(
                verification_status=VerificationStatus.VERIFIED,
                critical_contradictions=[],
                unsupported_or_weak_claims=[],
                stronger_alternative_if_any=None,
                recommended_revision=None,
                verification_summary="The visible evidence supports the proposal.",
            ),
            response_id=f"verified-{self.call_count}",
            usage={},
        )


def test_v3_batch_scores_and_compares_against_all_preserved_phases(
    isolated_project: Path,
    project_root: Path,
) -> None:
    for run_id in [STAGE0_ANCHOR_RUN_ID, V1_RUN_ID, V2_RUN_ID]:
        shutil.copytree(
            project_root / "results" / "curated" / run_id,
            isolated_project / "results" / "curated" / run_id,
        )
        shutil.copytree(
            project_root / "trajectories" / "curated" / run_id,
            isolated_project / "trajectories" / "curated" / run_id,
        )
    truths = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load_all()
    investigator = MappingV2Client(
        {truth.incident_id: diagnosis_from_truth(truth) for truth in truths}
    )
    verifier = AlwaysVerifiedClient()

    run_id, scores, comparisons, analysis = run_v3_batch(
        get_settings(isolated_project), investigator, verifier
    )

    assert scores["rcia"] == 1.0
    assert comparisons["stage0"]["anchor_run_id"] == STAGE0_ANCHOR_RUN_ID
    assert comparisons["v1"]["anchor_run_id"] == V1_RUN_ID
    assert comparisons["v2"]["anchor_run_id"] == V2_RUN_ID
    assert comparisons["v2"]["cases_regressed"] == []
    assert analysis["v2_run_id"] == V2_RUN_ID
    assert len(analysis["verified_correct_without_revision"]) == 10
    assert verifier.call_count == 10

    result_root = isolated_project / "results" / "local" / run_id
    for stem in ["comparison_to_stage0", "comparison_to_v1", "comparison_to_v2"]:
        assert (result_root / f"{stem}.json").is_file()
        assert (result_root / f"{stem}.csv").is_file()
        assert (result_root / f"{stem}.md").is_file()
    assert (result_root / "verification_analysis.json").is_file()
    assert (result_root / "verification_analysis.md").is_file()
    manifest = json.loads((result_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["system_version"] == "v3_adversarial_verification"
    assert manifest["failure_count"] == 0
    assert manifest["maximum_verifier_driven_revisions_per_case"] == 2
    assert manifest["aggregate_verifier_calls"] == 10
    assert manifest["aggregate_revisions"] == 0
