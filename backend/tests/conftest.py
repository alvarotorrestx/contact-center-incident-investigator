from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def isolated_project(tmp_path: Path, project_root: Path) -> Path:
    shutil.copytree(project_root / "benchmark", tmp_path / "benchmark")
    (tmp_path / "prompts").mkdir()
    shutil.copy2(project_root / "prompts" / "baseline_v1.txt", tmp_path / "prompts")
    return tmp_path
