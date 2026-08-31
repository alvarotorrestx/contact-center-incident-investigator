from __future__ import annotations

from pathlib import Path

from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.presentation import DemoReportService


def test_all_curated_reports_build_from_visible_cases(project_root: Path) -> None:
    loader = AgentVisibleCaseLoader(project_root / "benchmark" / "v1" / "cases")
    service = DemoReportService(project_root, loader)

    for summary in loader.list_incidents():
        for mode in ("default", "audit"):
            report = service.build(summary.incident_id, mode)
            assert report["diagnosis"]["incident_id"] == summary.incident_id
            assert report["impact"]["kpis"]
            assert report["impact"]["queues"]
            assert len(report["impact"]["trend"]) == 16
            assert report["trajectory"][0]["type"] == "started"
            assert report["trajectory"][-1]["type"] == "complete"


def test_standard_and_audit_trajectories_are_honest(project_root: Path) -> None:
    loader = AgentVisibleCaseLoader(project_root / "benchmark" / "v1" / "cases")
    service = DemoReportService(project_root, loader)

    standard = service.build("CC-001", "default")
    audit = service.build("CC-001", "audit")

    assert [item["type"] for item in standard["trajectory"]] == ["started", "complete"]
    assert standard["hypotheses"] == []
    assert any(item["type"] == "tool" for item in audit["trajectory"])
    assert audit["hypotheses"]
    assert all("reasoning" not in item for item in audit["trajectory"])
