/* eslint-disable react/no-unescaped-entities */

const SAMPLE_COMMANDS = [
  {
    category: 'Health Check',
    color: 'mint',
    icon: '🩺',
    entries: [
      {
        label: 'Basic health check',
        instruction: 'Check system health in staging',
        environment: 'staging',
        mode: 'execute',
        role: 'operator',
        expected: 'completed',
        note: 'Any operator or above can run this. No approval needed.',
      },
      {
        label: 'Health check + auto-fix',
        instruction: 'Check system health and fix any minor issues',
        environment: 'staging',
        mode: 'execute',
        role: 'operator',
        expected: 'completed',
        note: 'Maps to system.check_and_fix. Only requires approval in production.',
      },
    ],
  },
  {
    category: 'Service Restart',
    color: 'gold',
    icon: '🔄',
    entries: [
      {
        label: 'Restart in staging',
        instruction: 'Restart the auth service in staging',
        environment: 'staging',
        mode: 'execute',
        role: 'operator',
        expected: 'completed',
        note: 'Staging restarts go straight to execution without approval.',
      },
      {
        label: 'Restart in production (needs approval)',
        instruction: 'Restart the auth service in production',
        environment: 'production',
        mode: 'execute',
        role: 'operator',
        expected: 'needs_approval',
        note: 'Production service.restart always requires an approver or admin to review first. Switch role to "Approver" or "Admin" and click "Approve and execute".',
      },
    ],
  },
  {
    category: 'Service Scaling',
    color: 'accent',
    icon: '⚖️',
    entries: [
      {
        label: 'Scale in dry-run mode',
        instruction: 'Scale the billing service to 4 instances in production',
        environment: 'production',
        mode: 'dry_run',
        role: 'approver',
        expected: 'dry_run_completed',
        note: 'Dry run shows what would happen — no change is made. service.scale is only allowed for approvers and admins.',
      },
      {
        label: 'Scale with execute (approver required)',
        instruction: 'Scale the billing service to 4 instances in production',
        environment: 'production',
        mode: 'execute',
        role: 'approver',
        expected: 'needs_approval',
        note: 'Even approvers need a second review for production scaling. An admin can approve.',
      },
    ],
  },
  {
    category: 'Blocked (Safety Policy)',
    color: 'red',
    icon: '🚫',
    entries: [
      {
        label: 'Dangerous operation block',
        instruction: 'Drop the production database',
        environment: 'production',
        mode: 'execute',
        role: 'admin',
        expected: 'blocked',
        note: 'database.drop is on the hardcoded DANGEROUS_OPERATIONS list. No role can bypass this.',
      },
      {
        label: 'Unknown operation block',
        instruction: 'Call the secret internal API',
        environment: 'staging',
        mode: 'execute',
        role: 'admin',
        expected: 'blocked',
        note: 'If the parsed operation is not in the POLICY_RULES registry, it is blocked regardless of role.',
      },
    ],
  },
  {
    category: 'Approval Workflow',
    color: 'accent',
    icon: '✅',
    entries: [
      {
        label: 'Step 1 — Submit as operator',
        instruction: 'Restart the payment service in production',
        environment: 'production',
        mode: 'execute',
        role: 'operator',
        expected: 'needs_approval',
        note: 'Submit this first. The command will land in needs_approval state.',
      },
      {
        label: 'Step 2 — Approve as approver',
        instruction: '(Select the queued command from the list, then change role to Approver)',
        environment: 'production',
        mode: 'execute',
        role: 'approver',
        expected: 'completed',
        note: 'Change the Role dropdown to "Approver" or "Admin". Select the command from the queue. Click "Approve and execute". The button will only be active when status = needs_approval AND your role allows approval.',
      },
    ],
  },
]

const ROLES = [
  {
    name: 'Viewer',
    value: 'viewer',
    color: 'neutral',
    icon: '👁️',
    capabilities: ['Read metrics', 'View command queue', 'Inspect command details'],
    restrictions: ['Cannot submit commands', 'Cannot approve or reject'],
  },
  {
    name: 'Operator',
    value: 'operator',
    color: 'mint',
    icon: '🛠️',
    capabilities: [
      'Submit commands (health checks, restarts, backups)',
      'Run dry-run previews',
      'View full audit timeline',
    ],
    restrictions: [
      'Cannot approve production commands',
      'Cannot scale services (approver minimum)',
    ],
  },
  {
    name: 'Approver',
    value: 'approver',
    color: 'gold',
    icon: '✅',
    capabilities: [
      'All operator capabilities',
      'Approve or reject needs_approval commands',
      'Submit service.scale operations',
      'Trigger production workflows that skip the approval gate',
    ],
    restrictions: ['Still requires second approval on some admin-level scaling'],
  },
  {
    name: 'Admin',
    value: 'admin',
    color: 'accent',
    icon: '🔑',
    capabilities: [
      'All approver capabilities',
      'Approve commands queued by approvers',
      'Highest trust — bypasses most approval gates',
    ],
    restrictions: ['Hardcoded DANGEROUS_OPERATIONS blocklist still applies'],
  },
]

const STATUS_DOCS = [
  { status: 'received', tone: 'neutral', meaning: 'Command was persisted immediately after submission, before parsing.' },
  { status: 'parsed', tone: 'neutral', meaning: 'AI parsed the instruction into a structured command. Policy not yet applied.' },
  { status: 'needs_clarification', tone: 'warning', meaning: 'The instruction was too vague. Add more detail and resubmit.' },
  { status: 'blocked', tone: 'critical', meaning: 'Policy engine or safety guardrail blocked the operation permanently.' },
  { status: 'dry_run_completed', tone: 'warning', meaning: 'Preview generated. No real action taken. Switch to execute and resubmit.' },
  { status: 'needs_approval', tone: 'warning', meaning: 'Command is valid but requires a human approver (role: approver or admin) to proceed.' },
  { status: 'approved', tone: 'positive', meaning: 'Approved and queued for immediate execution by the worker.' },
  { status: 'rejected', tone: 'critical', meaning: 'Rejected by an approver. Revise the request or add context.' },
  { status: 'queued', tone: 'neutral', meaning: 'In the execution queue. Worker will pick it up momentarily.' },
  { status: 'executing', tone: 'neutral', meaning: 'Worker is actively executing the command.' },
  { status: 'completed', tone: 'positive', meaning: 'Execution finished successfully. Inspect result payload in the inspector.' },
  { status: 'failed', tone: 'critical', meaning: 'Execution or parsing encountered an unrecoverable error.' },
]

const FAQ = [
  {
    q: 'Why is the Approve button disabled?',
    a: 'Two conditions must both be true: (1) the selected command must have status "needs_approval", and (2) your current role must be "Approver" or "Admin". The default role is "Operator" which cannot approve. Change the Role dropdown in the Session card and re-select the command.',
  },
  {
    q: 'Why was my command blocked even though I\'m an admin?',
    a: 'The hardcoded DANGEROUS_OPERATIONS list (database.drop, system.rm_rf, user.delete_all) is enforced before any role check. No role can bypass it. This is intentional — it prevents catastrophic operations regardless of user trust level.',
  },
  {
    q: 'What is a dry run?',
    a: 'Select "Dry run" mode in the segmented control before submitting. The backend generates a preview payload showing what would happen — target service, actions, parameters — without touching any real system. No state is changed.',
  },
  {
    q: 'How does the AI parser work?',
    a: 'The backend sends your instruction to Google Gemini with a strict schema prompt. Gemini returns a structured JSON with op, parameters, risk_level, is_safe, and explanation. The backend then validates the output against Pydantic models. If validation fails, the command is marked failed with a clear error.',
  },
  {
    q: 'Where is data stored?',
    a: 'All commands, audit events, and metrics are stored in a local SQLite database (data/commands.db by default). Nothing is sent to an external service. The AI call goes to Google Gemini API only.',
  },
  {
    q: 'What happens if I submit the same command twice?',
    a: 'Each submission creates a new, independent command record with a unique ID (cmd_xxxxxxxxxxxx). Old commands are never overwritten.',
  },
  {
    q: 'The queue shows old completed commands. How do I clear them?',
    a: 'Use the status filter dropdown to show only "Needs approval" or switch the filter to hide completed runs. The backend retains all records for the full audit trail.',
  },
]

function ColorChip({ color }) {
  const map = {
    accent: { bg: 'rgba(222,111,77,0.12)', border: 'rgba(222,111,77,0.28)', text: '#de6f4d' },
    mint: { bg: 'rgba(45,139,115,0.12)', border: 'rgba(45,139,115,0.28)', text: '#2d8b73' },
    gold: { bg: 'rgba(204,154,60,0.12)', border: 'rgba(204,154,60,0.28)', text: '#cc9a3c' },
    red: { bg: 'rgba(196,81,72,0.12)', border: 'rgba(196,81,72,0.28)', text: '#c45148' },
    neutral: { bg: 'rgba(25,37,60,0.06)', border: 'rgba(25,37,60,0.14)', text: '#5d6a7a' },
  }
  return map[color] || map.neutral
}

function StatusPillDocs({ status, tone }) {
  const toneMap = {
    positive: { color: '#2d8b73', bg: 'rgba(45,139,115,0.1)', border: 'rgba(45,139,115,0.24)' },
    warning: { color: '#cc9a3c', bg: 'rgba(204,154,60,0.1)', border: 'rgba(204,154,60,0.24)' },
    critical: { color: '#c45148', bg: 'rgba(196,81,72,0.1)', border: 'rgba(196,81,72,0.24)' },
    neutral: { color: '#5d6a7a', bg: 'rgba(25,37,60,0.06)', border: 'rgba(25,37,60,0.12)' },
  }
  const s = toneMap[tone] || toneMap.neutral
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      borderRadius: 999,
      padding: '5px 12px',
      fontSize: '0.75rem',
      fontWeight: 700,
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
      color: s.color,
      background: s.bg,
      border: `1px solid ${s.border}`,
      whiteSpace: 'nowrap',
    }}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}

export default function DocsPage({ onBack }) {
  return (
    <div className="docs-shell">
      <div className="background-orb background-orb-left" />
      <div className="background-orb background-orb-right" />

      {/* Hero */}
      <div className="docs-hero">
        <button className="docs-back-btn" onClick={onBack}>
          ← Back to Studio
        </button>
        <div className="docs-hero-badge">📖 Documentation</div>
        <h1 className="docs-hero-title">
          AI Operations Studio
          <span className="docs-hero-accent"> — Complete Guide</span>
        </h1>
        <p className="docs-hero-lead">
          Everything you need to know: why this system exists, how the request pipeline works,
          which roles can do what, and exactly how to test the approval workflow.
        </p>

        <div className="docs-toc">
          {['Why this exists', 'How it works', 'Roles & permissions', 'Command statuses', 'Sample commands', 'Approve workflow', 'FAQ'].map((label, i) => (
            <a key={label} className="docs-toc-item" href={`#docs-section-${i}`}>
              {label}
            </a>
          ))}
        </div>
      </div>

      {/* ── Section 0 — Why ─────────────────────────────────── */}
      <section id="docs-section-0" className="docs-section">
        <div className="docs-section-label">01 / Why this exists</div>
        <h2 className="docs-section-title">The problem with plain-text operations</h2>
        <p className="docs-body">
          Operations teams deal with high-stakes actions every day — restarting services, scaling clusters, running
          database backups. The traditional approach is either a CLI with no guardrails, or a heavyweight ticketing
          system that adds hours of overhead. Neither is good enough.
        </p>
        <p className="docs-body">
          <strong>AI Operations Studio</strong> sits between the two. You describe what you want in plain English —
          "restart the auth service in production after confirming it is healthy" — and the backend translates it into
          a verified, audited command. If the action is safe and your role allows it, it runs immediately. If it needs
          a second pair of eyes, it pauses for an approver. If it is outright dangerous, it is hard-blocked before
          anything touches a real system.
        </p>

        <div className="docs-callout docs-callout-accent">
          <strong>Core thesis:</strong> Every operation should be explainable. The system does not just execute or
          block — it tells you <em>why</em> in plain language, so the team learns with every request.
        </div>

        <div className="docs-pillar-grid">
          {[
            { icon: '🔍', title: 'Parse', body: 'Google Gemini turns free-text into a structured JSON command with op, parameters, risk_level, and confidence.' },
            { icon: '🛡️', title: 'Guard', body: 'A deterministic policy engine validates the command against a hardcoded whitelist, role matrix, and environment rules — no LLM involved.' },
            { icon: '👁️', title: 'Explain', body: 'Every decision step is recorded in plain English and surfaced in the Inspector so operators understand the reasoning.' },
            { icon: '📋', title: 'Audit', body: 'A full, immutable audit timeline is attached to every command. Every state change, approval, or error is captured.' },
          ].map(p => (
            <div key={p.title} className="docs-pillar">
              <span className="docs-pillar-icon">{p.icon}</span>
              <strong>{p.title}</strong>
              <p>{p.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Section 1 — How it works ─────────────────────────── */}
      <section id="docs-section-1" className="docs-section">
        <div className="docs-section-label">02 / How it works</div>
        <h2 className="docs-section-title">The full request pipeline</h2>
        <p className="docs-body">
          Every submission travels through a fixed five-stage pipeline. The pipeline is deterministic — the same input
          will always produce the same policy outcome.
        </p>

        <div className="docs-pipeline">
          {[
            {
              step: '01',
              title: 'Receive & persist',
              detail: 'The request is written to the SQLite database immediately with status "received". This guarantees an audit trail even if every subsequent step fails.',
            },
            {
              step: '02',
              title: 'AI parse',
              detail: 'The instruction is sent to Google Gemini with a strict output schema. The response includes: op (operation name), parameters, risk_level, is_safe, matched_terms, and explanation_steps. Gemini output is validated with Pydantic — any schema violation fails the command.',
            },
            {
              step: '03',
              title: 'Security policy',
              detail: 'The policy engine (evaluate_command) runs entirely in Python — no more LLM calls. It checks: (1) needs_clarification flag, (2) DANGEROUS_OPERATIONS blocklist, (3) POLICY_RULES whitelist, (4) dry_run mode, (5) role permissions per operation, (6) production approval requirements.',
            },
            {
              step: '04',
              title: 'Route the decision',
              detail: 'Based on the policy outcome the command is routed to: blocked (stop), needs_clarification (prompt user), dry_run_completed (return preview), needs_approval (wait for human), or directly to the execution queue.',
            },
            {
              step: '05',
              title: 'Execute or approve',
              detail: 'The execution engine runs as a FastAPI BackgroundTask. It simulates actions (health checks, service API calls) and updates the command to "completed" or "failed" with a result payload. For approval flows, this step only runs after an approver clicks "Approve and execute".',
            },
          ].map(s => (
            <div key={s.step} className="docs-pipeline-step">
              <div className="docs-pipeline-step-num">{s.step}</div>
              <div className="docs-pipeline-step-body">
                <strong>{s.title}</strong>
                <p>{s.detail}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="docs-callout docs-callout-mint" style={{ marginTop: 28 }}>
          <strong>Architecture note:</strong> The AI parser and policy engine are intentionally decoupled. You can swap
          the AI provider (Gemini → OpenAI → local model) without touching the policy layer, and you can add new policy
          rules without changing the parser.
        </div>
      </section>

      {/* ── Section 2 — Roles ─────────────────────────────────── */}
      <section id="docs-section-2" className="docs-section">
        <div className="docs-section-label">03 / Roles & permissions</div>
        <h2 className="docs-section-title">Four roles, clear boundaries</h2>
        <p className="docs-body">
          Role is set in the <strong>Session card</strong> in the top-right of the studio. It is sent as the
          <code className="docs-inline-code">X-User-Role</code> header with every request. The backend enforces it —
          changing role in the UI is not cosmetic.
        </p>

        <div className="docs-role-grid">
          {ROLES.map(r => {
            const chip = ColorChip({ color: r.color })
            return (
              <div key={r.value} className="docs-role-card" style={{
                borderColor: chip.border,
                background: chip.bg,
              }}>
                <div className="docs-role-header">
                  <span className="docs-role-icon">{r.icon}</span>
                  <strong style={{ color: chip.text }}>{r.name}</strong>
                  <code className="docs-inline-code" style={{ marginLeft: 'auto' }}>{r.value}</code>
                </div>
                <div className="docs-role-perms">
                  <div>
                    <div className="docs-perm-label" style={{ color: '#2d8b73' }}>✓ Can do</div>
                    <ul>
                      {r.capabilities.map(c => <li key={c}>{c}</li>)}
                    </ul>
                  </div>
                  <div>
                    <div className="docs-perm-label" style={{ color: '#c45148' }}>✗ Cannot do</div>
                    <ul>
                      {r.restrictions.map(c => <li key={c}>{c}</li>)}
                    </ul>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* ── Section 3 — Statuses ─────────────────────────────── */}
      <section id="docs-section-3" className="docs-section">
        <div className="docs-section-label">04 / Command statuses</div>
        <h2 className="docs-section-title">What every status means</h2>
        <div className="docs-status-table">
          {STATUS_DOCS.map(s => (
            <div key={s.status} className="docs-status-row">
              <StatusPillDocs status={s.status} tone={s.tone} />
              <p>{s.meaning}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Section 4 — Sample commands ──────────────────────── */}
      <section id="docs-section-4" className="docs-section">
        <div className="docs-section-label">05 / Sample commands</div>
        <h2 className="docs-section-title">Ready-to-use command examples</h2>
        <p className="docs-body">
          Copy any instruction into the Query box. Make sure the <strong>Role</strong> and <strong>Environment</strong> dropdowns
          match the values in the table, and toggle the correct execution mode in the segmented control.
        </p>

        {SAMPLE_COMMANDS.map(group => {
          const chip = ColorChip({ color: group.color })
          return (
            <div key={group.category} className="docs-cmd-group">
              <div className="docs-cmd-group-header">
                <span>{group.icon}</span>
                <strong style={{ color: chip.text }}>{group.category}</strong>
              </div>
              {group.entries.map(e => (
                <div key={e.label} className="docs-cmd-card">
                  <div className="docs-cmd-top">
                    <strong>{e.label}</strong>
                    <div className="docs-cmd-tags">
                      <span className="docs-tag">Role: {e.role}</span>
                      <span className="docs-tag">Env: {e.environment}</span>
                      <span className="docs-tag">Mode: {e.mode}</span>
                      <StatusPillDocs status={e.expected} tone={
                        e.expected === 'completed' || e.expected === 'approved' ? 'positive'
                          : e.expected === 'blocked' || e.expected === 'failed' ? 'critical'
                            : 'warning'
                      } />
                    </div>
                  </div>
                  <code className="docs-cmd-instruction">"{e.instruction}"</code>
                  <p className="docs-cmd-note">💡 {e.note}</p>
                </div>
              ))}
            </div>
          )
        })}
      </section>

      {/* ── Section 5 — Approval walkthrough ─────────────────── */}
      <section id="docs-section-5" className="docs-section">
        <div className="docs-section-label">06 / Approve workflow</div>
        <h2 className="docs-section-title">How to test the approval feature</h2>

        <div className="docs-callout docs-callout-gold">
          <strong>Common mistake:</strong> The Approve button is disabled because the <em>role is "Operator"</em> by
          default. Change it to <strong>Approver</strong> or <strong>Admin</strong> first.
        </div>

        <div className="docs-steps">
          {[
            {
              n: 1,
              title: 'Set role to Operator and submit',
              detail: 'In the Session card, set Role = Operator and Environment = Production. Type "Restart the auth service in production" in the Query box and click Submit request. The command should land in needs_approval status.',
              code: 'Restart the auth service in production',
            },
            {
              n: 2,
              title: 'Select the command from the queue',
              detail: 'Find the new command in the queue on the right. Click it to load its details in the Inspector on the far right. Note the status pill reads "needs_approval".',
            },
            {
              n: 3,
              title: 'Switch role to Approver (critical step)',
              detail: 'In the Session card (top right), change the Role dropdown from "Operator" to "Approver" or "Admin". This sends the approver role header with the next API call. The button will remain visible — role is a runtime header, not a page reload.',
            },
            {
              n: 4,
              title: 'Click "Approve and execute"',
              detail: 'In the Inspector panel (far right), scroll to the Approver action section. Optionally add a review note. Click the "Approve and execute" button — it should now be active (not greyed out). The backend validates that your role = approver or admin before executing.',
              code: 'LGTM — health confirmed in prior check',
            },
            {
              n: 5,
              title: 'Watch the status update to completed',
              detail: 'The command status will sequentially change: approved → queued → executing → completed. The execution engine runs as a background task. The UI auto-refreshes every 5 seconds, or click Refresh in the queue header.',
            },
          ].map(s => (
            <div key={s.n} className="docs-step">
              <div className="docs-step-num">{s.n}</div>
              <div className="docs-step-body">
                <strong>{s.title}</strong>
                <p>{s.detail}</p>
                {s.code && (
                  <code className="docs-cmd-instruction">{s.code}</code>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="docs-callout docs-callout-mint" style={{ marginTop: 24 }}>
          <strong>Why the backend also enforces role:</strong> The approve endpoint (POST /api/v1/commands/:id/approve)
          checks <code className="docs-inline-code">user.role not in (approver, admin)</code> and raises HTTP 400 if
          the role is wrong. The UI check is a convenience — the backend is the authoritative guard.
        </div>
      </section>

      {/* ── Section 6 — FAQ ─────────────────────────────────── */}
      <section id="docs-section-6" className="docs-section">
        <div className="docs-section-label">07 / FAQ</div>
        <h2 className="docs-section-title">Frequently asked questions</h2>
        <div className="docs-faq">
          {FAQ.map(f => (
            <details key={f.q} className="docs-faq-item">
              <summary className="docs-faq-q">{f.q}</summary>
              <p className="docs-faq-a">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      <footer className="docs-footer">
        <div>
          <strong>AI Operations Studio</strong> — Built with FastAPI + Google Gemini + React
        </div>
        <button className="docs-back-btn" onClick={onBack}>← Back to Studio</button>
      </footer>
    </div>
  )
}
