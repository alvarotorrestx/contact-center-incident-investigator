# Representative Agent Trajectories

These four intentionally selected trajectories show the main experimental story without requiring
judges to inspect every official run artifact:

- [`stage0-cc001.jsonl`](stage0-cc001.jsonl) — the winning default: a compact two-step,
  complete-context analysis of CC-001.
- [`v1-cc001.jsonl`](v1-cc001.jsonl) — a representative failure in which shallow tool use led to
  premature finalization.
- [`v2-cc001.jsonl`](v2-cc001.jsonl) — a structured deep investigation with deterministic tools,
  hypothesis-ledger state, evidence tracking, and a richer audit history.
- [`v3-cc007.jsonl`](v3-cc007.jsonl) — the removed verifier experiment, showing repeated verifier
  challenges and revisions that still failed to improve the final diagnosis.

The complete official trajectory sets remain available under [`trajectories/curated/`](../curated/).
