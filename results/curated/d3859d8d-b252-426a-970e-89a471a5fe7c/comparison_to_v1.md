# V2 Comparison to V1

- Anchor run: `7fcf7453-609e-4006-8a72-cd1a6b26bcff`
- Candidate run: `d3859d8d-b252-426a-970e-89a471a5fe7c`
- Model: `gpt-5.6-sol`
- Model configuration: `{"reasoning_effort": "medium", "sampling_parameters": "provider_defaults"}`

| Metric | V1 | V2 | Delta |
|---|---:|---:|---:|
| rcia | 0.500000 | 0.700000 | +0.200000 |
| evidence_coverage | 0.425000 | 0.850000 | +0.425000 |
| non_allowlisted_evidence_rate | 0.441860 | 0.384615 | -0.057245 |
| contributing_exact_accuracy | 0.700000 | 0.200000 | -0.500000 |
| contributing_precision | 0.250000 | 0.200000 | -0.050000 |
| contributing_recall | 0.500000 | 1.000000 | +0.500000 |
| contributing_f1 | 0.333333 | 0.333333 | +0.000000 |
| causal_reasoning_average | 0.800000 | 1.000000 | +0.200000 |

- Cases improved: CC-001, CC-009, CC-015
- Cases regressed: CC-014
- Cases unchanged: CC-002, CC-003, CC-004, CC-005, CC-007, CC-012
- Cases with changed predicted category: CC-001, CC-005, CC-007, CC-009, CC-014, CC-015
- Tool calls: {'anchor_average_per_case': 2.1, 'candidate_average_per_case': 4.9, 'anchor_cases_with_one_or_two': ['CC-001', 'CC-003', 'CC-005', 'CC-007', 'CC-009', 'CC-012', 'CC-014', 'CC-015'], 'candidate_cases_with_one_or_two': []}
- Execution failures: {'anchor': 0, 'candidate': 0}
- Runtime: {'anchor_wall_seconds': 175.694609, 'candidate_wall_seconds': 793.079731, 'anchor_summed_case_seconds': 175.618674, 'candidate_summed_case_seconds': 792.990075}
- Token usage: {'anchor': {'input_tokens': 158153, 'input_tokens_details': {'cache_write_tokens': 48522, 'cached_tokens': 108348}, 'output_tokens': 15226, 'output_tokens_details': {'reasoning_tokens': 1970}, 'total_tokens': 173379}, 'candidate': {'input_tokens': 1337676, 'input_tokens_details': {'cache_write_tokens': 275804, 'cached_tokens': 1053390}, 'output_tokens': 72493, 'output_tokens_details': {'reasoning_tokens': 7179}, 'total_tokens': 1410169}}
- Estimated cost (when available): {'anchor': 0.5956012, 'candidate': 3.284164}
