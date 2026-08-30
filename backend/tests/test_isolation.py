from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from incident_investigator.baseline import build_baseline_prompt
from incident_investigator.benchmark import AgentVisibleCaseLoader
from incident_investigator.evaluation import GroundTruthLoader

EVALUATOR_ONLY_KEYS = {
    "primary_root_cause",
    "expected_evidence",
    "supported_signal_ids",
    "expected_causal_chain",
    "intentional_exceptions",
}


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _all_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _all_keys(item)}
    return set()


def test_ground_truth_never_reaches_loader_or_prompt(project_root: Path) -> None:
    loader = AgentVisibleCaseLoader(project_root / "benchmark" / "v1" / "cases")
    truth_loader = GroundTruthLoader(project_root / "benchmark" / "v1" / "ground_truth")

    for summary in loader.list_incidents():
        visible = loader.load(summary.incident_id)
        visible_payload = visible.model_dump(mode="json")
        assert not (_all_keys(visible_payload) & EVALUATOR_ONLY_KEYS)

        prompt = build_baseline_prompt(visible, project_root)
        for key in EVALUATOR_ONLY_KEYS:
            assert f'"{key}":' not in prompt.user
        truth = truth_loader.load(summary.incident_id)
        assert truth.primary_root_cause.detail not in prompt.user


def test_agent_and_api_modules_do_not_import_evaluator(project_root: Path) -> None:
    protected = [
        project_root / "backend" / "src" / "incident_investigator" / "api",
        project_root / "backend" / "src" / "incident_investigator" / "baseline" / "client.py",
        project_root / "backend" / "src" / "incident_investigator" / "baseline" / "prompting.py",
        project_root / "backend" / "src" / "incident_investigator" / "baseline" / "runner.py",
        project_root / "backend" / "src" / "incident_investigator" / "benchmark" / "loader.py",
    ]
    for path in protected:
        files = path.rglob("*.py") if path.is_dir() else [path]
        for file in files:
            source = file.read_text(encoding="utf-8")
            assert "incident_investigator.evaluation" not in source
            assert "ground_truth" not in source.lower()

    check = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import incident_investigator.api; "
                "forbidden=('incident_investigator.evaluation', "
                "'incident_investigator.benchmark.definitions', "
                "'incident_investigator.benchmark.generator', "
                "'incident_investigator.benchmark.validation'); "
                "assert not any(name.startswith(forbidden) for name in sys.modules), "
                "sorted(name for name in sys.modules if name.startswith(forbidden))"
            ),
        ],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stderr


def test_frozen_case_files_contain_no_evaluator_fields(project_root: Path) -> None:
    cases_root = project_root / "benchmark" / "v1" / "cases"
    for path in cases_root.rglob("*"):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for key in EVALUATOR_ONLY_KEYS:
            assert key not in content
