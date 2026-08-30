from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from incident_investigator.contracts import FinalDiagnosis
from incident_investigator.hypotheses import HypothesisLedgerSnapshot

from .models import VerificationResult


@dataclass(frozen=True)
class VerifierPrompt:
    system: str
    user: str
    version: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(f"{self.system}\n{self.user}".encode()).hexdigest()


def build_verifier_prompt(
    *,
    incident_metadata: dict[str, Any],
    proposed_diagnosis: FinalDiagnosis,
    hypothesis_state: HypothesisLedgerSnapshot,
    tool_evidence: list[dict[str, Any]],
    project_root: Path,
    revision_number: int,
) -> VerifierPrompt:
    system = (
        (project_root / "prompts" / "v3_adversarial_verifier.txt")
        .read_text(encoding="utf-8")
        .strip()
    )
    payload = {
        "experiment": "v3_adversarial_verification",
        "role_boundary": "Challenge the proposal; do not independently reinvestigate.",
        "revision_number": revision_number,
        "incident_metadata": incident_metadata,
        "proposed_diagnosis": proposed_diagnosis.model_dump(mode="json"),
        "hypothesis_state": hypothesis_state.model_dump(mode="json"),
        "accumulated_visible_tool_evidence": tool_evidence,
        "required_output_schema": VerificationResult.model_json_schema(mode="serialization"),
    }
    return VerifierPrompt(
        system=system,
        user=json.dumps(payload, indent=2, sort_keys=True),
        version="v3_adversarial_verifier_2",
    )
