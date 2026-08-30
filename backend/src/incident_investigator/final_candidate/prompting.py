from __future__ import annotations

import json
from pathlib import Path

from incident_investigator.contracts import (
    CausalConcept,
    ContributingFactor,
    EvidenceSignal,
    FinalDiagnosis,
    RootCauseCategory,
    VisibleCase,
)
from incident_investigator.hypotheses import HypothesisLedgerSnapshot, ledger_tool_schema
from incident_investigator.structured_investigator.prompting import V2Prompt
from incident_investigator.tools import CaseToolbox


def build_final_candidate_prompt(
    case: VisibleCase,
    toolbox: CaseToolbox,
    project_root: Path,
    max_tool_calls: int,
) -> V2Prompt:
    """Compose V2 discipline with the baseline's complete initial visible context."""
    system = (
        (project_root / "prompts" / "v2_hypothesis_investigator.txt")
        .read_text(encoding="utf-8")
        .strip()
    )
    payload = {
        "experiment": "final_candidate",
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
        "incident": case.model_dump(mode="json"),
        "information_presentation": (
            "Every agent-visible incident table is embedded in this initial request, matching the "
            "Stage 0 baseline's information visibility. Use deterministic tools for calculation, "
            "comparison, drill-down, and verification when useful; do not call tools merely to "
            "discover which visible datasets exist."
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
        version="final_candidate_full_context_1",
    )
