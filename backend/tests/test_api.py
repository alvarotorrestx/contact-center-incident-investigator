from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from helpers import MockBaselineClient, diagnosis_from_truth

from incident_investigator.api import create_app
from incident_investigator.evaluation import GroundTruthLoader


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
