from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from helpers import MockBaselineClient, diagnosis_from_truth

from incident_investigator.api import create_app
from incident_investigator.evaluation import GroundTruthLoader


def _copy_curated_case(project_root: Path, isolated_project: Path, run_id: str) -> None:
    prediction_source = (
        project_root / "results" / "curated" / run_id / "predictions" / "CC-001.json"
    )
    prediction_target = (
        isolated_project / "results" / "curated" / run_id / "predictions" / "CC-001.json"
    )
    prediction_target.parent.mkdir(parents=True)
    shutil.copy2(prediction_source, prediction_target)
    trajectory_source = project_root / "trajectories" / "curated" / run_id / "CC-001.jsonl"
    trajectory_target = isolated_project / "trajectories" / "curated" / run_id / "CC-001.jsonl"
    trajectory_target.parent.mkdir(parents=True)
    shutil.copy2(trajectory_source, trajectory_target)


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _all_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _all_keys(item)}
    return set()


def test_api_exposes_visible_data_and_runs_mock_baseline(isolated_project: Path) -> None:
    truth = GroundTruthLoader(isolated_project / "benchmark" / "v1" / "ground_truth").load("CC-001")
    mock = MockBaselineClient(diagnosis_from_truth(truth))
    client = TestClient(create_app(isolated_project, client_factory=lambda settings: mock))

    assert client.get("/api/health").json()["status"] == "ok"
    incidents = client.get("/api/incidents").json()
    assert len(incidents) == 10
    visible = client.get("/api/incidents/CC-001").json()
    assert set(visible) == {
        "incident_metadata",
        "performance",
        "staffing",
        "forecast",
        "queue_performance",
        "events",
    }
    assert "expected_evidence" not in str(visible)

    response = client.post(
        "/api/investigations",
        json={"incident_id": "CC-001", "system_version": "baseline"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["primary_root_cause_category"] == "DEMAND_SPIKE"
    saved = client.get(f"/api/runs/{payload['run_id']}")
    assert saved.status_code == 200
    assert saved.json()["manifest"]["system_version"] == "baseline"
    assert saved.json()["manifest"]["model_configuration"] == {
        "sampling_parameters": "provider_defaults",
        "reasoning_effort": "medium",
    }


def test_api_rejects_unknown_incident_and_non_baseline_version(isolated_project: Path) -> None:
    client = TestClient(create_app(isolated_project))

    assert client.get("/api/incidents/CC-999").status_code == 404
    assert (
        client.post(
            "/api/investigations",
            json={"incident_id": "CC-001", "system_version": "v1"},
        ).status_code
        == 422
    )


def test_demo_report_is_public_and_evaluator_isolated(
    isolated_project: Path, project_root: Path
) -> None:
    stage_zero_run = "02b97b0d-d68e-45f8-b678-386f7558dd02"
    v2_run = "d3859d8d-b252-426a-970e-89a471a5fe7c"
    _copy_curated_case(project_root, isolated_project, stage_zero_run)
    _copy_curated_case(project_root, isolated_project, v2_run)
    client = TestClient(create_app(isolated_project))

    response = client.get("/api/demo/incidents/CC-001/report")
    assert response.status_code == 200
    report = response.json()
    assert report["mode"] == {
        "id": "default",
        "label": "Standard analysis",
        "description": "Fast, complete-context analysis for day-to-day incident triage.",
        "run_id": stage_zero_run,
        "is_default": True,
    }
    assert report["diagnosis"]["primary_root_cause_category"] == "DEMAND_SPIKE"
    assert report["impact"]["impacted_queues"]
    assert len(report["impact"]["trend"]) == 16
    assert [item["type"] for item in report["trajectory"]] == ["started", "complete"]
    assert report["hypotheses"] == []

    audit = client.get("/api/demo/incidents/CC-001/report?mode=audit").json()
    assert audit["mode"]["run_id"] == v2_run
    assert any(item["type"] == "tool" for item in audit["trajectory"])
    assert audit["hypotheses"]

    forbidden = {
        "expected_evidence",
        "supported_signal_ids",
        "expected_contributors",
        "expected_causal_chain",
        "primary_root_cause",
        "score",
    }
    assert not ((_all_keys(report) | _all_keys(audit)) & forbidden)

    assert client.get("/api/demo/incidents/CC-001/report?mode=verifier").status_code == 422
