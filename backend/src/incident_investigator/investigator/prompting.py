from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from incident_investigator.contracts import (
    CausalConcept,
    ContributingFactor,
    EvidenceSignal,
    FinalDiagnosis,
    RootCauseCategory,
    VisibleCase,
)
from incident_investigator.tools import CaseToolbox


@dataclass(frozen=True)
class InvestigatorPrompt:
    system: str
    user: str
    tools: list[dict[str, Any]]
    version: str

    @property
    def sha256(self) -> str:
        serialized_tools = json.dumps(self.tools, sort_keys=True)
        return hashlib.sha256(
            f"{self.system}\n{self.user}\n{serialized_tools}".encode()
        ).hexdigest()


def build_investigator_prompt(
    case: VisibleCase,
    toolbox: CaseToolbox,
    project_root: Path,
    max_tool_calls: int,
) -> InvestigatorPrompt:
    system = (
        (project_root / "prompts" / "v1_tool_investigator.txt").read_text(encoding="utf-8").strip()
    )
    payload = {
        "experiment": "v1_tool_investigator",
        "metric_definition": (
            "service_level_pct = answered_within_threshold / "
            "(offered_calls - short_abandoned_calls) * 100"
        ),
        "root_cause_taxonomy": [item.value for item in RootCauseCategory],
        "canonical_evidence_signals": [item.value for item in EvidenceSignal],
        "canonical_contributing_factors": [item.value for item in ContributingFactor],
        "canonical_causal_concepts": [item.value for item in CausalConcept],
        "required_output_schema": FinalDiagnosis.model_json_schema(mode="serialization"),
        "incident_metadata": case.incident_metadata,
        "available_visible_sources": [
            "performance",
            "staffing",
            "forecast",
            "queue_performance",
            "events",
        ],
        "information_presentation": (
            "Raw interval tables are not embedded in this initial prompt. They are available only "
            "through the deterministic tools over this already-loaded visible incident."
        ),
        "maximum_tool_calls": max_tool_calls,
    }
    return InvestigatorPrompt(
        system=system,
        user=json.dumps(payload, indent=2, sort_keys=True),
        tools=toolbox.schemas,
        version="v1_tool_investigator_1",
    )
