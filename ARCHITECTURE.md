# Agent Architecture

## Design Philosophy
Purposeful components only. Add architecture when it addresses an observed failure.

The React/Vite frontend is a presentation layer only. Agent reasoning, deterministic analysis tools, benchmark execution, and evaluation live in the Python/FastAPI backend.

Target architecture:

```text
React/Vite UI
     |
     v
FastAPI API
     |
     v
Incident
   |
   v
Investigator Agent
   |
   +--> deterministic Python analysis tools
   |
   v
Hypothesis Ledger
   |
   v
Proposed Diagnosis
   |
   v
Verifier Agent
   |
   +--> VERIFIED --> Reporting Stage --> API response --> React UI
   |
   +--> REVISE ----> Investigator (bounded loop)
```

## Stage 0 — Baseline
One general-purpose contact-center operations analyst receives:
- incident metadata
- all available benchmark data
- root-cause taxonomy
- required output schema

It returns one diagnosis.

No:
- explicit hypothesis ledger
- dedicated verification step
- deliberate counter-evidence search
- multi-stage orchestration

This is intended to be a reasonable basic AI implementation, not a weak strawman.

## Investigator Agent
Goal: determine what caused the incident and prove it.

Responsibilities:
1. Understand the reported service impact.
2. Decide which operational signals to inspect.
3. Call deterministic tools.
4. Create/update explicit hypotheses.
5. Seek evidence for and against plausible causes.
6. Distinguish symptoms from deeper supported causes.
7. Propose a diagnosis only after termination criteria are met.

## Deterministic Python Tools
Initial tool set:

- get_performance_trends()
- compare_actual_vs_forecast()
- analyze_staffing()
- analyze_queue(queue_name)
- compare_queues()
- get_events(time_window=None, scope=None)
- calculate_metric_change(metric, time_window=None)
- recalculate_service_level()
- summarize_incident_window()

Principle:
Use the LLM for judgment and investigation decisions. Use deterministic code for arithmetic, aggregation, filtering, metric calculation, and scoring.

## Hypothesis Ledger
Maintain structured state.

Example:

```json
{
  "hypotheses": [
    {
      "category": "DEMAND_SPIKE",
      "status": "UNLIKELY",
      "confidence": 0.22,
      "evidence_for": ["Volume increased 8.7%"],
      "evidence_against": [
        "Increase is modest relative to degradation",
        "A larger transfer/AHT shift follows a routing event"
      ]
    },
    {
      "category": "ROUTING_CHANGE",
      "status": "LIKELY",
      "confidence": 0.88,
      "evidence_for": [
        "Routing deployment occurred before degradation",
        "Transfer rate increased materially",
        "AHT increased after transfers rose"
      ],
      "evidence_against": []
    }
  ]
}
```

Suggested statuses:
- UNTESTED
- POSSIBLE
- LIKELY
- UNLIKELY
- REJECTED

## Verifier Agent
Goal: try to disprove the proposed diagnosis rather than solve the incident from scratch.

Checks:
1. Does the claimed cause occur before or explain the observed effect?
2. Is the supporting evidence actually present?
3. Is there contradictory evidence?
4. Does another hypothesis explain the incident better?
5. Is a claimed root cause merely an intermediate symptom?
6. Are contributing factors being confused with the primary cause?

Verifier result:

```json
{
  "verification_status": "VERIFIED",
  "critical_contradictions": [],
  "recommended_revision": null
}
```

or

```json
{
  "verification_status": "REVISE",
  "critical_contradictions": [
    "The demand increase is too small to explain the severity.",
    "A routing event precedes a much larger transfer/AHT shift."
  ],
  "recommended_revision": "Reevaluate ROUTING_CHANGE as the primary root cause."
}
```

## Revision Limits
- Suggested maximum investigation tool calls: 10–12.
- Suggested maximum verifier-driven revisions: 2.
- Workflow must be able to return INCONCLUSIVE rather than loop indefinitely or invent certainty.

## Reporting Stage
Runs only after verification/finalization.

It may not invent new findings.

Inputs:
- verified structured diagnosis
- verified evidence
- contributing factors
- rejected hypotheses
- causal chain
- remediation recommendations

Outputs:
1. Detailed analyst view.
2. Concise stakeholder view.

## Frontend Contract
The React/Vite UI should remain deliberately small for the MVP.

Primary demo screen should show:
- incident summary and impact
- investigation progress/trajectory
- hypothesis states or key investigation steps
- primary root cause
- confidence
- supporting evidence
- rejected alternatives
- causal chain
- recommended actions
- stakeholder summary

Avoid:
- authentication
- settings systems
- multi-page navigation unless essential
- complex global state libraries unless demonstrably needed
- production design-system work

## Trajectory Logger
Log from the first working version.

Recommended fields:
- run_id
- incident_id
- system_version
- model
- agent/stage
- step_number
- agent_decision summary
- tool_called
- tool_arguments
- tool_result
- hypothesis_state
- verification_feedback
- final_output
- duration
- token_usage
- estimated_cost

Store representative trajectories in a human-readable form for submission.

## Planned Improvement Stages
### V0 — Baseline
Single general-purpose analyst.

### V1 — Tool-Using Investigator
Add deterministic read-only analysis tools, a bounded iterative tool-using investigator,
and trajectory capture for tool decisions. Do not add a hypothesis ledger, verifier, or
revision loop in V1.

### V2 — Structured Hypothesis Investigation
Add an explicit hypothesis ledger and evidence-for/evidence-against tracking. Benchmark
against the same frozen, configuration-matched anchor.

### V3 — Adversarial Verification
Add an adversarial verifier and bounded verifier-driven revision loop. Benchmark against
the same frozen, configuration-matched anchor.

### V4 — Product Quality
Add the polished React investigation experience and presentation improvements.

At every phase, stop after tests and measured benchmark results and wait for explicit
approval before beginning the next phase. Keep the frozen benchmark, taxonomy, output
contract, model, and model configuration constant unless a separately documented
experiment intentionally changes one of those resources.
