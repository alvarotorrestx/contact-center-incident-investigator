from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from incident_investigator.contracts import (
    CausalConcept,
    ContributingFactor,
    EvidenceSignal,
    RootCauseCategory,
)


class ScenarioDefinition(BaseModel):
    incident_id: str = Field(pattern=r"^CC-\d{3}$")
    date: str
    scenario: str
    primary_root_cause: RootCauseCategory
    primary_detail: str
    effect: str
    expected_evidence: list[EvidenceSignal]
    supported_signals: list[EvidenceSignal]
    contributing_factors: list[ContributingFactor]
    expected_causal_chain: list[CausalConcept]


class BenchmarkDefinition(BaseModel):
    benchmark_version: str
    seed: int
    interval_minutes: int
    interval_count: int
    cases: list[ScenarioDefinition]


def load_definition(path: Path) -> BenchmarkDefinition:
    with path.open(encoding="utf-8") as handle:
        raw: dict[str, Any] = json.load(handle)
    return BenchmarkDefinition.model_validate(raw)
