# Final Candidate Comparison to V3

- Anchor run: `5324184e-c646-456c-b58b-8e1c2e89a2fc`
- Candidate run: `9730ac8f-89d6-4102-acef-528d9027d80e`
- Model: `gpt-5.6-sol`
- Model configuration: `{"reasoning_effort": "medium", "sampling_parameters": "provider_defaults"}`

| Metric | V3 | Final Candidate | Delta |
|---|---:|---:|---:|
| rcia | 0.700000 | 0.800000 | +0.100000 |
| evidence_coverage | 0.825000 | 0.775000 | -0.050000 |
| non_allowlisted_evidence_rate | 0.417910 | 0.396825 | -0.021085 |
| contributing_exact_accuracy | 0.300000 | 0.300000 | +0.000000 |
| contributing_precision | 0.222222 | 0.222222 | +0.000000 |
| contributing_recall | 1.000000 | 1.000000 | +0.000000 |
| contributing_f1 | 0.363636 | 0.363636 | +0.000000 |
| causal_reasoning_average | 0.900000 | 1.300000 | +0.400000 |

- Cases improved: CC-007
- Cases regressed: none
- Cases unchanged: CC-001, CC-002, CC-003, CC-004, CC-005, CC-009, CC-012, CC-014, CC-015
- Cases with changed predicted category: CC-007
- Tool calls: {'anchor_average_per_case': 6.0, 'candidate_average_per_case': 4.4, 'anchor_cases_with_one_or_two': [], 'candidate_cases_with_one_or_two': ['CC-012']}
- Execution failures: {'anchor': 0, 'candidate': 0}
- Runtime: {'anchor_wall_seconds': 1421.932136, 'candidate_wall_seconds': 850.226785, 'anchor_summed_case_seconds': 1421.85583, 'candidate_summed_case_seconds': 850.12984}
- Token usage: {'anchor': {'input_tokens': 2153092, 'input_tokens_details': {'cache_write_tokens': 622391, 'cached_tokens': 1520427}, 'output_tokens': 106632, 'output_tokens_details': {'reasoning_tokens': 15492}, 'total_tokens': 2259724}, 'candidate': {'input_tokens': 2401312, 'input_tokens_details': {'cache_write_tokens': 507811, 'cached_tokens': 1886135}, 'output_tokens': 60975, 'output_tokens_details': {'reasoning_tokens': 6850}, 'total_tokens': 2462287}}
- Estimated cost (when available): {'anchor': 5.8938618, 'candidate': 4.542473}
