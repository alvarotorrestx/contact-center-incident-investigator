# V1 Comparison to Pinned Stage 0 Anchor

- Anchor run: `02b97b0d-d68e-45f8-b678-386f7558dd02`
- Candidate run: `7fcf7453-609e-4006-8a72-cd1a6b26bcff`
- Model: `gpt-5.6-sol`
- Model configuration: `{"reasoning_effort": "medium", "sampling_parameters": "provider_defaults"}`

| Metric | Anchor | V1 | Delta |
|---|---:|---:|---:|
| rcia | 0.900000 | 0.500000 | -0.400000 |
| evidence_coverage | 0.875000 | 0.425000 | -0.450000 |
| non_allowlisted_evidence_rate | 0.407895 | 0.441860 | +0.033966 |
| contributing_exact_accuracy | 0.200000 | 0.700000 | +0.500000 |
| contributing_precision | 0.200000 | 0.250000 | +0.050000 |
| contributing_recall | 1.000000 | 0.500000 | -0.500000 |
| contributing_f1 | 0.333333 | 0.333333 | -0.000000 |
| causal_reasoning_average | 1.800000 | 0.800000 | -1.000000 |

- Cases improved: none
- Cases regressed: CC-001, CC-007, CC-009, CC-015
- Cases unchanged: CC-002, CC-003, CC-004, CC-005, CC-012, CC-014
- Execution failures: {'anchor': 0, 'candidate': 0}
- Runtime: {'anchor_wall_seconds': 230.383888, 'candidate_wall_seconds': 175.694609, 'anchor_summed_case_seconds': 230.225395, 'candidate_summed_case_seconds': 175.618674}
- Token usage: {'anchor': {'input_tokens': 134410, 'input_tokens_details': {'cache_write_tokens': 134380, 'cached_tokens': 0}, 'output_tokens': 18362, 'output_tokens_details': {'reasoning_tokens': 7403}, 'total_tokens': 152772}, 'candidate': {'input_tokens': 158153, 'input_tokens_details': {'cache_write_tokens': 48522, 'cached_tokens': 108348}, 'output_tokens': 15226, 'output_tokens_details': {'reasoning_tokens': 1970}, 'total_tokens': 173379}}
- Estimated cost (when available): {'anchor': 1.03926, 'candidate': 0.5956012}
