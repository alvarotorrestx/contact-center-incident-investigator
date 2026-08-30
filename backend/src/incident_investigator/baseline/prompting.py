from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from incident_investigator.contracts import (
    CausalConcept,
    ContributingFactor,
    EvidenceSignal,
    FinalDiagnosis,
    RootCauseCategory,
    VisibleCase,
)


@dataclass(frozen=True)
class BaselinePrompt:
    system: str
    user: str
    version: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(f"{self.system}\n{self.user}".encode()).hexdigest()


def build_baseline_prompt(case: VisibleCase, project_root: Path) -> BaselinePrompt:
    system = (project_root / "prompts" / "baseline_v1.txt").read_text(encoding="utf-8").strip()
    payload = {
        "metric_definition": (
            "service_level_pct = answered_within_threshold / "
            "(offered_calls - short_abandoned_calls) * 100"
        ),
        "root_cause_taxonomy": [item.value for item in RootCauseCategory],
        "canonical_evidence_signals": [item.value for item in EvidenceSignal],
        "canonical_contributing_factors": [item.value for item in ContributingFactor],
        "canonical_causal_concepts": [item.value for item in CausalConcept],
        "required_output_schema": FinalDiagnosis.model_json_schema(mode="serialization"),
        "incident": case.model_dump(mode="json"),
    }
    return BaselinePrompt(
        system=system,
        user=json.dumps(payload, indent=2, sort_keys=True),
        version="baseline_v1",
    )
