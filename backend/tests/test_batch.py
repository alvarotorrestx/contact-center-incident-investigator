from __future__ import annotations

import json
from pathlib import Path

from helpers import MappingMockBaselineClient, diagnosis_from_truth

from incident_investigator.baseline.batch import run_baseline_batch
from incident_investigator.config import get_settings
from incident_investigator.evaluation import GroundTruthLoader


def test_mock_batch_runs_and_scores_all_ten_cases(isolated_project: Path) -> None:
    truths = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load_all()
    client = MappingMockBaselineClient(
        {truth.incident_id: diagnosis_from_truth(truth) for truth in truths}
    )

    run_id, scores = run_baseline_batch(get_settings(isolated_project), client)

    assert scores["case_count"] == 10
    assert scores["rcia"] == 1.0
    result_root = isolated_project / "results" / "local" / run_id
    trajectory_root = isolated_project / "trajectories" / "local" / run_id
    manifest = json.loads((result_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "COMPLETED"
    assert manifest["failure_count"] == 0
    assert len(list((result_root / "predictions").glob("CC-*.json"))) == 10
    assert len(list(trajectory_root.glob("CC-*.jsonl"))) == 10
    assert (result_root / "scores.json").is_file()
    assert (result_root / "comparison.csv").is_file()
