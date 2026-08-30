# Improvement Changelog

> Do not enter invented results. Update this file only after actual experiments.

| Stage | What We Tried and Why | Evidence / Result | Decision / Learning |
|---|---|---|---|
| Baseline | Single tool-free general-purpose operations analyst using all agent-visible incident data and the standard structured output schema. Historical run `cd671653-c755-4aaf-a83d-4d68d41dcf43` used `gpt-5.6-sol`, OpenAI SDK 2.54.0, and provider-default sampling/reasoning configuration. | 10/10 cases completed with zero execution failures. RCIA 9/10 (0.900); expected-evidence coverage 35/40 (0.875); non-allowlisted evidence 33/78 (0.423); contributing-factor exact accuracy 0.200, precision 0.200, recall 1.000, F1 0.333; mean causal reasoning 1.700/2. | Preserve this run unchanged as historical evidence. CC-005 was the only RCIA miss: the model selected initiating cause `ROUTING_CHANGE`, while benchmark v1 expects resulting condition `QUEUE_IMBALANCE`. The evidence allowlists are non-exhaustive and the 33/78 metric is not a hallucination/factual-error rate. Contributor recall was complete, but the model frequently promoted small or non-material visible deviations into contributing causes; benchmark v1 has no quantitative contributor-materiality threshold. |
| Baseline configuration cleanup | Make future comparisons explicit rather than depending on provider-default reasoning effort. No benchmark, prompt, scoring calculation, historical output, or model change. | Future requests now send `reasoning_effort=medium`; new manifests record `reasoning_effort="medium"`. `OPENAI_MODEL` remains `gpt-5.6-sol`. No new live run has been performed under this configuration. | Use a new run ID for the explicitly pinned baseline and retain the provider-default run above. Compare later phases only against a documented configuration-matched anchor. |
| Iteration 1 | Add deterministic analysis tools and iterative tool selection after observing baseline failure modes. | PENDING | PENDING |
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
