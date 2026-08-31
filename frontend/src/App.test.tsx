import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

const incident = {
  incident_id: 'CC-001',
  date: '2026-07-06',
  window_start: '2026-07-06T08:00:00',
  window_end: '2026-07-06T11:45:00',
  incident_start: '2026-07-06T09:15:00',
  alert: 'Service level fell below target.',
}

const report = {
  mode: {
    id: 'default',
    label: 'Standard analysis',
    description: 'Fast, complete-context analysis for day-to-day incident triage.',
    run_id: 'stage-zero-run',
    is_default: true,
  },
  incident: { ...incident, service_level_seconds: 30, service_level_target: 80 },
  impact: {
    impacted_queues: ['Billing'],
    kpis: [
      { id: 'service_level', label: 'Service level', value: 54.3, unit: '%', delta: -36.5, delta_unit: 'pp', context: 'Target 80%', tone: 'negative' },
      { id: 'asa', label: 'Average speed of answer', value: 72.5, unit: 's', delta: 47.7, delta_unit: 's', context: 'Weighted', tone: 'negative' },
      { id: 'abandonment', label: 'Abandonment', value: 13.2, unit: '%', delta: 10.1, delta_unit: 'pp', context: 'All calls', tone: 'negative' },
      { id: 'forecast_variance', label: 'Volume vs forecast', value: 55.5, unit: '%', delta: null, delta_unit: null, context: '1,308 actual / 841 forecast', tone: 'negative' },
    ],
    queues: [{ queue_name: 'Billing', service_level_pct: 49.2, service_level_delta_pp: -40.2, asa_seconds: 80.1, aht_seconds: 380, transfer_rate_pct: 6, staffed_agents: 12, volume_delta_pct: 60 }],
    trend: [
      { timestamp: '2026-07-06T08:00:00', service_level_pct: 92, asa_seconds: 20, abandonment_rate_pct: 1, offered_calls: 66, forecast_offered_calls: 72, productive_agents: 46, is_incident_period: false },
      { timestamp: '2026-07-06T09:15:00', service_level_pct: 51, asa_seconds: 74, abandonment_rate_pct: 12, offered_calls: 117, forecast_offered_calls: 79, productive_agents: 45, is_incident_period: true },
    ],
    staffing_context: { productive_agents: 45.6, productive_agent_delta: 0.4, occupancy_pct: 98.9 },
    forecast_context: { actual_calls: 1308, forecast_calls: 841, variance_pct: 55.5 },
    events: [],
  },
  diagnosis: {
    incident_id: 'CC-001',
    investigation_status: 'CONFIRMED',
    primary_root_cause_category: 'DEMAND_SPIKE',
    primary_root_cause_detail: 'Unexpected demand overwhelmed stable capacity.',
    confidence: 0.99,
    contributing_factors: [],
    evidence: [{ signal: 'demand_surge', source: 'performance', finding: 'Demand rose sharply at incident onset.' }],
    rejected_hypotheses: [{ category: 'STAFFING_SHORTFALL', reason: 'Staffing remained stable.' }],
    causal_chain: ['unexpected_demand', 'capacity_deficit', 'service_level_degradation'],
    recommended_actions: ['Activate surge staffing.'],
    stakeholder_summary: 'A confirmed demand spike caused the service-level incident.',
  },
  trajectory: [
    { step: 1, type: 'started', title: 'Investigation started', summary: 'Visible context supplied.' },
    { step: 2, type: 'complete', title: 'Diagnosis finalized', summary: 'Demand spike returned.' },
  ],
  hypotheses: [],
}

function response(body: unknown, ok = true) {
  return Promise.resolve({ ok, statusText: ok ? 'OK' : 'Unavailable', json: async () => body })
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

test('loads the polished standard investigation report', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    return url === '/api/incidents' ? response([incident]) : response(report)
  }))

  render(<App />)

  expect(screen.getByText(/contact center operations intelligence/i)).toBeInTheDocument()
  expect(await screen.findByRole('heading', { name: /demand spike/i })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /what the diagnosis is based on/i })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /how the incident unfolded/i })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /ready to share/i })).toBeInTheDocument()
  expect(screen.getByText(/2 public steps/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /run live analysis/i })).toBeEnabled()
})

test('switches to deep investigation without presenting it as an accuracy tier', async () => {
  const auditReport = {
    ...report,
    mode: { ...report.mode, id: 'audit', label: 'Deep investigation', is_default: false },
    hypotheses: [{ category: 'DEMAND_SPIKE', status: 'LIKELY', confidence: 0.94, evidence_for: [], evidence_against: [] }],
    trajectory: [...report.trajectory, { step: 3, type: 'tool', title: 'Compare Queues', summary: 'Compared queue performance.' }],
  }
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url === '/api/incidents') return response([incident])
    return response(url.includes('mode=audit') ? auditReport : report)
  }))
  render(<App />)
  await screen.findByRole('heading', { name: /demand spike/i })

  fireEvent.click(screen.getByRole('button', { name: /deep investigation audit trail/i }))

  expect(await screen.findByRole('heading', { name: /hypothesis ledger/i })).toBeInTheDocument()
  expect(screen.getByText(/not an accuracy tier/i)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /run live analysis/i })).not.toBeInTheDocument()
})

test('shows an API error and retries the report', async () => {
  let reportCalls = 0
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    if (String(input) === '/api/incidents') return response([incident])
    reportCalls += 1
    return reportCalls === 1 ? response({ detail: 'Curated report unavailable' }, false) : response(report)
  }))
  render(<App />)

  expect(await screen.findByRole('alert')).toHaveTextContent(/curated report unavailable/i)
  fireEvent.click(screen.getByRole('button', { name: /retry/i }))

  await waitFor(() => expect(screen.getByRole('heading', { name: /demand spike/i })).toBeInTheDocument())
  expect(reportCalls).toBe(2)
})

test('runs the live standard analysis and renders its result', async () => {
  const liveResult = {
    run_id: 'live-run-id',
    result: {
      ...report.diagnosis,
      confidence: 0.87,
      primary_root_cause_category: 'ROUTING_CHANGE',
      primary_root_cause_detail: 'A live standard analysis identified a routing change.',
    },
  }
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url === '/api/incidents') return response([incident])
    if (url === '/api/investigations' && init?.method === 'POST') return response(liveResult)
    return response(report)
  }))
  render(<App />)
  await screen.findByRole('heading', { name: /demand spike/i })

  fireEvent.click(screen.getByRole('button', { name: /run live analysis/i }))

  expect(await screen.findByText(/live standard analysis completed/i)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /routing change/i })).toBeInTheDocument()
  expect(screen.getByLabelText(/87 percent confidence/i)).toBeInTheDocument()
})
