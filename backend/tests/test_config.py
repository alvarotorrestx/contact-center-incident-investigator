from __future__ import annotations

import sys
from pathlib import Path

import pytest

from incident_investigator import __main__ as cli
from incident_investigator.baseline import batch
from incident_investigator.config import Settings, get_settings


def test_settings_load_openai_config_from_explicit_project_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    unrelated_working_directory = tmp_path / "elsewhere"
    project_root.mkdir()
    unrelated_working_directory.mkdir()
    (project_root / ".env").write_text(
        "OPENAI_API_KEY=test-only-placeholder\nOPENAI_MODEL=test-model\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.chdir(unrelated_working_directory)

    settings = get_settings(project_root)

    assert settings.openai_api_key == "test-only-placeholder"
    assert settings.openai_model == "test-model"
    assert settings.openai_reasoning_effort == "medium"
    assert settings.project_root == project_root.resolve()


def test_cli_uses_project_root_env_without_exposing_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".env").write_text(
        "OPENAI_API_KEY=cli-test-placeholder\nOPENAI_MODEL=cli-test-model\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    captured_settings: list[Settings] = []

    def fake_run(settings: Settings) -> tuple[str, dict[str, object]]:
        captured_settings.append(settings)
        return "test-run-id", {}

    monkeypatch.setattr(batch, "run_live_baseline", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "incident-investigator",
            "--project-root",
            str(project_root),
            "run-baseline",
        ],
    )

    cli.main()

    output = capsys.readouterr().out
    assert captured_settings[0].openai_api_key == "cli-test-placeholder"
    assert captured_settings[0].openai_model == "cli-test-model"
    assert "cli-test-placeholder" not in output
