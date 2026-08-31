import { useEffect, useMemo, useState } from 'react'
import {
  investigate,
  listIncidents,
  loadDemoReport,
  type DemoReport,
  type Diagnosis,
  type ImpactKpi,
  type IncidentSummary,
  type InvestigationMode,
  type TrajectoryItem,
  type TrendPoint,
} from './api'
import './styles.css'

function humanize(value: string) {
  return value.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function shortTime(value: string) {
  return new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' }).format(new Date(value))
}

function formatWindow(start: string, end: string) {
  const date = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  return `${date.format(new Date(start))} · ${shortTime(start)}–${shortTime(end)}`
}

function signed(value: number | null, unit = '') {
  if (value === null) return '—'
  return `${value > 0 ? '+' : ''}${value.toFixed(1)}${unit}`
}

function Icon({ name }: { name: 'pulse' | 'clock' | 'queue' | 'spark' | 'check' | 'arrow' }) {
  const paths = {
    pulse: 'M3 12h4l2-7 4 14 2-7h6',
    clock: 'M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
    queue: 'M4 6h16M4 12h12M4 18h8',
    spark: 'm12 3 1.7 4.3L18 9l-4.3 1.7L12 15l-1.7-4.3L6 9l4.3-1.7L12 3Z',
    check: 'm5 12 4 4L19 6',
    arrow: 'm8 5 7 7-7 7',
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d={paths[name]} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function KpiCard({ kpi }: { kpi: ImpactKpi }) {
  const icons: Record<string, 'pulse' | 'clock' | 'queue' | 'spark'> = {
    service_level: 'pulse',
    asa: 'clock',
    abandonment: 'queue',
    forecast_variance: 'spark',
  }
  return (
    <div className="kpi-card">
      <div className={`kpi-icon ${kpi.tone}`}><Icon name={icons[kpi.id] ?? 'pulse'} /></div>
      <div>
        <p className="kpi-label">{kpi.label}</p>
        <div className="kpi-value-row">
          <strong>{kpi.value === null ? '—' : kpi.value.toFixed(1)}<span>{kpi.unit}</span></strong>
          {kpi.delta !== null && <span className={`delta ${kpi.tone}`}>{signed(kpi.delta, kpi.delta_unit ?? '')}</span>}
        </div>
        <p className="kpi-context">{kpi.context}</p>
      </div>
    </div>
  )
}

function ServiceTrend({ points, target }: { points: TrendPoint[]; target: number }) {
  const width = 760
  const height = 220
  const padX = 34
  const padTop = 18
  const padBottom = 36
  const chartHeight = height - padTop - padBottom
  const x = (index: number) => padX + (index * (width - padX * 2)) / Math.max(points.length - 1, 1)
  const y = (value: number) => padTop + ((100 - Math.max(0, Math.min(100, value))) / 100) * chartHeight
  const path = points.map((point, index) => `${index ? 'L' : 'M'} ${x(index)} ${y(point.service_level_pct)}`).join(' ')
  const incidentIndex = Math.max(points.findIndex((point) => point.is_incident_period), 0)

  return (
    <div className="trend-wrap">
      <svg className="trend-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Service level trend across the incident window">
        <defs>
          <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#4fd1c5" stopOpacity=".28" />
            <stop offset="1" stopColor="#4fd1c5" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 50, 100].map((tick) => <line key={tick} x1={padX} x2={width - padX} y1={y(tick)} y2={y(tick)} className="grid-line" />)}
        <rect x={x(incidentIndex)} y={padTop} width={width - padX - x(incidentIndex)} height={chartHeight} className="incident-zone" />
        <line x1={padX} x2={width - padX} y1={y(target)} y2={y(target)} className="target-line" />
        <text x={width - padX} y={y(target) - 7} textAnchor="end" className="target-label">{target}% target</text>
        <path d={`${path} L ${x(points.length - 1)} ${height - padBottom} L ${padX} ${height - padBottom} Z`} className="trend-area" />
        <path d={path} className="trend-line" />
        {points.map((point, index) => <circle key={point.timestamp} cx={x(index)} cy={y(point.service_level_pct)} r="3.5" className={point.is_incident_period ? 'trend-dot incident' : 'trend-dot'} />)}
        {points.filter((_, index) => index % 3 === 0 || index === points.length - 1).map((point) => {
          const index = points.indexOf(point)
          return <text key={point.timestamp} x={x(index)} y={height - 12} textAnchor="middle" className="axis-label">{shortTime(point.timestamp)}</text>
        })}
      </svg>
    </div>
  )
}

function Trajectory({ items, mode }: { items: TrajectoryItem[]; mode: InvestigationMode }) {
  return (
    <section className="panel trajectory-panel">
      <div className="section-heading">
        <div><p className="section-kicker">Explainability</p><h2>Investigation history</h2></div>
        <span className="subtle-badge">{items.length} public steps</span>
      </div>
      <p className="section-intro">
        {mode === 'audit'
          ? 'A concise audit trail of tool decisions and structured hypothesis changes.'
          : 'The standard path uses one complete-context analysis, shown without fabricated intermediate activity.'}
      </p>
      <ol className="timeline">
        {items.map((item) => (
          <li key={`${item.step}-${item.title}`}>
            <div className={`timeline-marker ${item.type}`}><span>{item.step}</span></div>
            <div className="timeline-content">
              <div className="timeline-title"><strong>{item.title}</strong><span>{item.type === 'tool' ? 'Deterministic tool' : humanize(item.type)}</span></div>
              <p>{item.summary}</p>
              {item.arguments && Object.keys(item.arguments).length > 0 && <code>{JSON.stringify(item.arguments)}</code>}
              {item.changes && item.changes.length > 0 && (
                <div className="change-row">{item.changes.slice(0, 4).map((change) => <span key={change.category}>{humanize(change.category)} · {humanize(change.status)}</span>)}</div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

function DiagnosisView({ report, diagnosis, trajectory, liveRunId }: { report: DemoReport; diagnosis: Diagnosis; trajectory: TrajectoryItem[]; liveRunId: string }) {
  const incident = report.incident
  const impact = report.impact
  return (
    <div className="report" aria-live="polite">
      {liveRunId && <div className="live-banner"><Icon name="check" /><span>Live standard analysis completed</span><code>{liveRunId}</code></div>}

      <section className="overview-grid">
        <aside className="panel incident-card">
          <div className="incident-title-row">
            <div><p className="section-kicker">Incident overview</p><h2>{incident.incident_id}</h2></div>
            <span className="status-dot">Analysis complete</span>
          </div>
          <p className="alert-copy">{incident.alert}</p>
          <dl className="incident-facts">
            <div><dt>Evaluation window</dt><dd>{formatWindow(incident.window_start, incident.window_end)}</dd></div>
            <div><dt>Incident onset</dt><dd>{shortTime(incident.incident_start)}</dd></div>
            <div><dt>Service target</dt><dd>{incident.service_level_target}% in {incident.service_level_seconds}s</dd></div>
          </dl>
          <div className="queue-list"><p>Impacted queues</p><div>{impact.impacted_queues.map((queue) => <span key={queue}>{queue}</span>)}</div></div>
        </aside>

        <article className="panel diagnosis-card">
          <div className="diagnosis-topline">
            <div className="status-group"><span className="status-badge">{humanize(diagnosis.investigation_status)}</span><span>Finalized diagnosis</span></div>
            <div className="confidence" aria-label={`${Math.round(diagnosis.confidence * 100)} percent confidence`}>
              <span className="confidence-ring" style={{ '--confidence': `${diagnosis.confidence * 360}deg` } as React.CSSProperties}><strong>{Math.round(diagnosis.confidence * 100)}</strong><small>%</small></span>
              <span>Confidence</span>
            </div>
          </div>
          <p className="section-kicker">Primary root cause</p>
          <h1>{humanize(diagnosis.primary_root_cause_category)}</h1>
          <p className="diagnosis-detail">{diagnosis.primary_root_cause_detail}</p>
          <div className="causal-summary"><Icon name="arrow" /><span>{diagnosis.causal_chain.map(humanize).join(' → ')}</span></div>
        </article>
      </section>

      <section className="kpi-grid" aria-label="Incident impact metrics">{impact.kpis.map((kpi) => <KpiCard key={kpi.id} kpi={kpi} />)}</section>

      <section className="content-grid">
        <div className="content-main">
          <section className="panel chart-panel">
            <div className="section-heading"><div><p className="section-kicker">Performance impact</p><h2>Service-level trajectory</h2></div><span className="legend"><i /> Incident period</span></div>
            <ServiceTrend points={impact.trend} target={incident.service_level_target} />
          </section>

          <section className="panel">
            <div className="section-heading"><div><p className="section-kicker">Supporting evidence</p><h2>What the diagnosis is based on</h2></div><span className="subtle-badge">{diagnosis.evidence.length} findings</span></div>
            <div className="evidence-grid">{diagnosis.evidence.map((item) => (
              <article className="evidence-item" key={`${item.signal}-${item.source}`}>
                <div className="evidence-head"><span>{humanize(item.source)}</span><code>{humanize(item.signal)}</code></div>
                <p>{item.finding}</p>
              </article>
            ))}</div>
          </section>

          <section className="panel causal-panel">
            <div className="section-heading"><div><p className="section-kicker">Causal reasoning</p><h2>How the incident unfolded</h2></div></div>
            <ol className="causal-chain">{diagnosis.causal_chain.map((concept, index) => <li key={`${concept}-${index}`}><span>{index + 1}</span><strong>{humanize(concept)}</strong>{index < diagnosis.causal_chain.length - 1 && <Icon name="arrow" />}</li>)}</ol>
          </section>

          <section className="panel queue-panel">
            <div className="section-heading"><div><p className="section-kicker">Queue comparison</p><h2>Operating impact by queue</h2></div><span className="subtle-badge">Incident period</span></div>
            <div className="table-scroll"><table><thead><tr><th>Queue</th><th>Service level</th><th>Δ service</th><th>ASA</th><th>Δ volume</th><th>Staffed</th></tr></thead><tbody>{impact.queues.map((queue) => <tr key={queue.queue_name}><th>{queue.queue_name}</th><td><span className={(queue.service_level_pct ?? 100) < incident.service_level_target ? 'metric-alert' : ''}>{queue.service_level_pct?.toFixed(1) ?? '—'}%</span></td><td>{signed(queue.service_level_delta_pp, 'pp')}</td><td>{queue.asa_seconds?.toFixed(1) ?? '—'}s</td><td>{signed(queue.volume_delta_pct, '%')}</td><td>{queue.staffed_agents?.toFixed(0) ?? '—'}</td></tr>)}</tbody></table></div>
          </section>
        </div>

        <aside className="content-side">
          <section className="panel context-panel">
            <p className="section-kicker">Operating context</p><h2>Capacity & demand</h2>
            <div className="context-stat"><span>Productive agents</span><strong>{impact.staffing_context.productive_agents?.toFixed(1) ?? '—'}</strong><small>{signed(impact.staffing_context.productive_agent_delta)} vs before</small></div>
            <div className="context-stat"><span>Occupancy</span><strong>{impact.staffing_context.occupancy_pct?.toFixed(1) ?? '—'}%</strong><small>Incident-period average</small></div>
            <div className="context-stat"><span>Actual / forecast</span><strong>{impact.forecast_context.actual_calls.toLocaleString()} / {impact.forecast_context.forecast_calls.toLocaleString()}</strong><small>{signed(impact.forecast_context.variance_pct, '%')} variance</small></div>
            <div className="event-context"><span>Operational events</span><p>{impact.events.length ? `${impact.events.length} visible event${impact.events.length === 1 ? '' : 's'} recorded in the window.` : 'No operational events were recorded in the visible window.'}</p></div>
          </section>

          <section className="panel contributor-panel">
            <p className="section-kicker">Secondary context</p><h2>Contributing factors</h2>
            {diagnosis.contributing_factors.length ? <ul className="tag-list">{diagnosis.contributing_factors.map((factor) => <li key={factor}>{humanize(factor)}</li>)}</ul> : <p className="empty-copy">No material contributing factor was identified beyond the primary cause.</p>}
          </section>

          <section className="panel action-panel">
            <p className="section-kicker">Response plan</p><h2>Recommended actions</h2>
            <ol className="action-list">{diagnosis.recommended_actions.map((action, index) => <li key={action}><span>{index + 1}</span><p>{action}</p></li>)}</ol>
          </section>
        </aside>
      </section>

      {report.hypotheses.length > 0 && (
        <section className="panel hypothesis-panel">
          <div className="section-heading"><div><p className="section-kicker">Deep investigation</p><h2>Hypothesis ledger</h2></div><span className="subtle-badge">Audit mode</span></div>
          <div className="hypothesis-grid">{report.hypotheses.map((hypothesis) => <article key={hypothesis.category} className={hypothesis.status === 'LIKELY' ? 'leading' : ''}><div><strong>{humanize(hypothesis.category)}</strong><span>{humanize(hypothesis.status)}</span></div><progress value={hypothesis.confidence} max="1" /><p>{hypothesis.evidence_for.length} supporting · {hypothesis.evidence_against.length} counter signals</p></article>)}</div>
        </section>
      )}

      <section className="bottom-grid">
        <section className="panel rejected-panel">
          <div className="section-heading"><div><p className="section-kicker">Alternatives considered</p><h2>Rejected explanations</h2></div><span className="subtle-badge">{diagnosis.rejected_hypotheses.length} reviewed</span></div>
          <div className="rejected-list">{diagnosis.rejected_hypotheses.map((item) => <details key={item.category}><summary><span><Icon name="check" /></span>{humanize(item.category)}</summary><p>{item.reason}</p></details>)}</div>
        </section>
        <aside className="panel stakeholder-card"><div className="brief-icon"><Icon name="spark" /></div><p className="section-kicker">Stakeholder brief</p><h2>Ready to share</h2><blockquote>{diagnosis.stakeholder_summary}</blockquote><button type="button" className="copy-button" onClick={() => navigator.clipboard?.writeText(diagnosis.stakeholder_summary)}>Copy brief</button></aside>
      </section>

      <Trajectory items={trajectory} mode={report.mode.id} />
    </div>
  )
}

function LoadingReport() {
  return <div className="loading-report" aria-label="Loading investigation"><div className="skeleton tall" /><div className="skeleton tall" /><div className="skeleton-row">{[1, 2, 3, 4].map((item) => <div className="skeleton" key={item} />)}</div><div className="skeleton wide" /></div>
}

export default function App() {
  const [incidents, setIncidents] = useState<IncidentSummary[]>([])
  const [selected, setSelected] = useState('')
  const [mode, setMode] = useState<InvestigationMode>('default')
  const [report, setReport] = useState<DemoReport | null>(null)
  const [liveResult, setLiveResult] = useState<{ run_id: string; result: Diagnosis } | null>(null)
  const [catalogLoading, setCatalogLoading] = useState(true)
  const [reportLoading, setReportLoading] = useState(false)
  const [liveLoading, setLiveLoading] = useState(false)
  const [error, setError] = useState('')
  const [catalogAttempt, setCatalogAttempt] = useState(0)
  const [reportAttempt, setReportAttempt] = useState(0)

  useEffect(() => {
    let active = true
    setCatalogLoading(true)
    setError('')
    listIncidents().then((items) => {
      if (!active) return
      setIncidents(items)
      setSelected((current) => current || items[0]?.incident_id || '')
    }).catch((reason: Error) => active && setError(reason.message)).finally(() => active && setCatalogLoading(false))
    return () => { active = false }
  }, [catalogAttempt])

  useEffect(() => {
    if (!selected) return
    let active = true
    setReportLoading(true)
    setError('')
    setLiveResult(null)
    loadDemoReport(selected, mode).then((nextReport) => active && setReport(nextReport)).catch((reason: Error) => {
      if (active) { setReport(null); setError(reason.message) }
    }).finally(() => active && setReportLoading(false))
    return () => { active = false }
  }, [selected, mode, reportAttempt])

  async function runLiveInvestigation() {
    if (!selected) return
    setLiveLoading(true)
    setError('')
    try {
      setLiveResult(await investigate(selected))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Investigation failed')
    } finally {
      setLiveLoading(false)
    }
  }

  const liveTrajectory = useMemo<TrajectoryItem[]>(() => liveResult ? [
    { step: 1, type: 'started', title: 'Investigation started', summary: 'Complete visible incident context was sent to the structured analyst.' },
    { step: 2, type: 'complete', title: 'Diagnosis finalized', summary: `${humanize(liveResult.result.primary_root_cause_category)} was returned with ${Math.round(liveResult.result.confidence * 100)}% confidence.` },
  ] : [], [liveResult])

  const diagnosis = liveResult?.result ?? report?.diagnosis
  const trajectory = liveResult ? liveTrajectory : report?.trajectory ?? []

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand"><span className="brand-mark"><Icon name="pulse" /></span><div><strong>Incident Investigator</strong><small>Contact center operations intelligence</small></div></div>
        <div className="system-state"><span /><div><strong>Analysis service online</strong><small>Structured operational findings</small></div></div>
      </header>

      <main className="app-shell">
        <section className="workspace-bar" aria-label="Investigation controls">
          <div className="selector-group"><label htmlFor="incident">Incident</label><select id="incident" value={selected} disabled={catalogLoading} onChange={(event) => setSelected(event.target.value)}>{incidents.map((incident) => <option key={incident.incident_id} value={incident.incident_id}>{incident.incident_id} · {incident.date} · {incident.alert}</option>)}</select></div>
          <div className="mode-control"><span>Analysis mode</span><div className="segmented" role="group" aria-label="Analysis mode"><button type="button" className={mode === 'default' ? 'active' : ''} aria-pressed={mode === 'default'} onClick={() => setMode('default')}><span>Standard</span><small>Recommended</small></button><button type="button" className={mode === 'audit' ? 'active' : ''} aria-pressed={mode === 'audit'} onClick={() => setMode('audit')}><span>Deep investigation</span><small>Audit trail</small></button></div></div>
          {mode === 'default' ? <button type="button" className="run-button" disabled={!selected || liveLoading || reportLoading} onClick={runLiveInvestigation}><Icon name="spark" />{liveLoading ? 'Analyzing…' : 'Run live analysis'}</button> : <div className="audit-note"><Icon name="queue" /><span>For deeper drill-down and auditability—not an accuracy tier.</span></div>}
        </section>

        {report && !reportLoading && <div className="mode-description"><strong>{report.mode.label}</strong><span>{report.mode.description}</span>{report.mode.is_default && <i>Default</i>}</div>}

        {error && <section className="error-state" role="alert"><div><strong>We couldn’t load this investigation.</strong><p>{error}</p></div><button type="button" onClick={() => incidents.length ? setReportAttempt((value) => value + 1) : setCatalogAttempt((value) => value + 1)}>Retry</button></section>}
        {(catalogLoading || reportLoading) && <LoadingReport />}
        {!catalogLoading && !reportLoading && !error && report && diagnosis && <DiagnosisView report={report} diagnosis={diagnosis} trajectory={trajectory} liveRunId={liveResult?.run_id ?? ''} />}
      </main>
      <footer><span>Incident Investigator</span><span>Visible operational data only · No evaluator fields</span></footer>
    </div>
  )
}
