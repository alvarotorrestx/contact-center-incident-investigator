# V3 Comparison to V1

- Anchor run: `7fcf7453-609e-4006-8a72-cd1a6b26bcff`
- Candidate run: `5324184e-c646-456c-b58b-8e1c2e89a2fc`
- Model: `gpt-5.6-sol`
- Model configuration: `{"reasoning_effort": "medium", "sampling_parameters": "provider_defaults"}`

| Metric | V1 | V3 | Delta |
|---|---:|---:|---:|
| rcia | 0.500000 | 0.700000 | +0.200000 |
| evidence_coverage | 0.425000 | 0.825000 | +0.400000 |
| non_allowlisted_evidence_rate | 0.441860 | 0.417910 | -0.023950 |
| contributing_exact_accuracy | 0.700000 | 0.300000 | -0.400000 |
| contributing_precision | 0.250000 | 0.222222 | -0.027778 |
| contributing_recall | 0.500000 | 1.000000 | +0.500000 |
| contributing_f1 | 0.333333 | 0.363636 | +0.030303 |
| causal_reasoning_average | 0.800000 | 0.900000 | +0.100000 |

- Cases improved: CC-001, CC-009, CC-015
- Cases regressed: CC-014
- Cases unchanged: CC-002, CC-003, CC-004, CC-005, CC-007, CC-012
- Cases with changed predicted category: CC-001, CC-005, CC-007, CC-009, CC-014, CC-015
- Tool calls: {'anchor_average_per_case': 2.1, 'candidate_average_per_case': 6.0, 'anchor_cases_with_one_or_two': ['CC-001', 'CC-003', 'CC-005', 'CC-007', 'CC-009', 'CC-012', 'CC-014', 'CC-015'], 'candidate_cases_with_one_or_two': []}
- Execution failures: {'anchor': 0, 'candidate': 0}
- Runtime: {'anchor_wall_seconds': 175.694609, 'candidate_wall_seconds': 1421.932136, 'anchor_summed_case_seconds': 175.618674, 'candidate_summed_case_seconds': 1421.85583}
- Token usage: {'anchor': {'input_tokens': 158153, 'input_tokens_details': {'cache_write_tokens': 48522, 'cached_tokens': 108348}, 'output_tokens': 15226, 'output_tokens_details': {'reasoning_tokens': 1970}, 'total_tokens': 173379}, 'candidate': {'input_tokens': 2153092, 'input_tokens_details': {'cache_write_tokens': 622391, 'cached_tokens': 1520427}, 'output_tokens': 106632, 'output_tokens_details': {'reasoning_tokens': 15492}, 'total_tokens': 2259724}}
- Estimated cost (when available): {'anchor': 0.5956012, 'candidate': 5.8938618}
