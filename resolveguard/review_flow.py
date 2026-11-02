"""Pure transition specification. No banking tools, model calls or UI wiring."""
from typing import Literal
from pydantic import Field
from .contracts import Identifier
from .resolution_contracts import ReviewContract, IssueState, ResolutionOutcome, QAReport

Stage = Literal['ASSESS_ISSUE','RESOLUTION','DRAFT_RESPONSE','PRE_SEND_QA',
    'SAFE_FALLBACK_DRAFT','DELIVER_RESPONSE','SESSION_OPEN','POST_SESSION_QA',
    'AUDIT_RECORDED','HUMAN_REVIEW']


class ReviewCheckpoint(ReviewContract):
    bank_id: Literal['BOW','LEGACY_DEMO']
    stage: Stage
    session_ref: Identifier
    turn_ref: Identifier
    issue_state: IssueState
    candidate_response_ref: Identifier | None = None
    context_snapshot_ref: Identifier | None = None
    resolution: ResolutionOutcome | None = None
    qa: QAReport | None = None
    rewrite_count: int = Field(default=0,ge=0,le=1)
    fallback_used: bool = False
    session_ended: bool = False


def _bound_pre_send_review(state: ReviewCheckpoint) -> QAReport:
    report=state.qa
    if (not report or report.stage!='PRE_SEND' or report.bank_id!=state.bank_id or report.session_ref!=state.session_ref
            or report.turn_ref!=state.turn_ref or report.candidate_response_ref!=state.candidate_response_ref
            or report.context_snapshot_ref!=state.context_snapshot_ref):
        raise ValueError('Delivery review must match the current session, turn, candidate and context')
    return report


def next_review_stage(state: ReviewCheckpoint) -> Stage:
    """Describe the next allowed step; caller must perform/persist that step.

    Ref values must be backend-generated fingerprints, never client assertions.
    A delivery transition does not send a message or modify a banking record.
    """
    state=ReviewCheckpoint.model_validate(state)
    if state.stage=='ASSESS_ISSUE':
        return 'DRAFT_RESPONSE' if state.issue_state=='RESOLVED' else 'RESOLUTION'
    if state.stage=='RESOLUTION':
        if state.resolution is None or state.resolution.bank_id!=state.bank_id:
            raise ValueError('Resolution step must record a verified outcome or explicit uncertainty')
        return 'DRAFT_RESPONSE'
    if state.stage in {'DRAFT_RESPONSE','SAFE_FALLBACK_DRAFT'}:
        if not state.candidate_response_ref or not state.context_snapshot_ref:
            raise ValueError('Draft requires a candidate fingerprint and context snapshot')
        return 'PRE_SEND_QA'
    if state.stage=='PRE_SEND_QA':
        decision=_bound_pre_send_review(state).decision
        if decision=='APPROVE':return 'DELIVER_RESPONSE'
        if decision=='REVISE' and state.rewrite_count==0:return 'DRAFT_RESPONSE'
        if decision=='SAFE_FALLBACK' and not state.fallback_used:return 'SAFE_FALLBACK_DRAFT'
        return 'HUMAN_REVIEW'
    if state.stage=='DELIVER_RESPONSE':
        if _bound_pre_send_review(state).decision!='APPROVE':
            raise ValueError('A blocked or unreviewed draft cannot be delivered')
        return 'POST_SESSION_QA' if state.session_ended else 'SESSION_OPEN'
    if state.stage=='SESSION_OPEN':
        return 'POST_SESSION_QA' if state.session_ended else 'ASSESS_ISSUE'
    if state.stage=='POST_SESSION_QA':
        if not state.session_ended:
            raise ValueError('A post-session audit requires an explicit session-end event')
        if not state.qa or state.qa.stage!='POST_SESSION' or state.qa.bank_id!=state.bank_id or state.qa.session_ref!=state.session_ref:
            raise ValueError('Session audit requires a matching post-session report')
        return 'AUDIT_RECORDED'
    return state.stage
