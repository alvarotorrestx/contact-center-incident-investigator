export interface IncidentSummary {
  incident_id: string
  date: string
  window_start: string
  window_end: string
  incident_start: string
  alert: string
}

export interface Diagnosis {
  incident_id: string
  investigation_status: 'CONFIRMED' | 'LIKELY' | 'INCONCLUSIVE'
  primary_root_cause_category: string
  primary_root_cause_detail: string
  confidence: number
  evidence: Array<{ signal: string; source: string; finding: string }>
  contributing_factors: string[]
  rejected_hypotheses: Array<{ category: string; reason: string }>
  causal_chain: string[]
  recommended_actions: string[]
  stakeholder_summary: string
}

export type InvestigationMode = 'default' | 'audit'

export interface ImpactKpi {
  id: string
  label: string
  value: number | null
  unit: string
  delta: number | null
  delta_unit: string | null
  context: string
  tone: 'positive' | 'negative' | 'neutral'
}

export interface QueueImpact {
  queue_name: string
  service_level_pct: number | null
  service_level_delta_pp: number | null
  asa_seconds: number | null
  aht_seconds: number | null
  transfer_rate_pct: number | null
  staffed_agents: number | null
  volume_delta_pct: number | null
}

export interface TrendPoint {
  timestamp: string
  service_level_pct: number
  asa_seconds: number
  abandonment_rate_pct: number
  offered_calls: number
  forecast_offered_calls: number
  productive_agents: number
  is_incident_period: boolean
}

export interface TrajectoryItem {
  step: number
  type: 'started' | 'decision' | 'tool' | 'hypothesis' | 'guardrail' | 'complete'
  title: string
  summary: string
  timestamp?: string
  tool?: string
  tools?: string[]
  arguments?: Record<string, unknown>
  changes?: Array<{ category: string; status: string; confidence: number }>
  termination_reason?: string
}

export interface Hypothesis {
  category: string
  status: string
  confidence: number
  evidence_for: Array<{ signal: string; finding: string }>
  evidence_against: Array<{ signal: string; finding: string }>
}

export interface DemoReport {
  mode: {
    id: InvestigationMode
    label: string
    description: string
    run_id: string
    is_default: boolean
  }
  incident: IncidentSummary & {
    service_level_seconds: number
    service_level_target: number
  }
  impact: {
    impacted_queues: string[]
    kpis: ImpactKpi[]
    queues: QueueImpact[]
    trend: TrendPoint[]
    staffing_context: {
      productive_agents: number | null
      productive_agent_delta: number | null
      occupancy_pct: number | null
    }
    forecast_context: {
      actual_calls: number
      forecast_calls: number
      variance_pct: number | null
    }
    events: Array<Record<string, unknown>>
  }
  diagnosis: Diagnosis
  trajectory: TrajectoryItem[]
  hypotheses: Hypothesis[]
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(body.detail ?? 'Request failed')
  }
  return response.json() as Promise<T>
}

export function listIncidents(): Promise<IncidentSummary[]> {
  return request('/api/incidents')
}

export function loadDemoReport(
  incidentId: string,
  mode: InvestigationMode,
): Promise<DemoReport> {
  return request(`/api/demo/incidents/${incidentId}/report?mode=${mode}`)
}

export function investigate(incidentId: string): Promise<{ run_id: string; result: Diagnosis }> {
  return request('/api/investigations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ incident_id: incidentId, system_version: 'baseline' }),
  })
}
