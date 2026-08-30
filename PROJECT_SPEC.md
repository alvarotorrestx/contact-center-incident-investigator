# Contact Center Incident Investigator — Project Spec

## Working Goal
Build an agentic contact-center operations system that investigates service-performance incidents, tests likely root-cause hypotheses against operational evidence, and produces an evidence-backed incident brief explaining what happened, why it happened, and what action should be taken.

## Primary User
Contact center operations analysts and managers responsible for monitoring service performance and investigating operational incidents.

## Secondary User
Executives and business stakeholders who need a concise, evidence-backed explanation of what happened, why it happened, and what action should be taken.

## Problem
Contact centers frequently experience unexpected degradation in service goals such as Service Level, Average Speed of Answer, and Abandon Rate. Determining the root cause requires analysts to correlate multiple operational signals—including call volume, AHT, staffing, adherence, routing behavior, transfers, forecasts, queue behavior, and system events. This makes incident investigation slow, manual, and inconsistent.

## Product Promise
An agentic workflow that:
1. Receives a reported service-performance incident.
2. Investigates relevant operational signals with deterministic tools.
3. Builds and updates explicit root-cause hypotheses.
4. Tests evidence for and against the leading hypotheses.
5. Uses a verifier to challenge the proposed diagnosis.
6. Produces a structured analyst result and stakeholder-ready incident brief.

## Hackathon MVP Architecture

### Frontend
- React
- Vite
- Single polished investigation experience
- No authentication or unnecessary frontend infrastructure

### Backend
- Python
- FastAPI
- pandas for deterministic data analysis where useful
- Pydantic for contracts and structured agent outputs
- LLM API with tool/function calling when agent stages are implemented

### Core Principle
Use the model for investigation decisions and interpretation.
Use deterministic Python code for arithmetic, aggregation, filtering, validation, scoring, and repeatable benchmark logic.

## Scope

### In Scope
- Synthetic contact-center benchmark data.
- 15-minute interval operational data.
- Center-level and queue-level performance.
- Staffing/adherence data.
- Forecast data.
- Operational event logs.
- Root-cause investigation.
- Evidence-backed conclusions.
- Verification/revision loop.
- Analyst and stakeholder output.
- Trajectory logging.
- Deterministic evaluation.
- Lightweight React/Vite demo UI backed by FastAPI.

### Out of Scope for Hackathon MVP
- Real company/customer data.
- Authentication.
- Production integrations with Genesys, NICE, Five9, Salesforce, etc.
- Database persistence unless a concrete requirement emerges.
- Long-term memory.
- Vector databases/RAG unless an observed failure justifies them.
- MCP unless an observed need justifies it.
- Autonomous consequential actions.
- Full enterprise deployment.
- Multi-page SaaS navigation or elaborate design systems.

## Synthetic Contact Center Assumptions
- Service Level target: 80% answered within 30 seconds.
- Service Level benchmark definition: answered within threshold / (offered calls - short abandons).
- Evaluation window: approximately 4 hours per case.
- Interval size: 15 minutes.
- Fictional queues:
  - General Service
  - Billing
  - Account Support
  - Escalations

## Data Sources Per Incident

### incident_metadata.json
- incident_id
- date
- window_start
- window_end
- incident_start
- alert
- service_level_target
- service_level_seconds

### performance.csv
- timestamp
- offered_calls
- answered_calls
- answered_within_threshold
- abandoned_calls
- short_abandoned_calls
- service_level_pct
- asa_seconds
- aht_seconds
- transfer_rate_pct

### staffing.csv
- timestamp
- scheduled_agents
- logged_in_agents
- productive_agents
- adherence_pct
- occupancy_pct
- agents_in_training

### forecast.csv
- timestamp
- forecast_offered_calls
- forecast_aht_seconds
- required_agents

### queue_performance.csv
- timestamp
- queue_name
- offered_calls
- answered_calls
- service_level_pct
- asa_seconds
- aht_seconds
- transfer_rate_pct
- staffed_agents

### events.json
- timestamp
- event_type
- scope
- description

## Root-Cause Taxonomy
- DEMAND_SPIKE
- STAFFING_SHORTFALL
- HANDLE_TIME_INCREASE
- ROUTING_CHANGE
- QUEUE_IMBALANCE
- ADHERENCE_DROP
- TRAINING_CAPACITY_LOSS
- PLATFORM_INCIDENT
- FORECAST_ERROR
- DATA_QUALITY
- MULTIFACTOR
- NO_MATERIAL_INCIDENT

## Expected Final Output Contract
The baseline and final system must return the same structured schema.

```json
{
  "incident_id": "CC-015",
  "investigation_status": "CONFIRMED",
  "primary_root_cause_category": "ROUTING_CHANGE",
  "primary_root_cause_detail": "A routing deployment increased unnecessary transfers and elevated handle time.",
  "contributing_factors": ["moderate_volume_increase"],
  "confidence": 0.93,
  "evidence": [
    {
      "signal": "routing_deployment",
      "source": "events",
      "finding": "A routing deployment occurred immediately before degradation."
    }
  ],
  "rejected_hypotheses": [
    {
      "category": "STAFFING_SHORTFALL",
      "reason": "Productive staffing remained near baseline."
    }
  ],
  "causal_chain": [
    "routing change",
    "increased transfers",
    "increased AHT",
    "reduced throughput",
    "queue growth",
    "service level decline"
  ],
  "recommended_actions": [
    "Review or roll back the routing configuration.",
    "Validate affected queue mappings.",
    "Monitor transfer rate and AHT after remediation."
  ],
  "stakeholder_summary": "..."
}
```

`investigation_status` must be one of `CONFIRMED`, `LIKELY`, or `INCONCLUSIVE`.
Evidence signals, contributing factors, and causal-chain concepts use the canonical
identifiers defined by the shared output contract so deterministic evaluation does
not depend on free-text matching.

## Root-Cause Reasoning Rule
Prefer the deepest cause supported by available evidence rather than merely naming an intermediate symptom.

Example:
routing deployment -> transfers increase -> AHT increases -> throughput falls -> queue grows -> Service Level declines

In that chain, high AHT is a mechanism, while the routing change is the deepest supported cause.

## Agent Termination Criteria
A diagnosis may be proposed when:
1. There is a leading root-cause hypothesis.
2. At least two independent pieces of evidence support it.
3. Major plausible alternatives have been evaluated.
4. The proposed cause occurs before or reasonably explains the observed effects.
5. No unresolved critical contradiction remains.

Allowed investigation statuses:
- CONFIRMED
- LIKELY
- INCONCLUSIVE

## MVP Priority
The project should be impressive through reasoning, evidence, evaluation, and reproducibility—not through infrastructure breadth.
