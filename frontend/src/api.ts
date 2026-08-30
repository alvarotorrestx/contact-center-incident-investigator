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
  recommended_actions: string[]
  stakeholder_summary: string
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

export function investigate(incidentId: string): Promise<{ run_id: string; result: Diagnosis }> {
  return request('/api/investigations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ incident_id: incidentId, system_version: 'baseline' }),
  })
}

