# Agent Review Admin specification

## Human review receipt and integration status

Human feedback **was provided and recorded twice**: in chat (22 observations: 14 PASS, 6 FAIL, 2 PARTIAL PASS) and in the returned Excel workbook (28 live-app observations: 23 PASS, 2 FAIL, 3 PARTIAL PASS). These sets overlap and must not be added into 50 independent tests.

Receipt references: HR-CHAT-22 (`artifacts/human_feedback_20261101_batch02/Review_Summary.json`) and HR-XLSX-28 (`artifacts/human_review_received/817cb87ce51af0d4/Clarified_Review_Analysis.json`). The original returned workbook SHA-256 is `817cb87ce51af0d4429098b0e6ba09931a6e6482f15ab43939c266630856f628`.

The reviewer confirmed "I tested the live app" and clarified that another customer's case was not shown; three partial passes concern denial wording. Two product-context failures remain reported. Feedback receipt and documentation integration are complete; implementing or accepting every feedback item is not implied.

Human-judge agreement is **not yet calculated on matched responses**: the human reviewed live replies while the judge graded different saved responses. This is not missing human feedback. Formal source-contract approval and exact-saved-response calibration are separate outstanding decisions. No agreement percentage is invented.

This confirms handover of human review feedback to the project record, **not** a bank-support handoff, callback, or operational acknowledgement. Those require separate backend evidence.


Epic: Agent Observability & Traceability Dashboard

Specification version: 1.0

Date: October 30, 2026 (America/Los_Angeles)

Status: Proposed full specification, with a local synthetic implementation now available. Production identity, archival controls and institutional approval remain separate. See [local completion](LOCAL_COMPLETION_REPORT.md).

Current implementation: a separate local reviewer workspace provides bank-scoped
VIEWER/REVIEWER/ADMIN roles, recorded timelines, policy/access/tool evidence,
review notes and revisions, encrypted exports, source-bound human label review,
and configurable local alert rules. Its staff tokens are demo identity; no banking
rights, external webhook delivery or production archive approval is implied.

## Purpose and scope

Give an authorised internal reviewer a separate workspace to reconstruct what the assistant did, inspect the evidence behind its decisions and record a review outcome. The reviewer must not gain banking privileges through this workspace.

Initial scope is the local synthetic ResolveGuard demonstration: fraud/error intake, transaction questions, support requests and support delivery. Production identity, protected archival storage and external notification services require separate implementation and validation.

## Persona and permissions

The Agent Review Admin is an internal product-quality, operations, risk or compliance reviewer. Their primary question is: "What happened, what evidence supported it, and was the outcome appropriate?"

| Capability | Base role permission |
| --- | --- |
| Search sessions | Only assigned customer, business and environment scopes |
| Inspect conversation and execution | Masked messages, steps, policies and tool results |
| Review an interaction | Add findings, status changes, notes and escalation requests |
| Recorded playback | View captured events without re-executing tools |
| Synthetic replay | Only with a separate replay permission and isolated environment |
| Banking operations | No transfers, refunds, card blocks or customer-permission changes |
| Historical evidence | Cannot edit or delete captured traces |
| Deployment and policy changes | Cannot deploy models or change active policies through this role |

Additional privileges are assigned separately:

- Sensitive-data reviewer: controlled, purpose-bound access to necessary protected evidence.
- Audit exporter: permission to request and download approved evidence packages.
- Alert manager: permission to activate, disable or change alert rules.
- Replay operator: permission to run isolated, side-effect-free test replays.

Require individual staff authentication, MFA, time-limited sessions and server-side permission checks for every search, view, replay and export. Enforce tenant/business scope on queries and direct resource URLs. A known customer or trace ID does not grant access. Keep the reviewer identity distinct from the customer and the agent service identity.

Audit sensitive evidence access, searches, replay requests, exports and configuration changes. No shared admin account. The current sample-customer selector is not admin authentication. Staff sign-in is separate from customer KYC; a fixture labelled KYC VERIFIED is not identity proof.

## Dashboard structure

| View | Contents |
| --- | --- |
| Sessions | Search, filters, review priority, outcomes and review status |
| Session details | Customer conversation alongside chronological execution |
| Step details | Inputs, outputs, access checks, policies, timing and decision explanation |
| Reviews | Findings, evidence references, notes and decision history |
| Alerts and exports | Triggered alerts, delivery status and evidence-package requests |

Use plain-language labels by default. Place JSON and internal identifiers under "View technical details." Render messages and tool outputs as untrusted text, never executable HTML. Masking applies before telemetry storage or external publication, not only in the browser.

## System responsibilities and data flow

Customer application -> LangGraph and backend checks -> privacy filtering -> protected trace records -> scoped admin API -> reviewer dashboard.

Protected trace records also feed the alert evaluator. Review actions produce separate audit events. The export service combines permitted evidence, policies and review history into a protected package.

- LangGraph emits execution events and actual branch selections. Nodes are workflow steps; they must not be presented as independent autonomous agents unless that architecture exists.
- Banking backend emits authoritative access decisions and business results. The model cannot override access decisions.
- Pydantic validates versioned event, review, replay, alert-rule and export contracts at service boundaries.
- Trace ingestion applies field allowlists, masking, size limits and schema checks. Invalid events produce a visible ingestion failure rather than silently becoming valid evidence.
- Admin API enforces reviewer access independently of the customer-facing API.
- LangSmith can receive explicitly approved, masked diagnostic evidence. It is not the authoritative compliance archive.
- Replit, if used for the demo, hosts the UI/API. Hosting alone supplies neither staff IAM nor immutable evidence retention.
- Alert delivery and export encryption remain separate services with their own permissions and audit events.

## US-01: Session trace and step-by-step playback

As an Agent Review Admin, I want an end-to-end timeline so I can reconstruct the interaction and assess adherence to operational rules.

### Acceptance criteria

1. Search historical sessions by conversation/session reference, customer reference, date range, review priority, outcome, error type, model version and review status. Server-side scope applies to every filter and result count.
2. Selecting a session shows all available turns, execution attempts and nested steps in a sequential timeline or tree. Distinguish concurrent steps, retries, skipped steps and missing events.
3. Each step shows masked inputs/outputs, start/end timestamps, latency, outcome, parent span, attempt number and applicable model/tool/rule/application versions. Display "not captured" where evidence is absent.
4. Automatically mask/tokenise protected fields. Ordinary traces never contain passwords, tokens, PINs, card security codes or one-time codes.
5. Recorded playback makes no tool calls and changes no customer or business state.
6. Detect incomplete traces using sequence/completion metadata. Do not imply that missing events prove a check succeeded or failed.
7. Show customer-visible wording separately from internal responses. Include presentation-template version because the current web layer changes the internal wording.
8. Historical sessions lacking a review-priority calculation show "Not assessed." No fabricated historical score.

### Correlation identifiers

| Identifier | Purpose |
| --- | --- |
| Customer reference | Protected reference to the person, not an authentication secret |
| Conversation ID | Groups related messages |
| Turn ID | One customer message and its handling |
| Trace ID | One execution attempt |
| Span ID / parent span ID | One nested execution step |
| Business event reference | Saved report, support case or confirmed delivery |
| Replay ID / source trace ID | Separates a new test run from its historical source |

A retry can produce another attempt while pointing to the same durable business event. Never count it as a second report solely because another trace exists. Correlate without logging reusable customer session credentials.

### Review priority

Review priority is operational triage, not a fraud probability. Record contributing signals, calculation time and rule version. Proposed signals include access denials, missing outcome evidence, report-save failures and incomplete traces. A blocked unauthorised request can demonstrate a working guardrail; it is not automatically a confirmed breach.

## US-02: Tool calls and decision evidence

As an Agent Review Admin, I want to inspect tool activity and its supporting evidence so I can verify whether access and outcomes were justified.

### Acceptance criteria

1. Clicking a tool step opens the submitted request structure and returned response with protected values masked. Preserve field structure and distinguish omitted fields, redacted fields and unavailable evidence.
2. Show tool/schema versions, invocation source, validated parameters, result status, error/reason codes, retry information and committed event references.
3. Show customer authentication, exact-resource authorisation, agent tool entitlement, delegation and additional-verification results where applicable. Record which checks ran and which were not applicable.
4. Highlight blocked calls with a stable rejection reason, rule ID/version and evidence reference. Authorisation checks inside backend methods require explicit nested events; their occurrence must not be inferred only from the final tool result.
5. Show retrieved KB document/chunk IDs, source versions, text snapshots or protected snapshot references, effective dates, retrieval method, filters and ranking evidence. Identify the actual local keyword method; do not claim vector search or reranking unless implemented.
6. Distinguish policies retrieved, policies used in the answer and executable rules controlling actions. Retrieval alone does not establish influence.
7. Show versioned system/developer prompt templates and allowed masked model inputs/outputs. Banking tools receive their validated tool parameters, not necessarily the model's system prompt.
8. Show concise structured decision explanations supported by event references. Do not require or expose private model chain-of-thought or treat generated explanations as authoritative evidence.
9. A policy retrieved later cannot be presented as the cause of an earlier action. Earlier actions may instead reference the applicable versioned operating rule.
10. Missing evidence is labelled "Not captured"; historical steps are not reconstructed as facts from model guesses.

### Minimum event contract

Every event has schema version, unique event ID, environment, event time, ingestion time, source component, conversation/turn/trace/span IDs, parent span, sequence, event type, status, component version and data classification. Completed steps include duration; model calls include actual provider/model and prompt versions. Unknown usage/cost stays unknown, and mock execution is explicitly labelled.

Decision events add action, protected resource reference, decision, reason code, rule ID/version, evidence references and concise explanation. Retrieval events add query reference, product/jurisdiction/date filters, source IDs/versions, ranking and selection results. Business events add durable event references and confirmed/unknown/conflict outcomes.

Example proposed decision event:

```json
{
  "schema_version": "review-event-v1",
  "event_id": "EVENT-123",
  "trace_id": "TRACE-123",
  "span_id": "STEP-5",
  "event_type": "authorization_decision",
  "action": "get_transaction",
  "resource_ref": "PAYMENT-TOKEN-63",
  "decision": "DENY",
  "reason_code": "ACCOUNT_SCOPE_MISMATCH",
  "rule_id": "ACCESS-ACCOUNT-OWNER",
  "rule_version": "v1",
  "evidence_refs": ["AUTH-CHECK-123"],
  "explanation": "The payment is outside this customer's permitted account access.",
  "execution_mode": "SYNTHETIC"
}
```

This abbreviated example describes a proposal, not a currently emitted complete event.

## US-03: Review findings and audit exports

As an Agent Review Admin, I want to record findings and export evidence so authorised risk, fraud and compliance teams can review the interaction.

### Acceptance criteria

1. Maintain separate review statuses (Not reviewed, Under review, Review complete, Escalated) and findings (for example, suspected unsupported claim, incorrect retrieval, confirmed policy violation or access check behaved correctly).
2. An "Approved" label, if retained, means acceptance of the particular interaction only. It never grants production approval or approves the underlying policy/model. Distinguish suspected from confirmed violations.
3. Each review event includes authenticated reviewer ID/role, timestamp, target trace/span, previous/new status, note, reason and evidence references. Corrections append a new event pointing to the previous event.
4. Persist audit events append-only through the application; reject edits/deletions. Log attempted tampering and access failures. Apply concurrency controls so simultaneous reviews do not silently overwrite each other.
5. For production, protect the archive independently with restricted storage, retention enforcement and signed integrity manifests. A hash chain alone or application-level append-only SQLite does not prove immutability against privileged modification.
6. Use an approved retention schedule and legal-hold process rather than promising indefinite retention. Retention durations, residency and deletion procedures require organisational approval before production.
7. Export permission is separate from trace viewing. Record purpose, requester, filters, recipients, authorisation outcome, package creation and download activity. Expire download access.
8. Export JSON detail and/or CSV summary inside an authenticated encrypted package. CSV itself is not encrypted. Select encryption and key management through the approved platform; never bundle decryption keys with the package.
9. Include integrity verification instructions, a signed manifest where available and explicit gaps. Protect CSV exports against spreadsheet formula execution.

### Evidence package

- Manifest: scope, filters, requester, creation time, environment, versions and limitations.
- Masked conversation including the actual customer-visible reply.
- Correlated trace events, tool results and access decisions.
- Applicable policy snapshots and source versions.
- Durable business-event references and outcome evidence.
- Human review history and separately labelled automated findings.
- Integrity records and verification instructions.

Sensitive source evidence, if necessary and permitted, belongs in a separate restricted evidence store. Ordinary dashboards display masked structures. Controlled access to protected evidence is purpose-bound and audited; authentication secrets are never retained for diagnostic inspection.

## US-04: Automated error and anomaly alerts

As an Agent Review Admin with alert-management permission, I want configurable alerts so operations can assess unexpected behaviour promptly.

### Acceptance criteria

1. Rule builder supports event/reason code, threshold, time window, grouping, severity, destination, suppression period, owner and version. Changes are audited and validated.
2. Provide dry-run/test mode before activation. Differentiate an expected denied call from a suspected bypass or actual disclosure.
3. Proposed initial triggers: tool invocation outside agent permission; customer-visible success without confirmed business evidence; failed report save; both support destinations unavailable; repeated clarification; missing or broken trace sequences.
4. Proposed normal-operation target: create the local alert within five seconds of ingestion of the triggering event. This is a design target, not measured performance. Define separately the delivery target for each external destination.
5. Persist alerts before dispatch. Use an outbox/queue, retries, deduplication, delivery receipts, failed-delivery state and a dashboard fallback. Track occurrence time, detection time and delivery time separately.
6. Slack/Teams notifications contain a minimal summary and access-controlled dashboard link, never full conversations, payment details or sign-in secrets. Webhook secrets remain server-side and outside logs. Activating external destinations is a separate configured action.
7. Sentiment-drop or repeated-confusion alerts are estimates with detector version, evidence and limitations. They cannot alone establish misconduct or a compliance violation. Sentiment detection is not currently implemented.
8. Show suppression and acknowledgement history. Alert acknowledgement is not equivalent to resolving the underlying customer issue.

## Replay safety

Recorded playback only renders historical events. Test replay executes a new run against a frozen synthetic or approved de-identified snapshot with banking writes, webhooks and external side effects disabled by construction.

Use new run identifiers and storage namespaces. Link replay to source trace, dataset, policy snapshots, tool stubs, application/prompt/model versions and replay configuration. Re-executed model output can differ and is never substituted for the original evidence. Do not replay production authentication credentials. Restoring a customer conversation through the existing application service is not an admin playback mechanism because it can resume unfinished work.

## Compliance and product validation summaries

| Audience | Summary |
| --- | --- |
| Risk/compliance | Access decisions, policy versions, customer-impacting outcomes, findings, review history and evidence gaps |
| Product/engineering | Routing and retrieval quality, unsupported claims, latency, retries, repeated confusion and version comparisons |

Automated checks include evaluator versions, evidence references and limitations. Keep automated findings separate from human conclusions. Say "No issue detected by these checks" rather than declaring compliance without an authorised review basis. Report measured values separately from targets and distinguish mock runs from provider runs.

## Historical implementation alignment before local completion

The table below records the original gap assessment, not today's implementation
status. The local reviewer workspace, scoped demo staff access, recorded playback,
append-only reviews, encrypted exports and local alert queue are now implemented.
See [the completion report](LOCAL_COMPLETION_REPORT.md) for current verification
and remaining production decisions. Live tool replay and external notification
delivery are not enabled.

| Capability | Current state | Work needed |
| --- | --- | --- |
| LangGraph workflow | Implemented | Session-wide timeline and explicit branch evidence |
| Local nested spans/timing | Implemented | Unified event schema, correlation and completeness checks |
| Backend permissions | Demo enforcement implemented | Nested decision events for each access check |
| Policy retrieval | Implemented local keyword RAG | Historical snapshots and retrieved-versus-used links |
| Privacy | Basic sanitisation implemented | Field allowlists, coverage tests and restricted evidence access |
| Customer wording | Presentation layer implemented | Persist exact displayed response and presentation version |
| LangSmith | Explicit publishing adapter prepared | Approved masked integration; no authoritative audit-archive claim |
| Admin authentication/API/dashboard | Not implemented | Separate staff identity and scoped services |
| Review history/export protection | Not implemented | Audit records, integrity protection and encryption |
| Alert rules/delivery | Not implemented | Evaluator, queue, dashboard and optional destinations |
| Admin replay | Not implemented | Isolated playback and synthetic replay modes |

Existing references: `resolveguard/telemetry.py`, `workflow.py`, `backend.py`, `conversation.py`, `presentation.py`, `storage.py` and `langsmith_integration.py`. Original BRD/PRD files remain unchanged. This specification is an additive design; it does not claim all proposed controls exist in the current demo.

## Delivery sequence and validation

1. Event contracts and privacy rules: define Pydantic schemas and explicit event emission. Verify redaction, invalid-event handling, correlation and access-denial evidence.
2. Read-only admin workspace: implement reviewer identity/scopes, session search, timeline and playback. Verify direct-URL access denial, cross-scope isolation and zero playback side effects.
3. Decision evidence: link permissions, policy snapshots, executed branches and displayed responses. Verify chronology and unsupported-evidence labels.
4. Reviews and exports: append-only review events, correction history, protected packages and verification. Test concurrent reviews, denied exports and tamper detection.
5. Alerts: deterministic rules, durable queue and delivery states. Test threshold windows, duplicates, suppression, delivery failures and missing telemetry.
6. Isolated replay/comparison: frozen fixtures and separate storage. Verify no external tool effects and preserve original run evidence.

Use the existing 40 draft cases for trace coverage and add admin-specific access/privacy/replay tests. A passing mock evaluation is not independent model qualification or compliance approval.

## Decisions still required before production

- Identity provider, reviewer scope ownership and role-approval process.
- Approved privacy field classification and access to protected source evidence.
- Retention periods, legal holds, residency and archive-integrity platform.
- Encryption/key management, export recipients and download controls.
- Alert owners, thresholds, notification destinations and delivery objectives.
- Policy ownership, review workflow and version-approval authority.

These decisions do not block a clearly labelled local synthetic prototype. No cloud upload, webhook delivery or production replay is authorised merely by adding this specification.

## Reference guidance

Privacy and integrity controls are informed by [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) and [OpenTelemetry security guidance](https://opentelemetry.io/docs/security/). These are engineering references, not a statement of regulatory compliance.
