from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_root: Path = DEFAULT_PROJECT_ROOT
    openai_api_key: str | None = None
    openai_model: str | None = None
    openai_max_retries: int = 2
    openai_reasoning_effort: Literal["medium"] = "medium"
    v1_max_tool_calls: int = Field(default=10, ge=1, le=12)
    v2_max_tool_calls: int = Field(default=10, ge=1, le=12)
    v3_max_tool_calls: int = Field(default=10, ge=1, le=12)
    v3_max_revisions: int = Field(default=2, ge=1, le=2)
    final_candidate_max_tool_calls: int = Field(default=10, ge=1, le=12)
    adaptive_max_tool_calls: int = Field(default=10, ge=1, le=12)
    benchmark_version: str = "v1"

    @property
    def cases_root(self) -> Path:
        return self.project_root / "benchmark" / self.benchmark_version / "cases"

    @property
    def ground_truth_root(self) -> Path:
        return self.project_root / "benchmark" / self.benchmark_version / "ground_truth"


def get_settings(project_root: Path | None = None) -> Settings:
    resolved_root = (project_root or DEFAULT_PROJECT_ROOT).resolve()
    return Settings(
        project_root=resolved_root,
        _env_file=resolved_root / ".env",
    )
