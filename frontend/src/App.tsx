import { useEffect, useState } from 'react'
import { investigate, listIncidents, type Diagnosis, type IncidentSummary } from './api'
import './styles.css'

export default function App() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([])
  const [selected, setSelected] = useState('')
  const [result, setResult] = useState<Diagnosis | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    listIncidents()
      .then((items) => {
        setIncidents(items)
        setSelected(items[0]?.incident_id ?? '')
      })
      .catch((reason: Error) => setError(reason.message))
  }, [])

  async function runInvestigation() {
    if (!selected) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const response = await investigate(selected)
      setResult(response.result)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Investigation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="shell">
      <header>
        <p className="eyebrow">Stage 0 · Fair baseline</p>
        <h1>Contact Center Incident Investigator</h1>
        <p className="lede">Select a frozen synthetic incident and run the single-stage analyst baseline.</p>
      </header>

      <section className="control-card" aria-label="Incident controls">
        <label htmlFor="incident">Incident</label>
        <select id="incident" value={selected} onChange={(event) => setSelected(event.target.value)}>
          {incidents.map((incident) => (
            <option key={incident.incident_id} value={incident.incident_id}>
              {incident.incident_id} · {incident.date}
            </option>
          ))}
        </select>
        <button type="button" disabled={!selected || loading} onClick={runInvestigation}>
          {loading ? 'Investigating…' : 'Run baseline'}
        </button>
      </section>

      {error && <p className="error" role="alert">{error}</p>}

      {result && (
        <article className="result-card">
          <div className="result-heading">
            <div>
              <p className="eyebrow">{result.investigation_status}</p>
              <h2>{result.primary_root_cause_category}</h2>
            </div>
            <strong>{Math.round(result.confidence * 100)}% confidence</strong>
          </div>
          <p>{result.primary_root_cause_detail}</p>
          <h3>Evidence</h3>
          <ul>{result.evidence.map((item) => <li key={`${item.signal}-${item.source}`}>{item.finding}</li>)}</ul>
          <h3>Recommended actions</h3>
          <ul>{result.recommended_actions.map((action) => <li key={action}>{action}</li>)}</ul>
          <blockquote>{result.stakeholder_summary}</blockquote>
        </article>
      )}
    </main>
  )
}

