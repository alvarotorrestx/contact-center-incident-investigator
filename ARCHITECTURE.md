# Agent Architecture

## Design Philosophy
Purposeful components only. Add architecture when it addresses an observed failure.

The React/Vite frontend is a presentation layer only. Agent reasoning, deterministic analysis tools, benchmark execution, and evaluation live in the Python/FastAPI backend.

## A. Final Default Product Architecture

The measured winning default is the Stage 0 complete-context single-stage structured analyst. It
scored 9/10 RCIA, outperforming every more agentic configuration tested.

```text
React/Vite UI
     |
     v
FastAPI API
     |
     v
Complete visible incident context
     |
     v
Single-stage structured analyst
     |
     v
Structured diagnosis/report
     |
     v
React UI
```

## B. Optional Deep-Investigation / Audit Mode

The V2 workflow remains available when an analyst explicitly needs deeper deterministic drill-down
or a richer audit trail.

```text
Complete visible incident context
     |
     v
V2 structured investigator
     |
     +--> deterministic tools
     |
     +--> hypothesis ledger
     |
     v
Structured diagnosis / audit trail
```

This path is retained for auditability and deeper investigation, but it is not the default because
its 7/10 RCIA did not beat the Stage 0 anchor and it required substantially more runtime, tokens,
and estimated cost.

## C. V4 Product Presentation Boundary

V4 adds a presentation layer without changing either reasoning path. The primary screen loads one
frozen incident at a time and presents operational impact, diagnosis, evidence, causal chain,
contributors, rejected alternatives, actions, stakeholder brief, and a concise public trajectory.

```text
Frozen visible case tables ----> deterministic presentation summaries --+
                                                                        |
Curated structured diagnosis --> public report service ----------------+--> React UI
                                                                        |
Curated public trajectory -----> trajectory sanitizer -----------------+

Run live analysis -------------> existing Stage 0 API --------------------> React UI
```

The default demo report uses the official configuration-matched Stage 0 anchor. The optional Deep
Investigation view reads the preserved official V2 diagnosis and public trajectory, including
deterministic tool decisions and structured ledger states. It is an auditability/drill-down mode,
not an accuracy tier, and it does not activate V3 verification or adaptive escalation.

The report service imports no evaluator module and reads operational summaries only from
`AgentVisibleCaseLoader`. It returns no scores, expected causes/evidence/contributors/chains,
supported-signal allowlists, or evaluator metadata. Raw response identifiers, prompt hashes,
token accounting, and private reasoning are also omitted from the public trajectory. Live product
requests continue to use the unchanged Stage 0 `baseline` endpoint and contract.

## D. Removed Experiment Summary

The V3 adversarial verifier is not part of the final product architecture. It corrected no
diagnosis, left RCIA unchanged from V2 at 7/10, and added substantial runtime, token, and cost
overhead. Its design and measured evidence remain documented below for auditability.

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

## Experimental Tool-Using Investigator
The sections below document the V1–V3 experiments and the retained optional V2 audit mode; they do
not replace the final default architecture above.

Goal: determine what caused the incident and prove it.

Responsibilities:
1. Understand the reported service impact.
2. Decide which operational signals to inspect.
3. Call deterministic tools.
4. Create/update explicit hypotheses.
5. Seek evidence for and against plausible causes.
6. Distinguish symptoms from deeper supported causes.
7. Propose a diagnosis only after termination criteria are met.

### V1 Implementation Boundary

V1 implements only deterministic read-only tools and a bounded iterative investigator. The
investigator receives incident metadata, shared taxonomy/catalogs, metric definitions, and the
unchanged final schema in its initial prompt. Unlike the Stage 0 baseline, raw visible interval
tables are not serialized initially; the same underlying visible data is made available through
strict tools over an already-loaded `VisibleCase`.

V1 permits at most 10 operational tool calls per case and records public action rationales, validated
arguments, structured results, durations, usage, final output, and termination reason. It does not
maintain a hypothesis ledger or evidence-for/evidence-against state and has no verifier or revision
loop.

The completed V1 run `7fcf7453-609e-4006-8a72-cd1a6b26bcff` scored 5/10 RCIA versus the pinned
9/10 baseline. The tool and trajectory infrastructure is retained for later controlled experiments,
but the current V1 stopping/investigation policy is not promoted over the baseline: eight cases
stopped after one or two calls and often failed to gather enough independent evidence.

### V2 Implementation Boundary

V2 adds a typed, agent-visible hypothesis ledger on a separate workflow path while retaining the
unchanged V1 operational tools. The model initializes three to six plausible categories, records
status/confidence/evidence-for/evidence-against, and updates the complete ledger after every
operational tool result. The runner blocks a normal final answer unless one hypothesis is uniquely
leading, has two distinct supporting signals from at least two called tools, at least two competing
hypotheses have evidence-based evaluation, causal timing is supported, and no critical
contradiction remains. At the unchanged ten-call limit, unmet criteria require `INCONCLUSIVE`.

V2 trajectories add before/after ledger snapshots, structured status/confidence/evidence changes,
rejected proposed states, and premature-completion blocks. They record concise public summaries,
not private chain-of-thought. V2 contains no verifier, verifier call, verifier feedback, or revision
loop.

Official run `d3859d8d-b252-426a-970e-89a471a5fe7c` completed 10/10 cases with zero failures and
scored 7/10 RCIA. It improved on V1's 5/10 and increased expected-evidence coverage from 17/40 to
34/40; no case stopped after one or two tools. It remained below the pinned Stage 0 baseline's
9/10, required 49 tools and 1,410,169 tokens, and produced nine recoverable rejected-ledger
updates. Keep the structured hypothesis discipline as the stronger tool-using workflow, but do not
promote it over the Stage 0 baseline on quality, latency, or cost.

### Final Candidate Experiment

The final candidate retains the V2 deterministic tools, typed ledger, evidence-for/evidence-against
tracking, termination discipline, and trajectories, but supplies the complete `VisibleCase` in the
initial request exactly as the Stage 0 baseline does. Tools remain available for deterministic
calculation, comparison, drill-down, and validation. The V3 verifier and revision loop are disabled.

Official run `9730ac8f-89d6-4102-acef-528d9027d80e` completed 10/10 cases with zero failures and
scored 8/10 RCIA. It corrected CC-007 relative to V2 with no RCIA regression versus V2 and reduced
average tools from 4.9 to 4.4, but it remained below the Stage 0 baseline's 9/10 and regressed
CC-014 relative to that anchor. The default final reasoning architecture should therefore remain
the complete-context single-stage structured analyst. Retain tools, the ledger workflow, and rich
trajectories as an optional deep-investigation/audit path. Do not retain the V3 verifier.

### Adaptive Escalation Experiment

The final pre-V4 reasoning experiment keeps the Stage 0 complete-context structured analyst as the
first pass and selectively invokes the preserved V2 complete-context tool/ledger workflow. The
adaptive path has system version `adaptive_escalation`; it has no verifier and no revision loop.

The deterministic gate is frozen as `adaptive_gate_1` before the official run. It escalates when
one or more of these generic checks triggers:

1. the first-pass status is `INCONCLUSIVE`;
2. first-pass confidence is below `0.70`;
3. structured support contains fewer than two distinct canonical evidence signals or fewer than
   two distinct visible sources;
4. visible counts fail `offered = answered + abandoned`, or recalculated service level differs
   from the reported value by more than `1.0` percentage point in any interval;
5. an event-dependent diagnosis (`ROUTING_CHANGE`, `PLATFORM_INCIDENT`, or
   `TRAINING_CAPACITY_LOSS`) or structured routing/platform event claim has no matching visible
   event at or before incident onset.

The gate uses only the current first-pass `FinalDiagnosis` and already-loaded `VisibleCase`. It does
not read incident-specific rules, historical predictions, benchmark scores, ground truth,
supported-signal allowlists, or evaluator feedback. Direct cases preserve the first-pass diagnosis.
Escalated cases receive the complete visible case plus the first-pass diagnosis explicitly labeled
as an unverified starting hypothesis, then use V2 tools, ledger, termination discipline, and the
unchanged ten-call bound. The deep path may retain or revise the diagnosis solely from visible
evidence.

Official run `678d826d-8f74-43eb-9ce9-0157ebec8587` escalated only CC-012 on the hard visible-metric
consistency check. The deep path used five tools and retained the correct `DATA_QUALITY` category;
it corrected no first-pass category and harmed none. The system scored 8/10 RCIA, with CC-005 and
CC-014 incorrect, versus 9/10 for the Stage 0 anchor. It consumed 489,793 tokens, ran for 338.335
seconds, and cost an estimated $1.6058762. Selective escalation reduced cost and runtime materially
versus always-on V2, but it did not recover the Stage 0 quality anchor and cost more than Stage 0.
Preserve this as a measured negative experiment. The final default reasoning architecture remains
the Stage 0 complete-context single-stage analyst; V2 tools/ledger remain an optional audit path,
and V3 remains removed.

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
V2 maintains structured state after every operational tool result.

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

## Removed Experiment — Adversarial Verifier

This V3 component is preserved as historical experiment documentation only. It is not part of the
final product architecture because it corrected no diagnosis and added substantial runtime, token,
and cost overhead.

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

## Historical V3 Revision Limits
- Suggested maximum investigation tool calls: 10–12.
- Suggested maximum verifier-driven revisions: 2.
- Workflow must be able to return INCONCLUSIVE rather than loop indefinitely or invent certainty.

## Reporting Stage
Runs after the selected reasoning path finalizes its structured diagnosis. In the removed V3
experiment, it ran after verification/finalization.

It may not invent new findings.

Inputs:
- finalized structured diagnosis
- supporting evidence
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

## Completed Improvement Stages
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

Measured outcome: preserve V3 as a removed experiment; it did not improve V2.

### Final Candidate — Full Context + V2 Discipline
Supply every agent-visible table initially while retaining V2 tools, ledger, and termination
discipline. Measured outcome: 8/10 RCIA, better than V2 but below the 9/10 Stage 0 anchor.

### Adaptive Escalation — Complete-Context First Pass + Selective V2

Keep the Stage 0 presentation as the default and invoke complete-context V2 investigation only
when the frozen deterministic gate finds uncertainty, insufficient independent support, a hard
visible-data inconsistency, or a missing/late claimed causal event. Run one configuration-matched
ten-case experiment, then end reasoning-architecture experimentation regardless of the result.

Measured outcome: 8/10 RCIA with one escalation, below the Stage 0 anchor. Preserve the experiment
but do not promote it. No further reasoning-architecture experiment is planned or authorized.

### V4 — Product Quality
Delivered the polished React investigation experience and presentation improvements without
changing the measured reasoning decision.

At every phase, stop after tests and measured benchmark results and wait for explicit
approval before beginning the next phase. Keep the frozen benchmark, taxonomy, output
contract, model, and model configuration constant unless a separately documented
experiment intentionally changes one of those resources.
