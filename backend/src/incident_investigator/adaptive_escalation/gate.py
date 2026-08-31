from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from incident_investigator.contracts import (
    EvidenceSignal,
    FinalDiagnosis,
    InvestigationStatus,
    RootCauseCategory,
    VisibleCase,
)
from incident_investigator.tools import CaseToolbox

GATE_VERSION = "adaptive_gate_1"
MINIMUM_CONFIDENCE = 0.70
MAXIMUM_SERVICE_LEVEL_DIFFERENCE_POINTS = 1.0


@dataclass(frozen=True)
class EscalationCheck:
    check_id: str
    triggered: bool
    summary: str
    observed: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EscalationDecision:
    escalate: bool
    triggers: tuple[str, ...]
    checks: tuple[EscalationCheck, ...]
    gate_version: str = GATE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_version": self.gate_version,
            "escalate": self.escalate,
            "triggers": list(self.triggers),
            "checks": [check.to_dict() for check in self.checks],
        }


_EVENT_REQUIREMENTS: dict[RootCauseCategory, tuple[str, ...]] = {
    RootCauseCategory.ROUTING_CHANGE: ("routing",),
    RootCauseCategory.PLATFORM_INCIDENT: ("platform", "telephony", "voice"),
    RootCauseCategory.TRAINING_CAPACITY_LOSS: ("training",),
}

_EVIDENCE_EVENT_REQUIREMENTS: dict[EvidenceSignal, tuple[str, ...]] = {
    EvidenceSignal.ROUTING_CHANGE_EVENT: ("routing",),
    EvidenceSignal.PLATFORM_EVENT: ("platform", "telephony", "voice"),
}


def _event_text(event: dict[str, Any]) -> str:
    return " ".join(
        str(event.get(key, "")).casefold() for key in ("event_type", "scope", "description")
    )


def _matching_causal_events(
    case: VisibleCase,
    keywords: tuple[str, ...],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    incident_start = datetime.fromisoformat(str(case.incident_metadata["incident_start"]))
    matching = [
        event for event in case.events if any(keyword in _event_text(event) for keyword in keywords)
    ]
    timely = [
        event
        for event in matching
        if datetime.fromisoformat(str(event["timestamp"])) <= incident_start
    ]
    return matching, timely


def _count_conservation_mismatches(case: VisibleCase) -> list[dict[str, Any]]:
    mismatches = []
    for row in case.performance:
        difference = (
            int(row["offered_calls"]) - int(row["answered_calls"]) - int(row["abandoned_calls"])
        )
        if difference != 0:
            mismatches.append(
                {
                    "timestamp": row["timestamp"],
                    "offered_minus_answered_minus_abandoned": difference,
                }
            )
    return mismatches


def evaluate_escalation(case: VisibleCase, diagnosis: FinalDiagnosis) -> EscalationDecision:
    """Apply the frozen, evaluator-independent adaptive escalation gate."""
    if diagnosis.incident_id != case.incident_id:
        raise ValueError("Diagnosis incident_id does not match visible case")

    checks: list[EscalationCheck] = []
    checks.append(
        EscalationCheck(
            check_id="first_pass_inconclusive",
            triggered=diagnosis.investigation_status is InvestigationStatus.INCONCLUSIVE,
            summary="Escalate an explicitly inconclusive first-pass diagnosis.",
            observed={"investigation_status": diagnosis.investigation_status.value},
        )
    )
    checks.append(
        EscalationCheck(
            check_id="low_first_pass_confidence",
            triggered=diagnosis.confidence < MINIMUM_CONFIDENCE,
            summary="Escalate when first-pass confidence is below the frozen 0.70 threshold.",
            observed={
                "confidence": diagnosis.confidence,
                "minimum_confidence": MINIMUM_CONFIDENCE,
            },
        )
    )

    evidence_signals = {item.signal for item in diagnosis.evidence}
    evidence_sources = {item.source for item in diagnosis.evidence}
    insufficient_support = len(evidence_signals) < 2 or len(evidence_sources) < 2
    checks.append(
        EscalationCheck(
            check_id="insufficient_independent_evidence",
            triggered=insufficient_support,
            summary=(
                "Escalate unless the structured diagnosis cites at least two distinct signals "
                "from at least two visible sources."
            ),
            observed={
                "distinct_signal_count": len(evidence_signals),
                "distinct_source_count": len(evidence_sources),
                "minimum_distinct_signals": 2,
                "minimum_distinct_sources": 2,
            },
        )
    )

    recalculation = CaseToolbox(case).recalculate_service_level()
    count_mismatches = _count_conservation_mismatches(case)
    maximum_difference = float(recalculation["maximum_absolute_difference_pct_points"] or 0.0)
    consistency_failure = maximum_difference > MAXIMUM_SERVICE_LEVEL_DIFFERENCE_POINTS or bool(
        count_mismatches
    )
    checks.append(
        EscalationCheck(
            check_id="visible_metric_consistency_failure",
            triggered=consistency_failure,
            summary=(
                "Escalate hard visible-data inconsistencies: service-level recomputation differs "
                "by more than 1 percentage point or offered calls do not equal answered plus "
                "abandoned calls."
            ),
            observed={
                "maximum_service_level_difference_pct_points": maximum_difference,
                "maximum_allowed_difference_pct_points": (MAXIMUM_SERVICE_LEVEL_DIFFERENCE_POINTS),
                "count_conservation_mismatch_count": len(count_mismatches),
                "count_conservation_mismatches": count_mismatches,
            },
        )
    )

    event_requirements: list[tuple[str, tuple[str, ...]]] = []
    category_keywords = _EVENT_REQUIREMENTS.get(diagnosis.primary_root_cause_category)
    if category_keywords:
        event_requirements.append(
            (f"category:{diagnosis.primary_root_cause_category.value}", category_keywords)
        )
    for signal in sorted(evidence_signals, key=lambda item: item.value):
        keywords = _EVIDENCE_EVENT_REQUIREMENTS.get(signal)
        if keywords:
            event_requirements.append((f"evidence:{signal.value}", keywords))

    conflicts: list[dict[str, Any]] = []
    for claim, keywords in event_requirements:
        matching, timely = _matching_causal_events(case, keywords)
        if not timely:
            conflicts.append(
                {
                    "claim": claim,
                    "required_event_keywords": list(keywords),
                    "matching_event_count": len(matching),
                    "timely_event_count": 0,
                }
            )
    checks.append(
        EscalationCheck(
            check_id="event_claim_temporal_conflict",
            triggered=bool(conflicts),
            summary=(
                "Escalate when an event-dependent category or structured event signal lacks a "
                "matching visible event at or before incident onset."
            ),
            observed={"conflicts": conflicts, "evaluated_claim_count": len(event_requirements)},
        )
    )

    triggers = tuple(check.check_id for check in checks if check.triggered)
    return EscalationDecision(escalate=bool(triggers), triggers=triggers, checks=tuple(checks))
