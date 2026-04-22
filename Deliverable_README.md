# AI Command Control Center

This repository started as an assignment about converting natural language into backend-ready commands, and it has now been extended into a fuller operations workflow prototype.

## 1. Approach And Tradeoffs
I designed the system around one main idea:

Natural language is convenient for humans, but backend systems need structure, policy, and traceability.

So instead of letting the model directly execute anything, the application now does five distinct jobs:

1. parse the instruction into a strict command schema
2. detect ambiguity or unsafe intent
3. apply role-aware backend policy
4. route the command into approval, dry-run, or execution flows
5. persist the entire lifecycle for audit and debugging

### Key tradeoffs
- **Safety over autonomy:** the backend uses a default-deny policy and never trusts the model alone.
- **Deterministic local development:** there is a mock parser mode so the project can be demoed without depending on a live API key.
- **Operational visibility over demo simplicity:** I added persistence, metrics, and audit logs because those are what make the system feel credible in a real setting.
- **Mock execution over real infrastructure hooks:** the worker is intentionally simulated, which keeps the project easy to run while still demonstrating the full workflow.

## 2. Command Schema
The parser returns a structured command with fields like:

- `op`
- `summary`
- `actions`
- `parameters`
- `target_service`
- `environment`
- `confidence`
- `risk_level`
- `approval_required`
- `needs_clarification`
- `clarification_message`

This schema is validated with Pydantic before the rest of the system uses it.

## 3. Real Workflow
The system no longer stops at "model returns JSON." A command now moves through lifecycle states such as:

- `received`
- `parsed`
- `needs_clarification`
- `blocked`
- `needs_approval`
- `queued`
- `executing`
- `completed`
- `rejected`
- `dry_run_completed`

Every transition is stored in SQLite along with audit events.

## 4. How ambiguity and unsafe requests are handled
### Ambiguity
If the request is too vague, the parser sets `needs_clarification=true` and returns a user-facing clarification message.

Example:
```json
{
  "instruction": "Restart it",
  "environment": "staging",
  "execution_mode": "execute"
}
```

Result:
- no execution
- status becomes `needs_clarification`
- UI shows the clarification prompt

### Unsafe or destructive requests
If the request is dangerous, the parser marks it unsafe and the backend blocks it regardless of user intent.

Example:
```json
{
  "instruction": "Drop the production database",
  "environment": "production",
  "execution_mode": "execute"
}
```

Result:
- parsed as `database.drop`
- marked `critical`
- blocked by policy
- stored in the audit trail

## 5. Example flows
### Happy path
`"Check system health and fix any minor issues in staging"`

Output:
- `op: system.check_and_fix`
- safe
- auto-approved
- queued and completed by the mock worker

### Approval path
`"Restart the auth service in production"`

Output:
- `op: service.restart`
- high risk
- requires approval
- approver can approve or reject from the dashboard

### Dry run path
`"Scale the billing service to 4 instances in production"`

Output:
- `op: service.scale`
- preview only
- no execution triggered
- preview stored in history

## 6. Connection To A Real System
In a production system, the mock worker could be replaced with:

- a Redis or Kafka queue
- an internal orchestration service
- a job runner
- a secure CLI wrapper
- cloud functions or internal platform APIs

The important design idea is that the parser is only responsible for interpretation. Policy, execution, and auditability remain backend-owned concerns.

## 7. Why this is more than a parser demo
The project now includes:

- a React control-center dashboard
- role-aware command submission
- approval and rejection flows
- dry-run previews
- persistent command history
- metrics and audit trails
- a mock worker that simulates command execution

That makes it a stronger portfolio piece because it demonstrates backend design, product thinking, safety controls, and real-world operational workflows.
