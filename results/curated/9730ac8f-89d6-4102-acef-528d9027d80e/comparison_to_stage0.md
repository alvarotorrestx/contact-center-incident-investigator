# Final Candidate Comparison to Pinned Stage 0 Anchor

- Anchor run: `02b97b0d-d68e-45f8-b678-386f7558dd02`
- Candidate run: `9730ac8f-89d6-4102-acef-528d9027d80e`
- Model: `gpt-5.6-sol`
- Model configuration: `{"reasoning_effort": "medium", "sampling_parameters": "provider_defaults"}`

| Metric | Pinned Stage 0 Anchor | Final Candidate | Delta |
|---|---:|---:|---:|
| rcia | 0.900000 | 0.800000 | -0.100000 |
| evidence_coverage | 0.875000 | 0.775000 | -0.100000 |
| non_allowlisted_evidence_rate | 0.407895 | 0.396825 | -0.011069 |
| contributing_exact_accuracy | 0.200000 | 0.300000 | +0.100000 |
| contributing_precision | 0.200000 | 0.222222 | +0.022222 |
| contributing_recall | 1.000000 | 1.000000 | +0.000000 |
| contributing_f1 | 0.333333 | 0.363636 | +0.030303 |
| causal_reasoning_average | 1.800000 | 1.300000 | -0.500000 |

- Cases improved: none
- Cases regressed: CC-014
- Cases unchanged: CC-001, CC-002, CC-003, CC-004, CC-005, CC-007, CC-009, CC-012, CC-015
- Cases with changed predicted category: CC-014
- Tool calls: {'anchor_average_per_case': 0.0, 'candidate_average_per_case': 4.4, 'anchor_cases_with_one_or_two': [], 'candidate_cases_with_one_or_two': ['CC-012']}
- Execution failures: {'anchor': 0, 'candidate': 0}
- Runtime: {'anchor_wall_seconds': 230.383888, 'candidate_wall_seconds': 850.226785, 'anchor_summed_case_seconds': 230.225395, 'candidate_summed_case_seconds': 850.12984}
- Token usage: {'anchor': {'input_tokens': 134410, 'input_tokens_details': {'cache_write_tokens': 134380, 'cached_tokens': 0}, 'output_tokens': 18362, 'output_tokens_details': {'reasoning_tokens': 7403}, 'total_tokens': 152772}, 'candidate': {'input_tokens': 2401312, 'input_tokens_details': {'cache_write_tokens': 507811, 'cached_tokens': 1886135}, 'output_tokens': 60975, 'output_tokens_details': {'reasoning_tokens': 6850}, 'total_tokens': 2462287}}
- Estimated cost (when available): {'anchor': 1.03926, 'candidate': 4.542473}
