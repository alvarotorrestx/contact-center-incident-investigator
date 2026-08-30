from __future__ import annotations

import pytest
from pydantic import ValidationError

from incident_investigator.contracts import FinalDiagnosis
from incident_investigator.hypotheses import (
    HypothesisLedger,
    HypothesisLedgerSnapshot,
    HypothesisLedgerUpdate,
    assess_termination,
    ledger_tool_schema,
)


def _evidence(signal: str, source_tool: str) -> dict[str, str]:
    return {
        "signal": signal,
        "source_tool": source_tool,
        "finding": f"Observed {signal} via {source_tool}.",
    }


def _snapshot(*, ready: bool = False) -> dict[str, object]:
    return {
        "hypotheses": [
            {
                "category": "DEMAND_SPIKE",
                "status": "LIKELY" if ready else "POSSIBLE",
                "confidence": 0.85 if ready else 0.45,
                "evidence_for": (
                    [
                        _evidence("demand_surge", "compare_actual_vs_forecast"),
                        _evidence("service_level_decline", "get_performance_trends"),
                    ]
                    if ready
                    else []
                ),
                "evidence_against": [],
            },
            {
                "category": "STAFFING_SHORTFALL",
                "status": "UNLIKELY" if ready else "UNTESTED",
                "confidence": 0.1 if ready else 0.3,
                "evidence_for": [],
                "evidence_against": (
                    [_evidence("stable_staffing", "analyze_staffing")] if ready else []
                ),
            },
            {
                "category": "HANDLE_TIME_INCREASE",
                "status": "UNLIKELY" if ready else "UNTESTED",
                "confidence": 0.05 if ready else 0.25,
                "evidence_for": [],
                "evidence_against": (
                    [_evidence("actual_above_forecast", "compare_actual_vs_forecast")]
                    if ready
                    else []
                ),
            },
        ],
        "leading_hypothesis": "DEMAND_SPIKE" if ready else None,
        "causal_timing_supported": ready,
        "unresolved_critical_contradictions": [],
        "investigation_summary": "Demand is leading." if ready else "Initialize alternatives.",
    }


def _diagnosis(*, status: str = "CONFIRMED") -> FinalDiagnosis:
    return FinalDiagnosis.model_validate(
        {
            "incident_id": "CC-001",
            "investigation_status": status,
            "primary_root_cause_category": "DEMAND_SPIKE",
            "primary_root_cause_detail": "Unexpected demand exceeded available capacity.",
            "contributing_factors": [],
            "confidence": 0.85,
            "evidence": [
                {
                    "signal": "demand_surge",
                    "source": "forecast",
                    "finding": "Demand increased materially.",
                }
            ],
            "rejected_hypotheses": [],
            "causal_chain": ["unexpected_demand", "service_level_degradation"],
            "recommended_actions": ["Reforecast and add capacity."],
            "stakeholder_summary": "Demand exceeded planned capacity.",
        }
    )


def test_hypothesis_ledger_schema_is_strict_and_requires_competing_hypotheses() -> None:
    schema = ledger_tool_schema()
    parameters = schema["parameters"]

    assert schema["strict"] is True
    assert set(parameters["required"]) == set(parameters["properties"])
    with pytest.raises(ValidationError):
        HypothesisLedgerSnapshot.model_validate(
            {**_snapshot(), "hypotheses": _snapshot()["hypotheses"][:2]}
        )
    duplicate = _snapshot()
    duplicate["hypotheses"][2]["category"] = "STAFFING_SHORTFALL"
    with pytest.raises(ValidationError, match="unique"):
        HypothesisLedgerSnapshot.model_validate(duplicate)


def test_ledger_records_evidence_and_validates_status_transitions() -> None:
    ledger = HypothesisLedger()
    initial = HypothesisLedgerUpdate.model_validate(
        {"decision_summary": "Initialize.", "ledger": _snapshot()}
    )
    ledger.apply(initial, executed_tools=set())
    ready = HypothesisLedgerUpdate.model_validate(
        {
            "decision_summary": "Evidence discriminates alternatives.",
            "ledger": _snapshot(ready=True),
        }
    )
    changes = ledger.apply(
        ready,
        executed_tools={
            "compare_actual_vs_forecast",
            "get_performance_trends",
            "analyze_staffing",
        },
    )

    demand_change = next(item for item in changes if item.category == "DEMAND_SPIKE")
    assert demand_change.previous_status == "POSSIBLE"
    assert demand_change.new_status == "LIKELY"
    assert len(demand_change.evidence_for_added) == 2
    assert ledger.snapshot.hypotheses[1].evidence_against

    direct = _snapshot(ready=True)
    direct["hypotheses"][1]["status"] = "LIKELY"
    direct["hypotheses"][1]["confidence"] = 0.86
    fresh = HypothesisLedger()
    fresh.apply(initial, executed_tools=set())
    fresh.apply(
        HypothesisLedgerUpdate.model_validate(
            {"decision_summary": "New evidence strongly supports staffing.", "ledger": direct}
        ),
        executed_tools={
            "compare_actual_vs_forecast",
            "get_performance_trends",
            "analyze_staffing",
        },
    )
    assert fresh.snapshot.hypotheses[1].status == "LIKELY"

    rejected = _snapshot(ready=True)
    rejected["hypotheses"][0]["status"] = "REJECTED"
    rejected["hypotheses"][0]["confidence"] = 0.01
    ledger.apply(
        HypothesisLedgerUpdate.model_validate(
            {"decision_summary": "Reject demand.", "ledger": rejected}
        ),
        executed_tools={
            "compare_actual_vs_forecast",
            "get_performance_trends",
            "analyze_staffing",
        },
    )
    with pytest.raises(ValueError, match="Invalid hypothesis transition"):
        ledger.apply(
            ready,
            executed_tools={
                "compare_actual_vs_forecast",
                "get_performance_trends",
                "analyze_staffing",
            },
        )


def test_ledger_rejects_evidence_from_uncalled_tool() -> None:
    ledger = HypothesisLedger()
    with pytest.raises(ValueError, match="uncalled tool"):
        ledger.apply(
            HypothesisLedgerUpdate.model_validate(
                {"decision_summary": "Ready.", "ledger": _snapshot(ready=True)}
            ),
            executed_tools={"get_performance_trends"},
        )


def test_termination_blocks_untested_alternatives_and_allows_bounded_inconclusive() -> None:
    diagnosis = _diagnosis()
    incomplete = HypothesisLedgerSnapshot.model_validate(_snapshot())
    blocked = assess_termination(diagnosis, incomplete, tool_limit_reached=False)

    assert blocked.allowed is False
    assert any("alternative" in item for item in blocked.unmet_criteria)
    assert (
        assess_termination(
            _diagnosis(status="INCONCLUSIVE"), incomplete, tool_limit_reached=True
        ).reason
        == "tool_limit_inconclusive"
    )

    ready = assess_termination(
        diagnosis,
        HypothesisLedgerSnapshot.model_validate(_snapshot(ready=True)),
        tool_limit_reached=False,
    )
    assert ready.allowed is True
    assert ready.reason == "criteria_satisfied"
