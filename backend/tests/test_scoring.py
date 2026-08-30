from __future__ import annotations

from pathlib import Path

from helpers import diagnosis_from_truth

from incident_investigator.evaluation import GroundTruthLoader, score_benchmark, score_prediction


def test_perfect_prediction_scores_deterministically(project_root: Path) -> None:
    truth = GroundTruthLoader(project_root / "benchmark" / "v1" / "ground_truth").load("CC-015")
    prediction = diagnosis_from_truth(truth)

    score = score_prediction(prediction, truth)

    assert score.root_cause_correct
    assert score.evidence_covered == score.evidence_expected
    assert score.unsupported_evidence_claims == 0
    assert score.contributing_exact
    assert score.causal_reasoning_score == 2


def test_invalid_and_missing_predictions_are_auditable(project_root: Path) -> None:
    truths = GroundTruthLoader(project_root / "benchmark" / "v1" / "ground_truth").load_all()
    scores = score_benchmark({truths[0].incident_id: {"invalid": True}}, truths)

    assert scores.case_count == 10
    assert scores.root_cause_correct == 0
    assert scores.rcia == 0
    assert not scores.per_case[0].valid_prediction
    assert scores.per_case[1].validation_error == "missing_prediction"
