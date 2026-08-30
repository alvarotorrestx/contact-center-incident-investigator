from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from openai import pydantic_function_tool
from pydantic import BaseModel, ConfigDict, Field, model_validator

from incident_investigator.contracts import (
    EvidenceSignal,
    FinalDiagnosis,
    InvestigationStatus,
    RootCauseCategory,
)

OperationalToolName = Literal[
    "summarize_incident_window",
    "get_performance_trends",
    "compare_actual_vs_forecast",
    "analyze_staffing",
    "analyze_queue",
    "compare_queues",
    "get_events",
    "calculate_metric_change",
    "recalculate_service_level",
]

LEDGER_TOOL_NAME = "record_hypothesis_ledger"
LEDGER_VERSION = "v2_hypothesis_ledger_1"


class HypothesisStatus(StrEnum):
    UNTESTED = "UNTESTED"
    POSSIBLE = "POSSIBLE"
    LIKELY = "LIKELY"
    UNLIKELY = "UNLIKELY"
    REJECTED = "REJECTED"


class HypothesisEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: EvidenceSignal
    source_tool: OperationalToolName
    finding: str = Field(min_length=1, max_length=500)


class Hypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: RootCauseCategory
    status: HypothesisStatus
    confidence: float = Field(ge=0, le=1)
    evidence_for: list[HypothesisEvidence] = Field(default_factory=list)
    evidence_against: list[HypothesisEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_ids_are_unique(self) -> Hypothesis:
        for field_name in ("evidence_for", "evidence_against"):
            values = getattr(self, field_name)
            keys = [(item.signal, item.source_tool) for item in values]
            if len(keys) != len(set(keys)):
                raise ValueError(f"{field_name} contains duplicate signal/source pairs")
        return self


class HypothesisLedgerSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypotheses: list[Hypothesis] = Field(min_length=3, max_length=6)
    leading_hypothesis: RootCauseCategory | None = None
    causal_timing_supported: bool = False
    unresolved_critical_contradictions: list[str] = Field(default_factory=list, max_length=5)
    investigation_summary: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def categories_are_unique_and_leader_is_tracked(self) -> HypothesisLedgerSnapshot:
        categories = [item.category for item in self.hypotheses]
        if len(categories) != len(set(categories)):
            raise ValueError("hypothesis categories must be unique")
        if self.leading_hypothesis is not None and self.leading_hypothesis not in categories:
            raise ValueError("leading_hypothesis must appear in hypotheses")
        return self


class HypothesisLedgerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_summary: str = Field(min_length=1, max_length=1000)
    ledger: HypothesisLedgerSnapshot


class LedgerChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: RootCauseCategory
    previous_status: HypothesisStatus | None
    new_status: HypothesisStatus
    previous_confidence: float | None
    new_confidence: float
    evidence_for_added: list[HypothesisEvidence] = Field(default_factory=list)
    evidence_against_added: list[HypothesisEvidence] = Field(default_factory=list)


_ALLOWED_TRANSITIONS: dict[HypothesisStatus, set[HypothesisStatus]] = {
    HypothesisStatus.UNTESTED: {
        HypothesisStatus.UNTESTED,
        HypothesisStatus.POSSIBLE,
        HypothesisStatus.LIKELY,
        HypothesisStatus.UNLIKELY,
        HypothesisStatus.REJECTED,
    },
    HypothesisStatus.POSSIBLE: set(HypothesisStatus),
    HypothesisStatus.LIKELY: {
        HypothesisStatus.LIKELY,
        HypothesisStatus.POSSIBLE,
        HypothesisStatus.UNLIKELY,
        HypothesisStatus.REJECTED,
    },
    HypothesisStatus.UNLIKELY: set(HypothesisStatus),
    HypothesisStatus.REJECTED: {
        HypothesisStatus.REJECTED,
        HypothesisStatus.UNLIKELY,
        HypothesisStatus.POSSIBLE,
    },
}


class HypothesisLedger:
    """Validated, agent-visible hypothesis state with inspectable transitions."""

    def __init__(self) -> None:
        self.snapshot: HypothesisLedgerSnapshot | None = None

    def apply(
        self,
        update: HypothesisLedgerUpdate,
        *,
        executed_tools: set[str],
    ) -> list[LedgerChange]:
        snapshot = update.ledger
        for hypothesis in snapshot.hypotheses:
            for evidence in [*hypothesis.evidence_for, *hypothesis.evidence_against]:
                if evidence.source_tool not in executed_tools:
                    raise ValueError(
                        f"Evidence cites uncalled tool {evidence.source_tool!r} for "
                        f"{hypothesis.category}"
                    )

        previous_by_category = (
            {item.category: item for item in self.snapshot.hypotheses}
            if self.snapshot is not None
            else {}
        )
        current_by_category = {item.category: item for item in snapshot.hypotheses}
        removed = set(previous_by_category) - set(current_by_category)
        if removed:
            raise ValueError(
                "Tracked hypotheses cannot be removed; mark them UNLIKELY or REJECTED: "
                + ", ".join(sorted(item.value for item in removed))
            )

        changes: list[LedgerChange] = []
        for category, current in current_by_category.items():
            previous = previous_by_category.get(category)
            if previous is not None and current.status not in _ALLOWED_TRANSITIONS[previous.status]:
                raise ValueError(
                    f"Invalid hypothesis transition for {category}: "
                    f"{previous.status} -> {current.status}"
                )
            previous_for = (
                {(item.signal, item.source_tool) for item in previous.evidence_for}
                if previous
                else set()
            )
            previous_against = (
                {(item.signal, item.source_tool) for item in previous.evidence_against}
                if previous
                else set()
            )
            current_for = {(item.signal, item.source_tool) for item in current.evidence_for}
            current_against = {(item.signal, item.source_tool) for item in current.evidence_against}
            if not previous_for.issubset(current_for) or not previous_against.issubset(
                current_against
            ):
                raise ValueError(f"Recorded evidence cannot be removed from hypothesis {category}")
            changes.append(
                LedgerChange(
                    category=category,
                    previous_status=previous.status if previous else None,
                    new_status=current.status,
                    previous_confidence=previous.confidence if previous else None,
                    new_confidence=current.confidence,
                    evidence_for_added=[
                        item
                        for item in current.evidence_for
                        if (item.signal, item.source_tool) not in previous_for
                    ],
                    evidence_against_added=[
                        item
                        for item in current.evidence_against
                        if (item.signal, item.source_tool) not in previous_against
                    ],
                )
            )

        if self.snapshot is not None and snapshot == self.snapshot:
            raise ValueError("Hypothesis ledger update did not change the structured state")
        self.snapshot = snapshot
        return changes


class TerminationAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool
    reason: str
    unmet_criteria: list[str] = Field(default_factory=list)


def assess_termination(
    diagnosis: FinalDiagnosis,
    snapshot: HypothesisLedgerSnapshot | None,
    *,
    tool_limit_reached: bool,
) -> TerminationAssessment:
    if snapshot is None:
        return TerminationAssessment(
            allowed=False,
            reason="ledger_missing",
            unmet_criteria=["initialize the structured hypothesis ledger"],
        )

    by_category = {item.category: item for item in snapshot.hypotheses}
    leading = by_category.get(snapshot.leading_hypothesis) if snapshot.leading_hypothesis else None
    alternatives = [
        item for item in snapshot.hypotheses if item.category != snapshot.leading_hypothesis
    ]
    unmet: list[str] = []
    if leading is None:
        unmet.append("identify one leading hypothesis")
    else:
        if leading.category != diagnosis.primary_root_cause_category:
            unmet.append("align the final category with the ledger's leading hypothesis")
        if leading.status is not HypothesisStatus.LIKELY:
            unmet.append("mark the leading hypothesis LIKELY")
        if any(item.confidence >= leading.confidence for item in alternatives):
            unmet.append("make the leading hypothesis uniquely highest-confidence")
        supporting_signals = {item.signal for item in leading.evidence_for}
        supporting_tools = {item.source_tool for item in leading.evidence_for}
        if len(supporting_signals) < 2:
            unmet.append("record at least two distinct supporting evidence signals")
        if len(supporting_tools) < 2:
            unmet.append("support the leader with evidence from at least two distinct tools")

    if len(alternatives) < 2:
        unmet.append("track at least two major competing hypotheses")
    for alternative in alternatives:
        if alternative.status is HypothesisStatus.UNTESTED:
            unmet.append(f"evaluate alternative {alternative.category}")
        if not alternative.evidence_for and not alternative.evidence_against:
            unmet.append(f"record evidence for or against alternative {alternative.category}")
    if not snapshot.causal_timing_supported:
        unmet.append("establish that the proposed cause precedes or explains the effect")
    if snapshot.unresolved_critical_contradictions:
        unmet.append("resolve critical contradictions or return INCONCLUSIVE")

    if not unmet:
        return TerminationAssessment(allowed=True, reason="criteria_satisfied")
    if tool_limit_reached and diagnosis.investigation_status is InvestigationStatus.INCONCLUSIVE:
        return TerminationAssessment(
            allowed=True,
            reason="tool_limit_inconclusive",
            unmet_criteria=unmet,
        )
    return TerminationAssessment(
        allowed=False,
        reason="termination_criteria_not_met",
        unmet_criteria=unmet,
    )


def ledger_tool_schema() -> dict[str, Any]:
    wrapped = pydantic_function_tool(
        HypothesisLedgerUpdate,
        name=LEDGER_TOOL_NAME,
        description=(
            "Record the complete current hypothesis ledger and a concise public decision summary. "
            "This stores state only and does not access incident data."
        ),
    )
    function = wrapped["function"]
    return {
        "type": "function",
        "name": function["name"],
        "description": function.get("description"),
        "parameters": function["parameters"],
        "strict": function["strict"],
    }
