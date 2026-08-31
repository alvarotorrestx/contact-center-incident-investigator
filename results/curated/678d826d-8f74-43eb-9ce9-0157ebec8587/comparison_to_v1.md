# Adaptive Escalation Comparison to V1

- Anchor run: `7fcf7453-609e-4006-8a72-cd1a6b26bcff`
- Candidate run: `678d826d-8f74-43eb-9ce9-0157ebec8587`
- Model: `gpt-5.6-sol`
- Model configuration: `{"reasoning_effort": "medium", "sampling_parameters": "provider_defaults"}`

| Metric | V1 | Adaptive Escalation | Delta |
|---|---:|---:|---:|
| rcia | 0.500000 | 0.800000 | +0.300000 |
| evidence_coverage | 0.425000 | 0.900000 | +0.475000 |
| non_allowlisted_evidence_rate | 0.441860 | 0.425000 | -0.016860 |
| contributing_exact_accuracy | 0.700000 | 0.400000 | -0.300000 |
| contributing_precision | 0.250000 | 0.250000 | +0.000000 |
| contributing_recall | 0.500000 | 1.000000 | +0.500000 |
| contributing_f1 | 0.333333 | 0.400000 | +0.066667 |
| causal_reasoning_average | 0.800000 | 1.500000 | +0.700000 |

- Cases improved: CC-001, CC-007, CC-009, CC-015
- Cases regressed: CC-014
- Cases unchanged: CC-002, CC-003, CC-004, CC-005, CC-012
- Cases with changed predicted category: CC-001, CC-005, CC-007, CC-009, CC-014, CC-015
- Tool calls: {'anchor_average_per_case': 2.1, 'candidate_average_per_case': 0.5, 'anchor_cases_with_one_or_two': ['CC-001', 'CC-003', 'CC-005', 'CC-007', 'CC-009', 'CC-012', 'CC-014', 'CC-015'], 'candidate_cases_with_one_or_two': []}
- Execution failures: {'anchor': 0, 'candidate': 0}
- Runtime: {'anchor_wall_seconds': 175.694609, 'candidate_wall_seconds': 338.334615, 'anchor_summed_case_seconds': 175.618674, 'candidate_summed_case_seconds': 338.261785}
- Token usage: {'anchor': {'input_tokens': 158153, 'input_tokens_details': {'cache_write_tokens': 48522, 'cached_tokens': 108348}, 'output_tokens': 15226, 'output_tokens_details': {'reasoning_tokens': 1970}, 'total_tokens': 173379}, 'candidate': {'input_tokens': 463866, 'input_tokens_details': {'cache_write_tokens': 195333, 'cached_tokens': 267628}, 'output_tokens': 25927, 'output_tokens_details': {'reasoning_tokens': 7536}, 'total_tokens': 489793}}
- Estimated cost (when available): {'anchor': 0.5956012, 'candidate': 1.6058762}
