from __future__ import annotations

import json
from pathlib import Path

from helpers import MockBaselineClient, diagnosis_from_truth

from incident_investigator.baseline import BaselineRunner
from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.evaluation import GroundTruthLoader
from incident_investigator.persistence import RunStore


def test_mock_baseline_persists_manifest_prediction_and_trajectory(isolated_project: Path) -> None:
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    diagnosis = diagnosis_from_truth(truth)
    store = RunStore(isolated_project)
    store.create_manifest({"system_version": "baseline", "model": "mock-baseline-model"})
    runner = BaselineRunner(
        AgentVisibleCaseLoader(isolated_project / "benchmark" / "v1" / "cases"),
        MockBaselineClient(diagnosis),
        store,
    )

    actual = runner.run_case("CC-001")

    assert actual == diagnosis
    assert store.manifest_path.is_file()
    prediction = store.result_root / "predictions" / "CC-001.json"
    assert json.loads(prediction.read_text(encoding="utf-8"))["investigation_status"] == "CONFIRMED"
    events = [
        json.loads(line)
        for line in (store.trajectory_root / "CC-001.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [event["step_number"] for event in events] == [1, 2]
    assert events[1]["token_usage"]["total_tokens"] == 150
