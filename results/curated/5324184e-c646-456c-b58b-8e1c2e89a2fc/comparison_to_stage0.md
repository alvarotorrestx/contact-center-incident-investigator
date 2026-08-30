# V3 Comparison to Pinned Stage 0 Anchor

- Anchor run: `02b97b0d-d68e-45f8-b678-386f7558dd02`
- Candidate run: `5324184e-c646-456c-b58b-8e1c2e89a2fc`
- Model: `gpt-5.6-sol`
- Model configuration: `{"reasoning_effort": "medium", "sampling_parameters": "provider_defaults"}`

| Metric | Pinned Stage 0 Anchor | V3 | Delta |
|---|---:|---:|---:|
| rcia | 0.900000 | 0.700000 | -0.200000 |
| evidence_coverage | 0.875000 | 0.825000 | -0.050000 |
| non_allowlisted_evidence_rate | 0.407895 | 0.417910 | +0.010016 |
| contributing_exact_accuracy | 0.200000 | 0.300000 | +0.100000 |
| contributing_precision | 0.200000 | 0.222222 | +0.022222 |
| contributing_recall | 1.000000 | 1.000000 | +0.000000 |
| contributing_f1 | 0.333333 | 0.363636 | +0.030303 |
| causal_reasoning_average | 1.800000 | 0.900000 | -0.900000 |

- Cases improved: none
- Cases regressed: CC-007, CC-014
- Cases unchanged: CC-001, CC-002, CC-003, CC-004, CC-005, CC-009, CC-012, CC-015
- Cases with changed predicted category: CC-007, CC-014
- Tool calls: {'anchor_average_per_case': 0.0, 'candidate_average_per_case': 6.0, 'anchor_cases_with_one_or_two': [], 'candidate_cases_with_one_or_two': []}
- Execution failures: {'anchor': 0, 'candidate': 0}
- Runtime: {'anchor_wall_seconds': 230.383888, 'candidate_wall_seconds': 1421.932136, 'anchor_summed_case_seconds': 230.225395, 'candidate_summed_case_seconds': 1421.85583}
- Token usage: {'anchor': {'input_tokens': 134410, 'input_tokens_details': {'cache_write_tokens': 134380, 'cached_tokens': 0}, 'output_tokens': 18362, 'output_tokens_details': {'reasoning_tokens': 7403}, 'total_tokens': 152772}, 'candidate': {'input_tokens': 2153092, 'input_tokens_details': {'cache_write_tokens': 622391, 'cached_tokens': 1520427}, 'output_tokens': 106632, 'output_tokens_details': {'reasoning_tokens': 15492}, 'total_tokens': 2259724}}
- Estimated cost (when available): {'anchor': 1.03926, 'candidate': 5.8938618}
