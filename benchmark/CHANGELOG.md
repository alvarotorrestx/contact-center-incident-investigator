# Benchmark Changelog

## v1 pre-freeze calibration

- Generator 1.0.1 increases normal queue staffing and recalibrates the within-threshold response
  curve so every case begins from a center-level service level above the documented 80% target.
- A validator now rejects any case whose pre-incident mean misses that target.
- This defect was found during Stage 0 data-quality review before any model prediction or live
  benchmark run. No case was changed in response to agent performance.

