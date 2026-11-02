"""Resolution/QA boundaries used by the local customer-response gate.

Schema validity is not proof of authorization, backend commitment or redaction.
Only trusted services may construct verified outcomes from authoritative evidence.
"""
from datetime import datetime
from typing import Annotated, Literal, get_args
from pydantic import BeforeValidator, ConfigDict, Field, model_validator
from .contracts import StrictModel, Identifier, Text, Timestamp, Intent, array_to_tuple

PriorityTier = Literal['P1','P2','P3','P4']
IssueState = Literal['RESOLVED','UNRESOLVED','UNKNOWN']
ResolutionTrigger = Literal['UNRESOLVED','FAILED_OPERATION','HUMAN_REQUEST',
    'SUBMISSION_UNKNOWN','AUTH_UNFINISHED','QUEUE_UNAVAILABLE','REOPEN_REQUEST']


class ReviewContract(StrictModel):
    model_config = ConfigDict(frozen=True)


class EvidenceRef(ReviewContract):
    kind: Literal['POLICY','BACKEND_EVENT','TRACE','RUNTIME_CHECK','HUMAN_REVIEW','EVALUATION']
    reference: Identifier
    version: Identifier
    event_kind: Literal['CASE_CREATED','HANDOFF_ACKNOWLEDGED','ISSUE_RESOLVED',
        'CALLBACK_CONFIRMED','PRIORITY_ASSIGNED','REQUEST_RECONCILED','REPORT_CAPTURED'] | None = None
    resource_ref: Identifier | None = None

    @model_validator(mode='after')
    def backend_event_has_subject_and_kind(self):
        if self.kind=='BACKEND_EVENT' and (not self.event_kind or not self.resource_ref):
            raise ValueError('Backend evidence requires a typed event and resource reference')
        if self.kind!='BACKEND_EVENT' and self.event_kind is not None:
            raise ValueError('Only backend event evidence may assert an event kind')
        return self


Evidence = Annotated[tuple[EvidenceRef,...], BeforeValidator(array_to_tuple), Field(max_length=100)]


class PriorityProposal(ReviewContract):
    proposed_tier: PriorityTier
    reason_code: Identifier
    evidence: Evidence = Field(min_length=1)


class PriorityDecision(ReviewContract):
    """Backend decision, separate from the agent's proposal and any callback."""
    assigned_tier: PriorityTier
    queue_id: Identifier
    rule_id: Identifier
    rule_version: Identifier
    evidence: Evidence = Field(min_length=1)

    @model_validator(mode='after')
    def assignment_has_backend_record(self):
        if not any(e.kind=='BACKEND_EVENT' and e.event_kind=='PRIORITY_ASSIGNED' and e.resource_ref==self.queue_id for e in self.evidence):
            raise ValueError('Assigned priority requires a matching queue-assignment event')
        return self


class CallbackCommitment(ReviewContract):
    status: Literal['UNCONFIRMED','CONFIRMED']
    queue_id: Identifier | None = None
    commitment_id: Identifier | None = None
    window_start: Timestamp | None = None
    window_end: Timestamp | None = None
    confirmed_at: Timestamp | None = None
    evidence: Evidence = ()

    @model_validator(mode='after')
    def commitment_requires_backend_evidence(self):
        details=(self.queue_id,self.commitment_id,self.window_start,self.window_end,self.confirmed_at)
        if self.status=='UNCONFIRMED':
            if any(value is not None for value in details) or self.evidence:
                raise ValueError('Unconfirmed callbacks cannot carry a promised window or commitment')
        else:
            if any(value is None for value in details):
                raise ValueError('Confirmed callbacks require queue, commitment and aware timestamps')
            if not any(e.kind=='BACKEND_EVENT' and e.event_kind=='CALLBACK_CONFIRMED' and e.resource_ref==self.commitment_id for e in self.evidence):
                raise ValueError('Callback confirmation requires authoritative backend event evidence')
            start=datetime.fromisoformat(self.window_start.replace('Z','+00:00'))
            end=datetime.fromisoformat(self.window_end.replace('Z','+00:00'))
            if start>=end:
                raise ValueError('Callback end must be after start')
        return self


class ResolutionInput(ReviewContract):
    session_ref: Identifier
    turn_ref: Identifier
    bank_id: Literal['BOW','LEGACY_DEMO']
    intent: Intent
    summary: Text  # Caller must apply approved privacy filtering first.
    issue_state: IssueState
    triggers: Annotated[tuple[ResolutionTrigger,...], BeforeValidator(array_to_tuple), Field(min_length=1,max_length=7)]
    evidence: Evidence
    existing_case_ref: Identifier | None = None


class ResolutionOutcome(ReviewContract):
    bank_id: Literal['BOW','LEGACY_DEMO']
    issue_state: IssueState
    next_step_state: Literal['CASE_CONFIRMED','HANDOFF_ACKNOWLEDGED','APPROVED_FALLBACK','TRACKED_PENDING','UNKNOWN']
    next_action: Literal['NONE','CHECK_CASE','RECONCILE_SUBMISSION','REQUEST_HANDOFF',
                        'OFFER_APPROVED_CHANNEL','WAIT_FOR_UPDATE','REQUEST_CUSTOMER_INPUT']
    tracking_ref: Identifier | None = None
    case_ref: Identifier | None = None
    handoff_ref: Identifier | None = None
    next_owner: Identifier | None = None
    priority: PriorityDecision | None = None
    callback: CallbackCommitment
    evidence: Evidence

    @model_validator(mode='after')
    def outcome_requires_matching_kind_of_evidence(self):
        def event_matches(kind,resource):
            return resource is not None and any(e.kind=='BACKEND_EVENT' and e.event_kind==kind and e.resource_ref==resource for e in self.evidence)
        if self.next_step_state=='CASE_CONFIRMED' and not event_matches('CASE_CREATED',self.case_ref):
            raise ValueError('Case confirmation requires a case reference and backend evidence')
        if self.next_step_state=='HANDOFF_ACKNOWLEDGED' and (not self.next_owner or not event_matches('HANDOFF_ACKNOWLEDGED',self.handoff_ref)):
            raise ValueError('Handoff acknowledgement requires its reference, owner and backend evidence')
        if self.next_step_state=='TRACKED_PENDING' and not self.tracking_ref:
            raise ValueError('Tracked pending outcomes require a durable tracking reference')
        if self.next_step_state=='APPROVED_FALLBACK' and not any(e.kind=='POLICY' for e in self.evidence):
            raise ValueError('An approved fallback requires policy evidence')
        if self.issue_state=='RESOLVED' and not event_matches('ISSUE_RESOLVED',self.case_ref or self.tracking_ref):
            raise ValueError('Resolution requires backend outcome evidence; receipt alone is insufficient')
        if self.priority and self.next_owner and self.priority.queue_id!=self.next_owner:
            raise ValueError('Assigned priority queue and next owner must agree')
        if self.callback.status=='CONFIRMED':
            if not self.next_owner or self.callback.queue_id!=self.next_owner:
                raise ValueError('Confirmed callback queue must match the next owner')
        return self


CheckName = Literal['INTENT_ROUTING','ERROR_REPORT_PRESERVATION','AUTHORIZATION',
    'TOOL_CORRECTNESS','GROUNDING','ACTION_INTEGRITY','PRIVACY','CUSTOMER_EXPERIENCE']
REQUIRED_CHECKS = frozenset(get_args(CheckName))
CRITICAL_CHECKS = REQUIRED_CHECKS - {'INTENT_ROUTING','CUSTOMER_EXPERIENCE'}


class QACheck(ReviewContract):
    name: CheckName
    verdict: Literal['PASS','FAIL','NOT_EVALUABLE']
    severity: Literal['CRITICAL','MAJOR','MINOR']
    method: Literal['DETERMINISTIC','DETERMINISTIC_WITH_LLM','HUMAN','LLM_ADVISORY']
    reason_code: Identifier
    explanation: Annotated[str, Field(min_length=1,max_length=1500)]
    evidence: Evidence

    @model_validator(mode='after')
    def critical_checks_cannot_be_downgraded(self):
        if self.name in CRITICAL_CHECKS and self.severity!='CRITICAL':
            raise ValueError('Safety check severity cannot be downgraded')
        if self.verdict=='PASS' and not self.evidence:
            raise ValueError('Passing checks require evidence references')
        if self.name in CRITICAL_CHECKS and self.verdict=='PASS' and self.method=='LLM_ADVISORY':
            raise ValueError('Model opinion alone cannot establish a critical safety pass')
        return self


class QAReport(ReviewContract):
    bank_id: Literal['BOW','LEGACY_DEMO']
    report_id: Identifier
    session_ref: Identifier
    turn_ref: Identifier | None = None
    stage: Literal['PRE_SEND','POST_SESSION']
    trigger: Literal['DRAFT_READY','SESSION_ENDED','SESSION_ABANDONED','SESSION_EXPIRED','HANDOFF_BOUNDARY','IDLE_TIMEOUT']
    reviewed_at: Timestamp
    rubric_version: Identifier
    candidate_response_ref: Identifier | None = None
    context_snapshot_ref: Identifier | None = None
    checks: Annotated[tuple[QACheck,...], BeforeValidator(array_to_tuple), Field(min_length=8,max_length=8)]
    decision: Literal['APPROVE','REVISE','SAFE_FALLBACK','BLOCK','NEEDS_REVIEW','RECORD','ESCALATE']
    risk_level: Literal['LOW','MEDIUM','HIGH','CRITICAL']
    requires_human_review: bool

    @model_validator(mode='after')
    def gate_and_audit_are_distinct(self):
        if {check.name for check in self.checks}!=REQUIRED_CHECKS:
            raise ValueError('Every QA dimension must appear exactly once')
        critical_failure=any(c.verdict=='FAIL' and c.severity=='CRITICAL' for c in self.checks)
        critical_unknown=any(c.verdict=='NOT_EVALUABLE' and c.severity=='CRITICAL' for c in self.checks)
        other_gap=any(c.verdict!='PASS' for c in self.checks)
        expected_risk='CRITICAL' if critical_failure else 'HIGH' if critical_unknown else 'MEDIUM' if other_gap else 'LOW'
        if self.risk_level!=expected_risk:
            raise ValueError('Risk level must reflect safety failures and missing evidence')
        if (critical_failure or critical_unknown) and not self.requires_human_review:
            raise ValueError('Critical failures or uncertainty require human review')
        if self.stage=='PRE_SEND':
            if self.trigger!='DRAFT_READY' or not self.turn_ref or not self.candidate_response_ref or not self.context_snapshot_ref:
                raise ValueError('Pre-send review must identify the exact turn and candidate response')
            if self.decision not in {'APPROVE','REVISE','SAFE_FALLBACK','BLOCK','NEEDS_REVIEW'}:
                raise ValueError('Invalid pre-send gate decision')
            if self.decision=='APPROVE' and any(c.verdict=='FAIL' or c.name in CRITICAL_CHECKS and c.verdict!='PASS' for c in self.checks):
                raise ValueError('Failed or unverified safety checks cannot approve delivery')
            if critical_failure and self.decision not in {'BLOCK','SAFE_FALLBACK'}:
                raise ValueError('Critical failures must block the candidate or require a separately reviewed fallback')
        else:
            if self.trigger=='DRAFT_READY' or self.candidate_response_ref is not None:
                raise ValueError('Post-session review is an audit, not response approval')
            if self.decision not in {'RECORD','ESCALATE','NEEDS_REVIEW'}:
                raise ValueError('Invalid post-session decision')
            if critical_failure and self.decision!='ESCALATE':
                raise ValueError('Post-session critical failures must escalate internally')
            if critical_unknown and self.decision=='RECORD':
                raise ValueError('Missing critical evidence requires review or escalation')
        return self
