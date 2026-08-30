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
from incident_investigator.hypotheses import HypothesisLedgerSnapshot, ledger_tool_schema
from incident_investigator.tools import CaseToolbox


@dataclass(frozen=True)
class V2Prompt:
    system: str
    user: str
    operational_tools: list[dict[str, Any]]
    ledger_tool: dict[str, Any]
    version: str

    @property
    def sha256(self) -> str:
        tool_payload = {
            "operational_tools": self.operational_tools,
            "ledger_tool": self.ledger_tool,
        }
        return hashlib.sha256(
            f"{self.system}\n{self.user}\n{json.dumps(tool_payload, sort_keys=True)}".encode()
        ).hexdigest()


def build_v2_prompt(
    case: VisibleCase,
    toolbox: CaseToolbox,
    project_root: Path,
    max_tool_calls: int,
) -> V2Prompt:
    system = (
        (project_root / "prompts" / "v2_hypothesis_investigator.txt")
        .read_text(encoding="utf-8")
        .strip()
    )
    payload = {
        "experiment": "v2_structured_hypothesis_investigator",
        "metric_definition": (
            "service_level_pct = answered_within_threshold / "
            "(offered_calls - short_abandoned_calls) * 100"
        ),
        "root_cause_taxonomy": [item.value for item in RootCauseCategory],
        "canonical_evidence_signals": [item.value for item in EvidenceSignal],
        "canonical_contributing_factors": [item.value for item in ContributingFactor],
        "canonical_causal_concepts": [item.value for item in CausalConcept],
        "hypothesis_ledger_schema": HypothesisLedgerSnapshot.model_json_schema(
            mode="serialization"
        ),
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
            "through deterministic tools over this already-loaded visible incident."
        ),
        "maximum_operational_tool_calls": max_tool_calls,
        "state_protocol": (
            "Initialize the ledger first. After every operational tool result, call "
            "record_hypothesis_ledger with the complete updated state before continuing."
        ),
    }
    return V2Prompt(
        system=system,
        user=json.dumps(payload, indent=2, sort_keys=True),
        operational_tools=toolbox.schemas,
        ledger_tool=ledger_tool_schema(),
        version="v2_hypothesis_investigator_1",
    )
