from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from incident_investigator.contracts import (
    CausalConcept,
    ContributingFactor,
    EvidenceSignal,
    RootCauseCategory,
)

INCIDENT_ID_PATTERN = re.compile(r"^CC-\d{3}$")


class ExpectedRootCause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: RootCauseCategory
    detail: str


class GroundTruth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str = Field(pattern=r"^CC-\d{3}$")
    primary_root_cause: ExpectedRootCause
    contributing_factors: list[ContributingFactor]
    expected_evidence: list[EvidenceSignal]
    supported_signal_ids: list[EvidenceSignal]
    expected_causal_chain: list[CausalConcept]
    intentional_exceptions: list[str]


class GroundTruthLoader:
    """Evaluator-only loader. Never import this module from API or agent code."""

    def __init__(self, ground_truth_root: Path):
        self.ground_truth_root = ground_truth_root.resolve()

    def load(self, incident_id: str) -> GroundTruth:
        if not INCIDENT_ID_PATTERN.fullmatch(incident_id):
            raise ValueError(f"Invalid incident id: {incident_id!r}")
        path = (self.ground_truth_root / f"{incident_id}.json").resolve()
        if path.parent != self.ground_truth_root:
            raise ValueError("Ground-truth path escapes evaluator root")
        with path.open(encoding="utf-8") as handle:
            return GroundTruth.model_validate(json.load(handle))

    def load_all(self) -> list[GroundTruth]:
        return [self.load(path.stem) for path in sorted(self.ground_truth_root.glob("CC-*.json"))]
