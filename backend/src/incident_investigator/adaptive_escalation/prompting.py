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


def build_adaptive_investigation_prompt(
    case: VisibleCase,
    first_pass_diagnosis: FinalDiagnosis,
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
        "experiment": "adaptive_escalation",
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
        "first_pass_diagnosis": first_pass_diagnosis.model_dump(mode="json"),
        "first_pass_instruction": (
            "Treat the first-pass diagnosis as an unverified starting hypothesis, not as a known "
            "correct or incorrect answer. Retain or revise it only from visible operational "
            "evidence. No evaluator feedback or score is available."
        ),
        "information_presentation": (
            "Every agent-visible incident table is embedded in this initial request. Use the "
            "deterministic tools for discriminating calculation, comparison, drill-down, and "
            "validation."
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
        version="adaptive_escalation_deep_investigation_1",
    )
