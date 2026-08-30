from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from incident_investigator.contracts import EvidenceSignal, RootCauseCategory
from incident_investigator.hypotheses.models import OperationalToolName


class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    REVISE = "REVISE"


class VerificationCheck(StrEnum):
    CAUSAL_TIMING = "causal_timing"
    EVIDENCE_PRESENCE = "evidence_presence"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    ALTERNATIVE_EXPLANATION = "alternative_explanation"
    SYMPTOM_VS_ROOT_CAUSE = "symptom_vs_root_cause"
    TAXONOMY_LEVEL = "taxonomy_level"
    MATERIALITY = "materiality"
    CONTRIBUTOR_ROLE = "contributor_role"
    INCIDENT_SIGNIFICANCE = "incident_significance"


class VerificationFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check: VerificationCheck
    finding: str = Field(min_length=1, max_length=700)
    evidence_signal: EvidenceSignal | None
    source_tool: OperationalToolName | None


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_status: VerificationStatus
    critical_contradictions: list[VerificationFinding] = Field(default_factory=list, max_length=8)
    unsupported_or_weak_claims: list[VerificationFinding] = Field(
        default_factory=list, max_length=8
    )
    stronger_alternative_if_any: RootCauseCategory | None
    recommended_revision: str | None = Field(
        default=None,
        max_length=1000,
        description=(
            "Required and acted upon when status is REVISE. A minor recommendation on a "
            "VERIFIED proposal is recorded but does not trigger a revision."
        ),
    )
    verification_summary: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def status_matches_findings(self) -> VerificationResult:
        if self.verification_status is VerificationStatus.VERIFIED:
            if self.critical_contradictions:
                raise ValueError("VERIFIED cannot include critical contradictions")
            if self.stronger_alternative_if_any is not None:
                raise ValueError("VERIFIED cannot name a stronger alternative")
        elif (
            not self.critical_contradictions and not self.unsupported_or_weak_claims
        ) or not self.recommended_revision:
            raise ValueError("REVISE requires a material finding and recommended_revision")
        return self
