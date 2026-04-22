import {
  startTransition,
  useCallback,
  useDeferredValue,
  useEffect,
  useState,
} from 'react'
import DocsPage from './DocsPage'
import Dropdown from './Dropdown'

const ROLE_OPTIONS = [
  { value: 'viewer', label: 'Viewer' },
  { value: 'operator', label: 'Operator' },
  { value: 'approver', label: 'Approver' },
  { value: 'admin', label: 'Admin' },
]

const ENV_OPTIONS = [
  { value: 'dev', label: 'Dev' },
  { value: 'staging', label: 'Staging' },
  { value: 'production', label: 'Production' },
]

const STATUS_OPTIONS = [
  { value: 'all', label: 'All statuses' },
  { value: 'needs_approval', label: 'Needs approval' },
  { value: 'queued', label: 'Queued' },
  { value: 'executing', label: 'Executing' },
  { value: 'completed', label: 'Completed' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'dry_run_completed', label: 'Dry run' },
]

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const API_KEY = import.meta.env.VITE_APP_API_KEY || 'dev-secret-key-123'

const DEFAULT_METRICS = {
  total_commands: 0,
  approvals_pending: 0,
  blocked_commands: 0,
  completed_commands: 0,
  dry_runs: 0,
  failed_commands: 0,
  average_confidence: 0,
}

const METRIC_CONFIG = [
  { key: 'total_commands', label: 'Requests tracked' },
  { key: 'approvals_pending', label: 'Awaiting approval' },
  { key: 'completed_commands', label: 'Completed runs' },
  { key: 'blocked_commands', label: 'Blocked requests' },
]

const EXAMPLES = [
  {
    label: 'Safe remediation',
    description: 'Checks health and applies low-risk fixes.',
    instruction: 'Check system health and fix any minor issues in staging',
    environment: 'staging',
    executionMode: 'execute',
  },
  {
    label: 'Approval request',
    description: 'Valid production action that should pause for review.',
    instruction: 'Restart the auth service in production',
    environment: 'production',
    executionMode: 'execute',
  },
  {
    label: 'Preview only',
    description: 'Shows what would happen without touching the system.',
    instruction: 'Scale the billing service to 4 instances in production',
    environment: 'production',
    executionMode: 'dry_run',
  },
  {
    label: 'Unsafe command',
    description: 'Demonstrates a hard block from the policy engine.',
    instruction: 'Drop the production database',
    environment: 'production',
    executionMode: 'execute',
  },
]

const WORKFLOW_STEPS = [
  {
    title: 'Parse the query',
    copy: 'Normalize the request and map it to a known operational intent.',
  },
  {
    title: 'Apply policy',
    copy: 'Check role permissions, safety rules, and production approval requirements.',
  },
  {
    title: 'Choose the next step',
    copy: 'Clarify, block, preview, or queue the command depending on risk and completeness.',
  },
  {
    title: 'Run or review',
    copy: 'Execute via the worker, or let an approver make the final decision.',
  },
]

function App() {
  const [showDocs, setShowDocs] = useState(false)
  const [instruction, setInstruction] = useState('')
  const [environment, setEnvironment] = useState('staging')
  const [executionMode, setExecutionMode] = useState('execute')
  const [role, setRole] = useState('operator')
  const [userName, setUserName] = useState('Harshit Mehra')
  const [statusFilter, setStatusFilter] = useState('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [actionNote, setActionNote] = useState('')
  const [metrics, setMetrics] = useState(DEFAULT_METRICS)
  const [commands, setCommands] = useState([])
  const [selectedCommandId, setSelectedCommandId] = useState('')
  const [selectedCommand, setSelectedCommand] = useState(null)
  const [dashboardLoading, setDashboardLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [acting, setActing] = useState(false)
  const [banner, setBanner] = useState({
    tone: 'neutral',
    title: 'Ready',
    text: 'Submit a request to see how the query is parsed, checked, and executed.',
  })

  const deferredSearch = useDeferredValue(searchTerm)

  const buildHeaders = useCallback(() => ({
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY,
    'X-User-Id': userName.trim().toLowerCase().replace(/\s+/g, '-') || 'local-operator',
    'X-User-Name': userName.trim() || 'Local Operator',
    'X-User-Role': role,
  }), [role, userName])

  const fetchJson = useCallback(async (path, options = {}) => {
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        ...buildHeaders(),
        ...(options.headers || {}),
      },
    })

    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload.detail || payload.error || 'Request failed')
    }
    return payload
  }, [buildHeaders])

  const loadCommandDetail = useCallback(async (commandId) => {
    if (!commandId) {
      setSelectedCommand(null)
      return
    }

    const detail = await fetchJson(`/api/v1/commands/${commandId}`)
    startTransition(() => {
      setSelectedCommand(detail.data)
      setSelectedCommandId(commandId)
    })
  }, [fetchJson])

  const refreshDashboard = useCallback(async (preferredCommandId = '') => {
    const [nextMetrics, nextCommandsPayload] = await Promise.all([
      fetchJson('/api/v1/metrics'),
      fetchJson('/api/v1/commands?limit=30'),
    ])

    const nextCommands = nextCommandsPayload.commands || []
    const nextSelectedId =
      preferredCommandId ||
      selectedCommandId ||
      (nextCommands.length > 0 ? nextCommands[0].id : '')

    startTransition(() => {
      setMetrics(nextMetrics)
      setCommands(nextCommands)
      if (!nextSelectedId) {
        setSelectedCommandId('')
        setSelectedCommand(null)
      }
    })

    if (nextSelectedId) {
      await loadCommandDetail(nextSelectedId)
    }
  }, [fetchJson, loadCommandDetail, selectedCommandId])

  useEffect(() => {
    let cancelled = false

    const bootstrap = async () => {
      try {
        await refreshDashboard()
      } catch (error) {
        if (!cancelled) {
          setBanner({
            tone: 'critical',
            title: 'Connection issue',
            text: error.message,
          })
        }
      } finally {
        if (!cancelled) {
          setDashboardLoading(false)
        }
      }
    }

    bootstrap()

    const intervalId = window.setInterval(() => {
      refreshDashboard(selectedCommandId).catch(() => {})
    }, 5000)

    return () => {
      cancelled = true
      window.clearInterval(intervalId)
    }
  }, [refreshDashboard, selectedCommandId])

  const filteredCommands = commands.filter((command) => {
    const matchesStatus = statusFilter === 'all' || command.status === statusFilter
    const haystack = [
      command.instruction,
      command.command?.op || '',
      command.command?.intent_label || '',
      command.requested_by,
    ].join(' ').toLowerCase()
    const matchesSearch = haystack.includes(deferredSearch.trim().toLowerCase())
    return matchesStatus && matchesSearch
  })

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!instruction.trim()) {
      return
    }

    setSubmitting(true)
    try {
      const payload = await fetchJson('/api/v1/parse-command', {
        method: 'POST',
        body: JSON.stringify({
          instruction,
          environment,
          execution_mode: executionMode,
          context: {
            source: 'operations-studio-ui',
          },
        }),
      })

      setBanner({
        tone: payload.success ? 'positive' : 'warning',
        title: payload.success ? 'Request processed' : 'Needs attention',
        text: payload.error || payload.data?.decision_summary || 'Command accepted into the workflow.',
      })
      setInstruction('')
      setActionNote('')
      await refreshDashboard(payload.data?.id || '')
    } catch (error) {
      setBanner({
        tone: 'critical',
        title: 'Submission failed',
        text: error.message,
      })
    } finally {
      setSubmitting(false)
    }
  }

  const handleAction = async (action) => {
    if (!selectedCommandId) {
      return
    }

    setActing(true)
    try {
      const payload = await fetchJson(`/api/v1/commands/${selectedCommandId}/${action}`, {
        method: 'POST',
        body: JSON.stringify({ note: actionNote }),
      })

      setBanner({
        tone: action === 'approve' ? 'positive' : 'warning',
        title: action === 'approve' ? 'Approved' : 'Rejected',
        text: payload.data?.decision_summary || payload.data?.error || 'Command updated.',
      })
      setActionNote('')
      await refreshDashboard(selectedCommandId)
    } catch (error) {
      setBanner({
        tone: 'critical',
        title: 'Action failed',
        text: error.message,
      })
    } finally {
      setActing(false)
    }
  }

  const applyExample = (example) => {
    setInstruction(example.instruction)
    setEnvironment(example.environment)
    setExecutionMode(example.executionMode)
  }

  const selectedTone = getStatusTone(selectedCommand?.status)
  const selectedWorkflowStage = getWorkflowStage(selectedCommand?.status)
  const matchedTerms = selectedCommand?.command?.matched_terms || []
  const explanationSteps = selectedCommand?.command?.explanation_steps || []
  const decisionReasons = selectedCommand?.decision_reasons || []
  const hasApproverAction = selectedCommand?.status === 'needs_approval'
  const canApprove = role === 'approver' || role === 'admin'

  if (showDocs) {
    return <DocsPage onBack={() => setShowDocs(false)} />
  }

  return (
    <div className="page-shell">
      <div className="background-orb background-orb-left" />
      <div className="background-orb background-orb-right" />

      <header className="masthead">
        <div className="masthead-copy">
          <p className="kicker">AI operations studio</p>
          <h1>Queries become commands only when the system can explain the decision.</h1>
          <p className="lead">
            The interface now focuses on the full path: what the request means, why the
            backend accepted or blocked it, and what happens next.
          </p>

          <div className="hero-tags">
            <span>Readable parser</span>
            <span>Clear policy reasons</span>
            <span>Modern workflow UI</span>
            <button
              type="button"
              className="docs-nav-btn"
              onClick={() => setShowDocs(true)}
            >
              📖 View Docs
            </button>
          </div>
        </div>

        <aside className="surface-card session-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Session</p>
              <h2>Operator context</h2>
            </div>
            <span className="mini-badge">Local demo</span>
          </div>

          <label className="control">
            <span>Name</span>
            <input value={userName} onChange={(event) => setUserName(event.target.value)} />
          </label>

          <div className="control-grid">
            <div className="control">
              <span>Role</span>
              <Dropdown value={role} onChange={setRole} options={ROLE_OPTIONS} label="Role" />
            </div>

            <div className="control">
              <span>Environment</span>
              <Dropdown value={environment} onChange={setEnvironment} options={ENV_OPTIONS} label="Environment" />
            </div>
          </div>

          <div className="session-note">
            <strong>Current mode</strong>
            <p>
              Requests run as <span className="mono">{role}</span> in{' '}
              <span className="mono">{environment}</span>. Production actions may still pause for approval.
            </p>
          </div>
        </aside>
      </header>

      <section className="metrics-row">
        {METRIC_CONFIG.map((metric) => (
          <MetricCard
            key={metric.key}
            label={metric.label}
            value={metrics[metric.key]}
          />
        ))}
        <article className="surface-card metric-card metric-card-wide">
          <p className="eyebrow">Signal quality</p>
          <div className="metric-mainline">
            <strong>{Math.round((metrics.average_confidence || 0) * 100)}%</strong>
            <span>average parser confidence</span>
          </div>
          <p className="metric-footnote">
            {metrics.dry_runs} preview-only requests and {metrics.failed_commands} failed workflows recorded.
          </p>
        </article>
      </section>

      <section className={`banner banner-${banner.tone}`}>
        <div>
          <strong>{banner.title}</strong>
          <p>{banner.text}</p>
        </div>
      </section>

      <main className="workspace-grid">
        <section className="left-column">
          <article className="surface-card composer-card">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Create request</p>
                <h2>Submit a natural-language operation</h2>
              </div>
              <div className="segmented-control" role="radiogroup" aria-label="Execution mode">
                <button
                  type="button"
                  className={executionMode === 'execute' ? 'active' : ''}
                  onClick={() => setExecutionMode('execute')}
                >
                  Execute
                </button>
                <button
                  type="button"
                  className={executionMode === 'dry_run' ? 'active' : ''}
                  onClick={() => setExecutionMode('dry_run')}
                >
                  Dry run
                </button>
              </div>
            </div>

            <form className="composer-form" onSubmit={handleSubmit}>
              <label className="control">
                <span>Query</span>
                <textarea
                  rows="6"
                  value={instruction}
                  onChange={(event) => setInstruction(event.target.value)}
                  placeholder="Restart the auth service in production after confirming it is healthy."
                />
              </label>

              <div className="composer-footer">
                <p>
                  The backend will parse the query, explain the matched intent, and then decide
                  whether to execute, preview, clarify, or block it.
                </p>
                <button className="primary-button" type="submit" disabled={submitting}>
                  {submitting ? 'Processing request...' : 'Submit request'}
                </button>
              </div>
            </form>
          </article>

          <article className="surface-card examples-card">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Examples</p>
                <h2>Preloaded demo prompts</h2>
              </div>
            </div>

            <div className="example-grid">
              {EXAMPLES.map((example) => (
                <button
                  key={example.label}
                  type="button"
                  className="example-card"
                  onClick={() => applyExample(example)}
                >
                  <strong>{example.label}</strong>
                  <span>{example.description}</span>
                  <p>{example.instruction}</p>
                </button>
              ))}
            </div>
          </article>

          <article className="surface-card guide-card">
            <div className="section-heading">
              <div>
                <p className="eyebrow">How it works</p>
                <h2>Readable backend workflow</h2>
              </div>
            </div>

            <div className="workflow-grid">
              {WORKFLOW_STEPS.map((step, index) => (
                <article
                  key={step.title}
                  className={`workflow-card ${selectedWorkflowStage >= index ? 'workflow-card-active' : ''}`}
                >
                  <span className="workflow-index">0{index + 1}</span>
                  <strong>{step.title}</strong>
                  <p>{step.copy}</p>
                </article>
              ))}
            </div>
          </article>
        </section>

        <section className="surface-card queue-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Queue</p>
              <h2>Recent requests</h2>
            </div>
            <button
              type="button"
              className="secondary-button"
              onClick={() => refreshDashboard(selectedCommandId)}
            >
              Refresh
            </button>
          </div>

          <div className="filter-row">
            <input
              className="search-input"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search by query, intent, operation, or requester"
            />

            <Dropdown value={statusFilter} onChange={setStatusFilter} options={STATUS_OPTIONS} label="Status filter" />
          </div>

          <div className="history-list">
            {dashboardLoading ? (
              <div className="empty-state">Loading requests...</div>
            ) : filteredCommands.length === 0 ? (
              <div className="empty-state">No requests match the current filters.</div>
            ) : (
              filteredCommands.map((command) => (
                <button
                  key={command.id}
                  type="button"
                  className={`history-entry ${selectedCommandId === command.id ? 'history-entry-active' : ''}`}
                  onClick={() => loadCommandDetail(command.id)}
                >
                  <div className="history-entry-top">
                    <StatusPill status={command.status} />
                    <span className="mini-badge">{command.command?.intent_label || 'Pending parse'}</span>
                  </div>

                  <p className="history-entry-title">{command.instruction}</p>
                  <p className="history-entry-copy">
                    {command.decision_summary || command.command?.summary || 'Waiting for more detail.'}
                  </p>

                  <div className="history-entry-meta">
                    <span>{command.requested_by}</span>
                    <span>{command.environment}</span>
                    <span>{command.risk_level}</span>
                  </div>
                </button>
              ))
            )}
          </div>
        </section>

        <section className="surface-card inspector-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Inspector</p>
              <h2>{selectedCommand?.command?.intent_label || 'Select a request'}</h2>
            </div>
            {selectedCommand ? <StatusPill status={selectedCommand.status} /> : null}
          </div>

          {!selectedCommand ? (
            <div className="empty-state">
              Choose a request from the queue to inspect the parser explanation, policy reasons, and execution details.
            </div>
          ) : (
            <div className="inspector-body">
              <div className="overview-grid">
                <OverviewCard label="Command ID" value={selectedCommand.id} mono />
                <OverviewCard label="Confidence" value={`${Math.round((selectedCommand.confidence || 0) * 100)}%`} />
                <OverviewCard label="Environment" value={selectedCommand.environment} />
                <OverviewCard label="Next step" value={selectedCommand.next_action || 'Review the latest result.'} />
              </div>

              <article className="inspector-section">
                <div className="section-title-row">
                  <h3>Backend decision</h3>
                  <span className={`tone-text tone-${selectedTone}`}>{selectedCommand.risk_level}</span>
                </div>
                <p className="body-copy strong-copy">{selectedCommand.decision_summary}</p>
                {selectedCommand.error ? (
                  <div className="note note-critical">{selectedCommand.error}</div>
                ) : null}
                <ul className="reason-list">
                  {decisionReasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </article>

              <article className="inspector-section">
                <h3>How the query was understood</h3>
                <div className="term-row">
                  {matchedTerms.length > 0 ? matchedTerms.map((term) => (
                    <span key={term} className="term-chip">{term}</span>
                  )) : <span className="subtle-copy">No matched terms recorded.</span>}
                </div>
                <ol className="explanation-list">
                  {explanationSteps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              </article>

              <article className="inspector-section">
                <h3>Structured command</h3>
                <details className="data-block" open>
                  <summary>View command payload</summary>
                  <pre>{formatJson(selectedCommand.command || { message: 'Command not parsed yet.' })}</pre>
                </details>
              </article>

              <article className="inspector-section">
                <h3>Execution result</h3>
                <details className="data-block" open>
                  <summary>View result payload</summary>
                  <pre>{formatJson(selectedCommand.result || { message: 'No execution result yet.' })}</pre>
                </details>
              </article>

              <article className="inspector-section">
                <h3>Approver action</h3>

                {hasApproverAction && !canApprove && (
                  <div className="approve-role-hint">
                    <span className="approve-hint-icon">⚠️</span>
                    <div>
                      <strong>Role upgrade required</strong>
                      <p>
                        This command is waiting for approval, but your current role is{' '}
                        <span className="mono">{role}</span>. Only{' '}
                        <span className="mono">approver</span> or{' '}
                        <span className="mono">admin</span> can approve.
                        Change the <strong>Role</strong> dropdown in the Session card above.
                      </p>
                    </div>
                  </div>
                )}

                <label className="control">
                  <span>Review note</span>
                  <textarea
                    rows="3"
                    value={actionNote}
                    onChange={(event) => setActionNote(event.target.value)}
                    placeholder="Add context for the approval or rejection decision."
                  />
                </label>

                <div className="action-row">
                  <button
                    type="button"
                    className="primary-button"
                    disabled={!hasApproverAction || !canApprove || acting}
                    title={!canApprove ? 'Switch role to Approver or Admin to enable this button' : ''}
                    onClick={() => handleAction('approve')}
                  >
                    {acting ? 'Saving...' : 'Approve and execute'}
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={!hasApproverAction || !canApprove || acting}
                    title={!canApprove ? 'Switch role to Approver or Admin to enable this button' : ''}
                    onClick={() => handleAction('reject')}
                  >
                    Reject
                  </button>
                </div>

                {!hasApproverAction && selectedCommand && (
                  <p className="subtle-copy" style={{ marginTop: 10, fontSize: '0.85rem' }}>
                    Approve and Reject are only active when the command status is{' '}
                    <span className="mono">needs_approval</span>.
                    Current status: <span className="mono">{selectedCommand.status}</span>.
                  </p>
                )}
              </article>

              <article className="inspector-section">
                <h3>Audit timeline</h3>
                <div className="timeline">
                  {selectedCommand.audit_trail.map((entry) => (
                    <article key={entry.id} className="timeline-entry">
                      <div className="timeline-dot" />
                      <div className="timeline-copy">
                        <div className="timeline-top">
                          <strong>{formatLabel(entry.event_type)}</strong>
                          <span className="mono subtle-copy">{formatDate(entry.created_at)}</span>
                        </div>
                        <p>{entry.message}</p>
                        <span className="subtle-copy">
                          {entry.actor_id} | {entry.actor_role}
                        </span>
                      </div>
                    </article>
                  ))}
                </div>
              </article>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

function MetricCard({ label, value }) {
  return (
    <article className="surface-card metric-card">
      <p className="eyebrow">{label}</p>
      <div className="metric-mainline">
        <strong>{value}</strong>
      </div>
    </article>
  )
}

function OverviewCard({ label, value, mono = false }) {
  return (
    <article className="overview-card">
      <span>{label}</span>
      <strong className={mono ? 'mono' : ''}>{value}</strong>
    </article>
  )
}

function StatusPill({ status }) {
  const tone = getStatusTone(status)
  return (
    <span className={`status-pill status-pill-${tone}`}>
      {formatLabel(status)}
    </span>
  )
}

function formatJson(value) {
  return JSON.stringify(value, null, 2)
}

function formatLabel(value = '') {
  return value.replace(/_/g, ' ')
}

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function getStatusTone(status = '') {
  if (['completed', 'approved'].includes(status)) {
    return 'positive'
  }
  if (['blocked', 'rejected', 'failed'].includes(status)) {
    return 'critical'
  }
  if (['needs_approval', 'needs_clarification', 'dry_run_completed'].includes(status)) {
    return 'warning'
  }
  return 'neutral'
}

function getWorkflowStage(status = '') {
  if (['received', 'parsed'].includes(status)) {
    return 1
  }
  if (['needs_clarification', 'blocked'].includes(status)) {
    return 2
  }
  if (['needs_approval', 'approved', 'rejected', 'dry_run_completed'].includes(status)) {
    return 3
  }
  if (['queued', 'executing', 'completed', 'failed'].includes(status)) {
    return 4
  }
  return 0
}

export default App
