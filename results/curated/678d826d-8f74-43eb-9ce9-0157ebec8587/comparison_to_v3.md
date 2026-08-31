# Adaptive Escalation Comparison to V3

- Anchor run: `5324184e-c646-456c-b58b-8e1c2e89a2fc`
- Candidate run: `678d826d-8f74-43eb-9ce9-0157ebec8587`
- Model: `gpt-5.6-sol`
- Model configuration: `{"reasoning_effort": "medium", "sampling_parameters": "provider_defaults"}`

| Metric | V3 | Adaptive Escalation | Delta |
|---|---:|---:|---:|
| rcia | 0.700000 | 0.800000 | +0.100000 |
| evidence_coverage | 0.825000 | 0.900000 | +0.075000 |
| non_allowlisted_evidence_rate | 0.417910 | 0.425000 | +0.007090 |
| contributing_exact_accuracy | 0.300000 | 0.400000 | +0.100000 |
| contributing_precision | 0.222222 | 0.250000 | +0.027778 |
| contributing_recall | 1.000000 | 1.000000 | +0.000000 |
| contributing_f1 | 0.363636 | 0.400000 | +0.036364 |
| causal_reasoning_average | 0.900000 | 1.500000 | +0.600000 |

- Cases improved: CC-007
- Cases regressed: none
- Cases unchanged: CC-001, CC-002, CC-003, CC-004, CC-005, CC-009, CC-012, CC-014, CC-015
- Cases with changed predicted category: CC-007
- Tool calls: {'anchor_average_per_case': 6.0, 'candidate_average_per_case': 0.5, 'anchor_cases_with_one_or_two': [], 'candidate_cases_with_one_or_two': []}
- Execution failures: {'anchor': 0, 'candidate': 0}
- Runtime: {'anchor_wall_seconds': 1421.932136, 'candidate_wall_seconds': 338.334615, 'anchor_summed_case_seconds': 1421.85583, 'candidate_summed_case_seconds': 338.261785}
- Token usage: {'anchor': {'input_tokens': 2153092, 'input_tokens_details': {'cache_write_tokens': 622391, 'cached_tokens': 1520427}, 'output_tokens': 106632, 'output_tokens_details': {'reasoning_tokens': 15492}, 'total_tokens': 2259724}, 'candidate': {'input_tokens': 463866, 'input_tokens_details': {'cache_write_tokens': 195333, 'cached_tokens': 267628}, 'output_tokens': 25927, 'output_tokens_details': {'reasoning_tokens': 7536}, 'total_tokens': 489793}}
- Estimated cost (when available): {'anchor': 5.8938618, 'candidate': 1.6058762}
