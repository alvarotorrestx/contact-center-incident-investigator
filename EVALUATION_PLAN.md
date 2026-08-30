# Evaluation Plan

## Experimental Principle
Keep the comparison fair:
- Same underlying model.
- Same benchmark incidents.
- Same data available.
- Same root-cause taxonomy.
- Same final output schema.
- Different investigation strategy.

The baseline must not be intentionally crippled.

## Primary Metric
### Root-Cause Identification Accuracy (RCIA)

RCIA = correct primary root-cause categories / total evaluated incidents

The comparison is deterministic:
`predicted_category == expected_category`

Do not invent results. Report only benchmark outputs produced by actual runs.

## Secondary Metrics

### Expected-Evidence Coverage
Designated scenario evidence correctly surfaced / total designated expected evidence items.

This measures whether the system found the evidence selected as important to the
scenario. It is not a measure of every factual observation the system could
legitimately make from the visible data.

### Non-Allowlisted Evidence Rate
Predicted structured evidence signal IDs absent from the case-specific
`supported_signal_ids` allowlist / all predicted structured evidence signal IDs.

For benchmark `v1`, the case-specific allowlists are intentionally not exhaustive
factual catalogs. A non-allowlisted evidence ID may be a legitimate secondary
observation, an imprecise canonical-ID choice, an inference not directly represented
in the visible schema, or genuine model overreach. Therefore this metric must not be
reported as a hallucination rate, factual-error rate, or direct measure of unsupported
reasoning. Free-form stakeholder prose is not scored as an atomic factual-claim set.

### Contributing-Factor Accuracy
Measure whether the system distinguishes:
- primary root cause
- contributing factors

This is especially important in multifactor and adversarial cases.

Benchmark `v1` does not define a quantitative materiality threshold for promoting a
visible deviation into a contributing cause. Contributor materiality is therefore a
known limitation that must be considered alongside exact-set accuracy, precision,
recall, and F1; it must not be repaired retroactively after observing predictions.

### Causal Reasoning Score
Per incident:
- 0 = incorrect explanation
- 1 = correct root cause but weak/incorrect causal explanation
- 2 = correct root cause and correct causal chain

This is secondary; RCIA remains the headline metric.

## Benchmark Case Catalog

| ID | Scenario | Ground Truth | Difficulty |
|---|---|---|---|
| CC-001 | Sudden SL collapse | DEMAND_SPIKE | Easy |
| CC-002 | Gradual SL deterioration | STAFFING_SHORTFALL | Easy |
| CC-003 | Normal demand/staffing but queue growth | HANDLE_TIME_INCREASE | Easy-Medium |
| CC-004 | AHT spikes after routing change | ROUTING_CHANGE | Medium |
| CC-005 | One queue fails while center average looks acceptable | QUEUE_IMBALANCE (routing misconfiguration detail) | Medium |
| CC-006 | Abandonment surge following staffing reduction | STAFFING_SHORTFALL | Medium |
| CC-007 | Nominal headcount but service deteriorates | ADHERENCE_DROP | Medium |
| CC-008 | Midday degradation during training | TRAINING_CAPACITY_LOSS | Medium |
| CC-009 | Sudden accumulation during voice/platform issue | PLATFORM_INCIDENT | Medium |
| CC-010 | Demand materially exceeds plan | FORECAST_ERROR | Medium |
| CC-011 | Aggregate staffing healthy, one segment starved | QUEUE_IMBALANCE | Medium-Hard |
| CC-012 | Dashboard indicates severe issue but counts disagree | DATA_QUALITY | Hard |
| CC-013 | Severe degradation from demand + staffing together | MULTIFACTOR | Hard |
| CC-014 | Brief fluctuation with no corroborating issue | NO_MATERIAL_INCIDENT | Hard |
| CC-015 | Volume rises modestly, but routing event drives transfer/AHT spike | ROUTING_CHANGE | Adversarial |

## MVP Benchmark Strategy
Target: all 15 cases.

If time becomes the constraint:
- Implement and validate at least 10 high-quality cases.
- Keep CC-012, CC-014, and CC-015 in the evaluated set because they test restraint, data validation, and adversarial reasoning.
- Do not submit partially validated synthetic cases merely to reach 15.

Recommended 10-case core if scope must be cut:
CC-001, CC-002, CC-003, CC-004, CC-005, CC-007, CC-009, CC-012, CC-014, CC-015.

Benchmark `v1` is this 10-case core. The remaining catalog cases are candidates for
a later benchmark version and must not be added selectively after observing model
predictions.

## Ground-Truth Record
Ground truth must live separately from data visible to the agent.

Example:

```json
{
  "incident_id": "CC-015",
  "primary_root_cause": {
    "category": "ROUTING_CHANGE",
    "detail": "Routing change increased unnecessary transfers."
  },
  "contributing_factors": ["moderate_volume_increase"],
  "expected_evidence": [
    "routing_change_event",
    "transfer_rate_increase",
    "aht_increase",
    "stable_staffing"
  ],
  "misleading_evidence": [
    "moderate_volume_increase"
  ],
  "expected_causal_chain": [
    "routing_change",
    "increased_transfers",
    "increased_aht",
    "reduced_throughput",
    "queue_growth",
    "service_level_degradation"
  ]
}
```

## Synthetic Data Rules
- Use deterministic generation with a fixed random seed (initially 42).
- Include normal operational noise.
- Avoid cartoonishly perfect before/after values.
- Causes must precede effects in time.
- Different queues should have different normal profiles.
- Incident injections should alter only the signals logically associated with the scenario, plus natural downstream effects.
- Include misleading but plausible signals in harder cases.
- Data-quality cases should contain internal inconsistencies that can be independently verified.
- No-incident cases should contain brief normal variance without a sustained causal pattern.

## Evaluation Procedure
For each benchmark version:
1. Generate/freeze the benchmark.
2. Run the baseline over every evaluation case.
3. Save full output and trajectory.
4. Score against hidden ground truth.
5. Run the candidate agent workflow on the exact same cases.
6. Save full output and trajectory.
7. Score against the same ground truth.
8. Produce a comparison table.
9. Record runtime, model configuration, token usage, and estimated cost if available.

The formal Stage 0 comparison anchor for V1–V3 is run
`02b97b0d-d68e-45f8-b678-386f7558dd02`: benchmark v1, `gpt-5.6-sol`, and explicitly pinned
`reasoning_effort=medium`. V1 changes only information presentation and investigation strategy:
the baseline receives every visible table in one prompt, while V1 lets the same model select
deterministic read-only tools over the same visible case.

## Reproducibility Controls
Record:
- model and exact version/name
- model parameters
- benchmark seed
- prompt/instruction version
- code commit/version if available
- tool implementation version
- runtime
- token/cost information when available

Do not claim perfect LLM determinism. Claim reproducibility of the benchmark, configuration, commands, scoring criteria, and main experimental comparison.
