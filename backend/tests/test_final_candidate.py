from __future__ import annotations

import json
import shutil
from pathlib import Path

from helpers import diagnosis_from_truth
from test_v2_batch import MappingV2Client

from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.config import get_settings
from incident_investigator.contracts import FinalDiagnosis
from incident_investigator.evaluation import (
    STAGE0_ANCHOR_RUN_ID,
    V1_RUN_ID,
    V2_RUN_ID,
    V3_RUN_ID,
    GroundTruthLoader,
)
from incident_investigator.final_candidate import build_final_candidate_prompt
from incident_investigator.final_candidate.batch import run_final_candidate_batch
from incident_investigator.tools import CaseToolbox


def test_final_candidate_prompt_contains_complete_visible_case_and_v2_contracts(
    isolated_project: Path,
) -> None:
    loader = AgentVisibleCaseLoader(isolated_project / "benchmark" / "v1" / "cases")
    case = loader.load("CC-001")
    prompt = build_final_candidate_prompt(
        case,
        CaseToolbox(case),
        isolated_project,
        10,
    )
    payload = json.loads(prompt.user)

    assert payload["experiment"] == "final_candidate"
    assert payload["incident"] == case.model_dump(mode="json")
    assert set(payload["incident"]) == {
        "incident_metadata",
        "performance",
        "staffing",
        "forecast",
        "queue_performance",
        "events",
    }
    assert payload["required_output_schema"] == FinalDiagnosis.model_json_schema(
        mode="serialization"
    )
    assert payload["hypothesis_ledger_schema"]
    assert len(prompt.operational_tools) == 9
    assert prompt.ledger_tool["name"] == "record_hypothesis_ledger"
    assert prompt.version == "final_candidate_full_context_1"
    assert "verifier" not in payload


def test_final_candidate_batch_preserves_v2_discipline_without_verifier(
    isolated_project: Path,
    project_root: Path,
) -> None:
    anchor_ids = [STAGE0_ANCHOR_RUN_ID, V1_RUN_ID, V2_RUN_ID, V3_RUN_ID]
    for run_id in anchor_ids:
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

    run_id, scores, comparisons = run_final_candidate_batch(get_settings(isolated_project), client)

    assert scores["rcia"] == 1.0
    assert set(comparisons) == {"stage0", "v1", "v2", "v3"}
    assert comparisons["stage0"]["anchor_run_id"] == STAGE0_ANCHOR_RUN_ID
    assert comparisons["v1"]["anchor_run_id"] == V1_RUN_ID
    assert comparisons["v2"]["anchor_run_id"] == V2_RUN_ID
    assert comparisons["v3"]["anchor_run_id"] == V3_RUN_ID
    assert comparisons["stage0"]["information_presentation"]["candidate"] == (
        "all_visible_tables_initially; deterministic_tools_for_analysis"
    )

    result_root = isolated_project / "results" / "local" / run_id
    trajectory_root = isolated_project / "trajectories" / "local" / run_id
    manifest = json.loads((result_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["system_version"] == "final_candidate"
    assert manifest["failure_count"] == 0
    assert manifest["verifier_enabled"] is False
    assert manifest["aggregate_verifier_calls"] == 0
    assert manifest["aggregate_revisions"] == 0
    assert manifest["aggregate_tool_calls"] == 20
    assert manifest["aggregate_hypothesis_updates"] == 30
    for key in ["stage0", "v1", "v2", "v3"]:
        for suffix in ["json", "csv", "md"]:
            assert (result_root / f"comparison_to_{key}.{suffix}").is_file()

    for path in sorted(trajectory_root.glob("CC-*.jsonl")):
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert events[0]["information_presentation"] == (
            "all_visible_tables_initially; deterministic_tools_for_analysis"
        )
        assert events[-1]["event_type"] == "final_output"
        assert events[-1]["verifier_call_count"] == 0
        assert events[-1]["revision_count"] == 0
        assert not any(event["agent_stage"] == "verifier" for event in events)
