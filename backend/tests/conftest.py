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
    shutil.copytree(project_root / "prompts", tmp_path / "prompts")
    return tmp_path
