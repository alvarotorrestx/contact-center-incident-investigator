from __future__ import annotations

import csv
import io
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from incident_investigator.contracts import FinalDiagnosis

from .ground_truth import GroundTruth


class PerCaseScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    valid_prediction: bool
    validation_error: str | None = None
    root_cause_correct: bool
    evidence_covered: int
    evidence_expected: int
    non_allowlisted_evidence_count: int
    predicted_evidence_count: int
    contributing_exact: bool
    contributing_true_positive: int
    contributing_predicted: int
    contributing_expected: int
    causal_reasoning_score: int


class BenchmarkScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_count: int
    root_cause_correct: int
    rcia: float
    evidence_covered: int
    evidence_expected: int
    evidence_coverage: float
    non_allowlisted_evidence_count: int
    predicted_evidence_count: int
    non_allowlisted_evidence_rate: float
    contributing_exact_count: int
    contributing_exact_accuracy: float
    contributing_precision: float
    contributing_recall: float
    contributing_f1: float
    causal_reasoning_total: int
    causal_reasoning_average: float
    per_case: list[PerCaseScore]

    def to_csv(self) -> str:
        buffer = io.StringIO()
        fieldnames = list(PerCaseScore.model_fields)
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for item in self.per_case:
            writer.writerow(item.model_dump(mode="json"))
        return buffer.getvalue()

    def to_markdown(self) -> str:
        return (
            "# Benchmark Scores\n\n"
            f"- Cases: {self.case_count}\n"
            f"- RCIA: {self.root_cause_correct}/{self.case_count} ({self.rcia:.3f})\n"
            f"- Expected-evidence coverage: {self.evidence_covered}/{self.evidence_expected} "
            f"({self.evidence_coverage:.3f})\n"
            f"- Non-allowlisted evidence rate: {self.non_allowlisted_evidence_count}/"
            f"{self.predicted_evidence_count} ({self.non_allowlisted_evidence_rate:.3f})\n"
            f"- Contributing-factor exact accuracy: {self.contributing_exact_accuracy:.3f}\n"
            f"- Contributing-factor F1: {self.contributing_f1:.3f}\n"
            f"- Mean causal reasoning score: {self.causal_reasoning_average:.3f}/2\n"
        )


def _ordered_subsequence(expected: list[object], predicted: list[object]) -> bool:
    iterator = iter(predicted)
    return all(any(candidate == item for candidate in iterator) for item in expected)


def score_prediction(
    prediction: FinalDiagnosis | Mapping[str, object] | None, truth: GroundTruth
) -> PerCaseScore:
    validation_error: str | None = None
    parsed: FinalDiagnosis | None
    if prediction is None:
        parsed = None
        validation_error = "missing_prediction"
    else:
        try:
            parsed = (
                prediction
                if isinstance(prediction, FinalDiagnosis)
                else FinalDiagnosis.model_validate(prediction)
            )
        except Exception as exc:  # Pydantic supplies a stable, auditable validation message.
            parsed = None
            validation_error = str(exc)

    if parsed is None:
        return PerCaseScore(
            incident_id=truth.incident_id,
            valid_prediction=False,
            validation_error=validation_error,
            root_cause_correct=False,
            evidence_covered=0,
            evidence_expected=len(set(truth.expected_evidence)),
            non_allowlisted_evidence_count=0,
            predicted_evidence_count=0,
            contributing_exact=False,
            contributing_true_positive=0,
            contributing_predicted=0,
            contributing_expected=len(set(truth.contributing_factors)),
            causal_reasoning_score=0,
        )

    predicted_evidence = {item.signal for item in parsed.evidence}
    expected_evidence = set(truth.expected_evidence)
    supported_evidence = set(truth.supported_signal_ids)
    predicted_contributing = set(parsed.contributing_factors)
    expected_contributing = set(truth.contributing_factors)
    root_correct = parsed.primary_root_cause_category == truth.primary_root_cause.category
    chain_correct = _ordered_subsequence(truth.expected_causal_chain, parsed.causal_chain)

    return PerCaseScore(
        incident_id=truth.incident_id,
        valid_prediction=True,
        validation_error=None,
        root_cause_correct=root_correct,
        evidence_covered=len(predicted_evidence & expected_evidence),
        evidence_expected=len(expected_evidence),
        non_allowlisted_evidence_count=len(predicted_evidence - supported_evidence),
        predicted_evidence_count=len(predicted_evidence),
        contributing_exact=predicted_contributing == expected_contributing,
        contributing_true_positive=len(predicted_contributing & expected_contributing),
        contributing_predicted=len(predicted_contributing),
        contributing_expected=len(expected_contributing),
        causal_reasoning_score=2 if root_correct and chain_correct else (1 if root_correct else 0),
    )


def _fraction(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def score_benchmark(
    predictions: Mapping[str, FinalDiagnosis | Mapping[str, object] | None],
    truths: list[GroundTruth],
) -> BenchmarkScores:
    per_case = [score_prediction(predictions.get(truth.incident_id), truth) for truth in truths]
    case_count = len(per_case)
    root_correct = sum(item.root_cause_correct for item in per_case)
    evidence_covered = sum(item.evidence_covered for item in per_case)
    evidence_expected = sum(item.evidence_expected for item in per_case)
    non_allowlisted = sum(item.non_allowlisted_evidence_count for item in per_case)
    predicted_evidence = sum(item.predicted_evidence_count for item in per_case)
    contributing_exact = sum(item.contributing_exact for item in per_case)
    contributing_tp = sum(item.contributing_true_positive for item in per_case)
    contributing_predicted = sum(item.contributing_predicted for item in per_case)
    contributing_expected = sum(item.contributing_expected for item in per_case)
    precision = _fraction(contributing_tp, contributing_predicted)
    recall = _fraction(contributing_tp, contributing_expected)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    causal_total = sum(item.causal_reasoning_score for item in per_case)
    return BenchmarkScores(
        case_count=case_count,
        root_cause_correct=root_correct,
        rcia=_fraction(root_correct, case_count),
        evidence_covered=evidence_covered,
        evidence_expected=evidence_expected,
        evidence_coverage=_fraction(evidence_covered, evidence_expected),
        non_allowlisted_evidence_count=non_allowlisted,
        predicted_evidence_count=predicted_evidence,
        non_allowlisted_evidence_rate=_fraction(non_allowlisted, predicted_evidence),
        contributing_exact_count=contributing_exact,
        contributing_exact_accuracy=_fraction(contributing_exact, case_count),
        contributing_precision=precision,
        contributing_recall=recall,
        contributing_f1=f1,
        causal_reasoning_total=causal_total,
        causal_reasoning_average=_fraction(causal_total, case_count),
        per_case=per_case,
    )
