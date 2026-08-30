from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .catalogs import CausalConcept, ContributingFactor, EvidenceSignal
from .enums import InvestigationStatus, RootCauseCategory


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: EvidenceSignal
    source: Literal[
        "incident_metadata",
        "performance",
        "staffing",
        "forecast",
        "queue_performance",
        "events",
    ]
    finding: str = Field(min_length=1)


class RejectedHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: RootCauseCategory
    reason: str = Field(min_length=1)


class FinalDiagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str = Field(pattern=r"^CC-\d{3}$")
    investigation_status: InvestigationStatus
    primary_root_cause_category: RootCauseCategory
    primary_root_cause_detail: str = Field(min_length=1)
    contributing_factors: list[ContributingFactor] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceItem] = Field(min_length=1)
    rejected_hypotheses: list[RejectedHypothesis] = Field(default_factory=list)
    causal_chain: list[CausalConcept] = Field(min_length=1)
    recommended_actions: list[str] = Field(min_length=1)
    stakeholder_summary: str = Field(min_length=1)


class IncidentSummary(BaseModel):
    incident_id: str
    date: str
    window_start: str
    window_end: str
    incident_start: str
    alert: str


class VisibleCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_metadata: dict[str, Any]
    performance: list[dict[str, Any]]
    staffing: list[dict[str, Any]]
    forecast: list[dict[str, Any]]
    queue_performance: list[dict[str, Any]]
    events: list[dict[str, Any]]

    @property
    def incident_id(self) -> str:
        return str(self.incident_metadata["incident_id"])


class InvestigationRequest(BaseModel):
    incident_id: str = Field(pattern=r"^CC-\d{3}$")
    system_version: Literal["baseline"] = "baseline"
