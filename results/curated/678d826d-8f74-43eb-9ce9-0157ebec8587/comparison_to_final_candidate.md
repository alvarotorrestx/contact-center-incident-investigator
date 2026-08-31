# Adaptive Escalation Comparison to Complete-Context Agentic Candidate

- Anchor run: `9730ac8f-89d6-4102-acef-528d9027d80e`
- Candidate run: `678d826d-8f74-43eb-9ce9-0157ebec8587`
- Model: `gpt-5.6-sol`
- Model configuration: `{"reasoning_effort": "medium", "sampling_parameters": "provider_defaults"}`

| Metric | Complete-Context Agentic Candidate | Adaptive Escalation | Delta |
|---|---:|---:|---:|
| rcia | 0.800000 | 0.800000 | +0.000000 |
| evidence_coverage | 0.775000 | 0.900000 | +0.125000 |
| non_allowlisted_evidence_rate | 0.396825 | 0.425000 | +0.028175 |
| contributing_exact_accuracy | 0.300000 | 0.400000 | +0.100000 |
| contributing_precision | 0.222222 | 0.250000 | +0.027778 |
| contributing_recall | 1.000000 | 1.000000 | +0.000000 |
| contributing_f1 | 0.363636 | 0.400000 | +0.036364 |
| causal_reasoning_average | 1.300000 | 1.500000 | +0.200000 |

- Cases improved: none
- Cases regressed: none
- Cases unchanged: CC-001, CC-002, CC-003, CC-004, CC-005, CC-007, CC-009, CC-012, CC-014, CC-015
- Cases with changed predicted category: none
- Tool calls: {'anchor_average_per_case': 4.4, 'candidate_average_per_case': 0.5, 'anchor_cases_with_one_or_two': ['CC-012'], 'candidate_cases_with_one_or_two': []}
- Execution failures: {'anchor': 0, 'candidate': 0}
- Runtime: {'anchor_wall_seconds': 850.226785, 'candidate_wall_seconds': 338.334615, 'anchor_summed_case_seconds': 850.12984, 'candidate_summed_case_seconds': 338.261785}
- Token usage: {'anchor': {'input_tokens': 2401312, 'input_tokens_details': {'cache_write_tokens': 507811, 'cached_tokens': 1886135}, 'output_tokens': 60975, 'output_tokens_details': {'reasoning_tokens': 6850}, 'total_tokens': 2462287}, 'candidate': {'input_tokens': 463866, 'input_tokens_details': {'cache_write_tokens': 195333, 'cached_tokens': 267628}, 'output_tokens': 25927, 'output_tokens_details': {'reasoning_tokens': 7536}, 'total_tokens': 489793}}
- Estimated cost (when available): {'anchor': 4.542473, 'candidate': 1.6058762}
