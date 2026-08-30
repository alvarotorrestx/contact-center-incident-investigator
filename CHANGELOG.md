# Improvement Changelog

> Do not enter invented results. Update this file only after actual experiments.

| Stage | What We Tried and Why | Evidence / Result | Decision / Learning |
|---|---|---|---|
| Baseline | Single tool-free general-purpose operations analyst using all agent-visible incident data and the standard structured output schema. Historical run `cd671653-c755-4aaf-a83d-4d68d41dcf43` used `gpt-5.6-sol`, OpenAI SDK 2.54.0, and provider-default sampling/reasoning configuration. | 10/10 cases completed with zero execution failures. RCIA 9/10 (0.900); expected-evidence coverage 35/40 (0.875); non-allowlisted evidence 33/78 (0.423); contributing-factor exact accuracy 0.200, precision 0.200, recall 1.000, F1 0.333; mean causal reasoning 1.700/2. | Preserve this run unchanged as historical evidence. CC-005 was the only RCIA miss: the model selected initiating cause `ROUTING_CHANGE`, while benchmark v1 expects resulting condition `QUEUE_IMBALANCE`. The evidence allowlists are non-exhaustive and the 33/78 metric is not a hallucination/factual-error rate. Contributor recall was complete, but the model frequently promoted small or non-material visible deviations into contributing causes; benchmark v1 has no quantitative contributor-materiality threshold. |
| Pinned baseline anchor | Repeat the fair tool-free baseline on benchmark v1 with `gpt-5.6-sol` and explicitly pinned `reasoning_effort=medium`. Run `02b97b0d-d68e-45f8-b678-386f7558dd02`. | 10/10 cases completed with zero execution failures. RCIA 9/10 (0.900); expected-evidence coverage 35/40 (0.875); non-allowlisted evidence 31/76 (0.408); contributing-factor exact accuracy 0.200; contributing-factor F1 0.333; mean causal reasoning 1.800/2. CC-005 was the sole RCIA miss. | This explicitly pinned run is the formal configuration-matched Stage 0 comparison anchor for V1, V2, and V3. Preserve the provider-default run above as separate historical evidence. |
| Iteration 1 | Test whether the same `gpt-5.6-sol` model at medium reasoning improves when it chooses deterministic read-only analysis tools over the same visible benchmark data. V1 used a 1–10 tool-call bound, the unchanged final schema, and detailed decision/tool trajectories. Official run `7fcf7453-609e-4006-8a72-cd1a6b26bcff`. | 10/10 cases produced valid predictions with zero execution failures and 21 tool calls. RCIA 5/10 (0.500); expected-evidence coverage 17/40 (0.425); non-allowlisted evidence 19/43 (0.442); contributor exact accuracy 0.700, precision 0.250, recall 0.500, F1 0.333; mean causal reasoning 0.800/2. Runtime 175.695 seconds; 173,379 tokens; estimated cost $0.5956012. No cases improved RCIA; CC-001, CC-007, CC-009, and CC-015 regressed; the remaining six were unchanged. CC-005 remained incorrect and changed from `ROUTING_CHANGE` to `NO_MATERIAL_INCIDENT`. | The current V1 investigator did not earn promotion over the 9/10 baseline. Seven cases stopped after only one or two tools, often treating a broad summary as sufficient or incorrectly claiming further tools were unavailable. Keep the deterministic tool library and trajectory infrastructure because they provide reusable, auditable analysis; do not make this investigator policy the default. A future V2 experiment may test whether explicit structured hypothesis/evidence state improves investigation breadth, but only after separate approval. |
| Iteration 2 | Add structured hypothesis tracking with explicit evidence for/against alternatives. | PENDING | PENDING |
| Iteration 3 | Add adversarial verification and bounded revision loop. | PENDING | PENDING |
| Iteration 4 | Improve end-to-end React report/UI quality without changing benchmark conditions. | PENDING | PENDING |
| Removed Experiment | Reserve for a meaningful idea that is tested and later removed if it does not help. | PENDING | PENDING |
| Final | Combine only the changes that earned their place. | PENDING | PENDING |

## Main Failure Mode
The baseline can explain the causal mechanism correctly while choosing a different
taxonomy level than benchmark v1, as in CC-005. It also tends to elevate visible but
small/non-material deviations into contributing causes.

## Hot Take / Practical Insight
A deterministic metric is only as meaningful as its reference set. Comparing evidence
IDs with a deliberately non-exhaustive allowlist is useful for audit, but calling every
non-allowlisted item an unsupported factual claim overstates what the benchmark proves.

## Preserved V1 Implementation Attempts

These runs are implementation diagnostics, not the official V1 comparison result:

- `b8079e56-eec9-445a-babe-36b8ba969c7a`: 10 sandbox-network connection failures before any API usage.
- `9aeb35e0-8d49-4a71-93d4-286ff0fbfb75`: 10 API schema-validation failures caused by optional fields in strict tool schemas; fixed generically and regression-tested.
- `c7443733-aa6b-48e7-9dcf-83fc8a53a999`: valid API run but zero tool calls; the model finalized from metadata, so this did not test V1 tool use.
- `39197a77-0124-49a8-bb61-1ff312d68260`: 10 locally rejected zero-tool completions while validating the first minimum-tool-call enforcement approach.

All attempt artifacts remain preserved locally. None were substituted for or merged into the
official V1 result.
