# Codex Project Instructions

## Source of Truth

Before making architectural or implementation decisions, read:

- PROJECT_SPEC.md
- EVALUATION_PLAN.md
- ARCHITECTURE.md
- CHANGELOG.md

If `TONIGHT_PLAN.md` is present locally, it is an internal execution aid only. It is intentionally gitignored and is not part of the public project specification.

The project documents above define the intended product, benchmark, evaluation methodology, and agent architecture.

## Authorization State: V2 COMPLETE — AWAITING V3 APPROVAL

Stage 0 is frozen and complete. V1 tool-use and V2 structured-hypothesis implementations and their
measured ten-case experiments are complete. The project is awaiting explicit approval to begin V3.

V3 and all later implementation remain **NO-GO** without explicit user approval. V2 was limited to
a structured hypothesis ledger, evidence-for/evidence-against tracking, explicit competing-
hypothesis evaluation, termination discipline, hypothesis trajectories, the configuration-matched
ten-case experiment, and minimal supporting integration/documentation.

Do not add a verifier, verifier feedback, a revision loop, multi-agent voting, or later-stage UI work
without explicit approval. V2 did not authorize changing the frozen benchmark, ground truth,
scoring behavior, taxonomy, output schema, baseline behavior, model configuration, or historical
experimental artifacts.

## Strict GO / NO-GO Phase Gates

This project uses explicit phase gates.

Never begin a phase merely because the previous one was completed.

Only begin implementation after an explicit user instruction such as:
- `GO to Stage 0`
- `Proceed with V1`
- `Approved — continue with the verifier`

Ambiguous encouragement is not approval to advance phases.

At the end of every implementation phase:

1. Stop implementation.
2. Run relevant tests and validation.
3. Summarize what was implemented.
4. Report exact test/benchmark results.
5. Report known problems, assumptions, or compromises.
6. List important files changed.
7. State the next proposed phase.
8. WAIT for explicit user approval.

Do not silently continue into the next phase.

## Stage Definitions

### Stage 0 — Foundation + Fair Baseline
Stage 0 may begin only after explicit approval.

Includes:
- repository/bootstrap structure
- Python + FastAPI backend foundation
- React + Vite frontend foundation only as needed for the eventual app
- deterministic synthetic benchmark generator
- hidden ground-truth files
- deterministic evaluation/scoring harness
- trajectory/result persistence
- fair single-agent baseline

Stage 0 does **not** include:
- hypothesis ledger
- verifier agent
- revision loop
- polished final investigation UI
- later experimental stages

### V1 — Tool-Using Investigator
Only after explicit approval:
- deterministic analysis tools
- iterative agent tool selection
- benchmark rerun and evidence capture

### V2 — Structured Hypothesis Investigation
Only after explicit approval:
- explicit hypothesis ledger
- evidence-for / evidence-against tracking
- alternative hypothesis evaluation
- benchmark rerun and evidence capture

### V3 — Adversarial Verification
Only after explicit approval:
- verifier agent
- contradiction search
- bounded revision loop
- benchmark rerun and evidence capture

### V4 — Product Quality
Only after explicit approval:
- polished React/Vite incident investigation experience
- analyst/stakeholder report presentation
- trajectory/progress visualization
- final benchmark regression run

## Approved Technical Direction

Prefer:
- React + Vite frontend
- Python + FastAPI backend
- pandas where useful for deterministic analysis
- Pydantic for structured contracts
- an LLM API with tool/function calling once agent stages are authorized

Do not introduce additional infrastructure without a concrete demonstrated need.

Avoid by default:
- databases
- Redis
- queues/workers
- Docker unless it materially improves reproducibility within the available time
- LangChain/LangGraph unless the project clearly benefits
- MCP
- RAG/vector databases
- long-term memory
- authentication
- multi-agent swarms
- elaborate frontend state-management libraries

## Engineering Rules

- Optimize for a working, explainable hackathon MVP.
- Prefer simple and understandable implementations.
- Never expose hidden ground-truth files or labels to the agent.
- Baseline and later systems must use the same benchmark, root-cause taxonomy, required output schema, and—when comparing agent quality—the same underlying model/configuration unless a documented experiment explicitly changes a resource.
- Never fabricate benchmark results.
- Preserve actual experiment outputs and representative failures.
- Do not write fake values into CHANGELOG.md.
- Use deterministic code for calculations, aggregation, filtering, metric validation, and scoring whenever practical.
- Keep credentials, API keys, private data, and local secrets out of source control.
- Treat synthetic benchmark generation as production-quality evaluation code: deterministic, inspectable, and reproducible.
- Prefer the deepest evidence-supported root cause over intermediate symptoms.
- The final reporting layer may summarize verified findings but must not invent new evidence.

## Frontend Rules

The React frontend is intentionally small.

For the MVP, optimize around one polished incident-investigation flow rather than a broad SaaS shell.

Do not add:
- authentication
- settings/account pages
- unnecessary routing
- dashboards unrelated to the core demo
- elaborate component systems

unless explicitly approved.

## Evaluation Rules

The headline benchmark is Root-Cause Identification Accuracy (RCIA).

The primary score must remain deterministic and auditable:
`predicted_category == expected_category`

Do not replace the headline metric with an LLM-as-judge score.

## .gitignore

The repository includes a deliberate `.gitignore`.

You may propose or add standard ignore patterns when new tools/build outputs require them.

Do not remove the `TONIGHT_PLAN.md` ignore rule unless the user explicitly requests that file be committed.
