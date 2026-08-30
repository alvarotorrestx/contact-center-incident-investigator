# Final Candidate Comparison to V2

- Anchor run: `d3859d8d-b252-426a-970e-89a471a5fe7c`
- Candidate run: `9730ac8f-89d6-4102-acef-528d9027d80e`
- Model: `gpt-5.6-sol`
- Model configuration: `{"reasoning_effort": "medium", "sampling_parameters": "provider_defaults"}`

| Metric | V2 | Final Candidate | Delta |
|---|---:|---:|---:|
| rcia | 0.700000 | 0.800000 | +0.100000 |
| evidence_coverage | 0.850000 | 0.775000 | -0.075000 |
| non_allowlisted_evidence_rate | 0.384615 | 0.396825 | +0.012210 |
| contributing_exact_accuracy | 0.200000 | 0.300000 | +0.100000 |
| contributing_precision | 0.200000 | 0.222222 | +0.022222 |
| contributing_recall | 1.000000 | 1.000000 | +0.000000 |
| contributing_f1 | 0.333333 | 0.363636 | +0.030303 |
| causal_reasoning_average | 1.000000 | 1.300000 | +0.300000 |

- Cases improved: CC-007
- Cases regressed: none
- Cases unchanged: CC-001, CC-002, CC-003, CC-004, CC-005, CC-009, CC-012, CC-014, CC-015
- Cases with changed predicted category: CC-007
- Tool calls: {'anchor_average_per_case': 4.9, 'candidate_average_per_case': 4.4, 'anchor_cases_with_one_or_two': [], 'candidate_cases_with_one_or_two': ['CC-012']}
- Execution failures: {'anchor': 0, 'candidate': 0}
- Runtime: {'anchor_wall_seconds': 793.079731, 'candidate_wall_seconds': 850.226785, 'anchor_summed_case_seconds': 792.990075, 'candidate_summed_case_seconds': 850.12984}
- Token usage: {'anchor': {'input_tokens': 1337676, 'input_tokens_details': {'cache_write_tokens': 275804, 'cached_tokens': 1053390}, 'output_tokens': 72493, 'output_tokens_details': {'reasoning_tokens': 7179}, 'total_tokens': 1410169}, 'candidate': {'input_tokens': 2401312, 'input_tokens_details': {'cache_write_tokens': 507811, 'cached_tokens': 1886135}, 'output_tokens': 60975, 'output_tokens_details': {'reasoning_tokens': 6850}, 'total_tokens': 2462287}}
- Estimated cost (when available): {'anchor': 3.284164, 'candidate': 4.542473}
