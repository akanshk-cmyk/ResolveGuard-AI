"""Contract and transition guarantees, with no live services or model calls."""
import copy
import unittest
from pydantic import ValidationError
from resolveguard.resolution_contracts import (
    CallbackCommitment, EvidenceRef, PriorityDecision, PriorityProposal,
    QACheck, QAReport, ResolutionOutcome, REQUIRED_CHECKS, CRITICAL_CHECKS,
)
from resolveguard.review_flow import ReviewCheckpoint, next_review_stage


def evidence(kind='RUNTIME_CHECK',event_kind=None,resource_ref=None):
    return {'kind':kind,'reference':'evidence-001','version':'v1',
            'event_kind':event_kind,'resource_ref':resource_ref}


def qa_payload(stage='PRE_SEND'):
    return {'bank_id':'BOW','report_id':'qa-001','session_ref':'session-001','turn_ref':'turn-001',
        'stage':stage,'trigger':'DRAFT_READY' if stage=='PRE_SEND' else 'SESSION_ENDED',
        'reviewed_at':'2026-10-31T18:00:00Z','rubric_version':'review-v1',
        'candidate_response_ref':'sha256-draft-1' if stage=='PRE_SEND' else None,
        'context_snapshot_ref':'sha256-context-1',
        'checks':[{'name':name,'verdict':'PASS',
                   'severity':'CRITICAL' if name in CRITICAL_CHECKS else 'MINOR',
                   'method':'DETERMINISTIC','reason_code':'VERIFIED',
                   'explanation':'Supported by test runtime evidence.', 'evidence':[evidence()]}
                  for name in sorted(REQUIRED_CHECKS)],
        'decision':'APPROVE' if stage=='PRE_SEND' else 'RECORD',
        'risk_level':'LOW','requires_human_review':False}


def alter_check(payload,name,verdict):
    next(c for c in payload['checks'] if c['name']==name)['verdict']=verdict


class ResolutionContractTests(unittest.TestCase):
    def test_unconfirmed_callback_cannot_make_time_promise(self):
        self.assertEqual(CallbackCommitment(status='UNCONFIRMED').status,'UNCONFIRMED')
        with self.assertRaises(ValidationError):
            CallbackCommitment(status='UNCONFIRMED',window_end='2026-11-01T18:00:00Z')

    def callback(self):
        return {'status':'CONFIRMED','queue_id':'support','commitment_id':'callback-1',
                'window_start':'2026-11-01T10:00:00-08:00','window_end':'2026-11-01T11:00:00-08:00',
                'confirmed_at':'2026-10-31T18:00:00Z',
                'evidence':[evidence('BACKEND_EVENT','CALLBACK_CONFIRMED','callback-1')]}

    def test_confirmed_callback_requires_matching_backend_record(self):
        payload=self.callback()
        self.assertEqual(CallbackCommitment.model_validate(payload).queue_id,'support')
        for change in ({'evidence':[evidence()]},{'commitment_id':'different'},
                       {'window_start':'2026-11-01T12:00:00-08:00'},
                       {'window_end':'2026-11-01T19:00:00'}, {'queue_id':None}):
            with self.subTest(change=change),self.assertRaises(ValidationError):
                CallbackCommitment.model_validate({**payload,**change})

    def test_priority_is_not_a_callback_and_model_proposal_is_not_assignment(self):
        proposal=PriorityProposal(proposed_tier='P1',reason_code='ONGOING_EXPOSURE',evidence=[evidence()])
        with self.assertRaises(ValidationError):PriorityDecision.model_validate(proposal.model_dump())
        with self.assertRaises(ValidationError):
            PriorityDecision(assigned_tier='P1',queue_id='fraud',rule_id='risk-rule',rule_version='v1',evidence=[evidence()])
        assigned=PriorityDecision(assigned_tier='P1',queue_id='fraud',rule_id='risk-rule',rule_version='v1',
                                 evidence=[evidence('BACKEND_EVENT','PRIORITY_ASSIGNED','fraud')])
        self.assertNotIn('callback',assigned.model_dump())

    def outcome(self):
        return {'bank_id':'BOW','issue_state':'UNRESOLVED','next_step_state':'HANDOFF_ACKNOWLEDGED',
                'next_action':'WAIT_FOR_UPDATE','handoff_ref':'handoff-1','next_owner':'support',
                'callback':{'status':'UNCONFIRMED'},
                'evidence':[evidence('BACKEND_EVENT','HANDOFF_ACKNOWLEDGED','handoff-1')]}

    def test_handoff_receipt_does_not_resolve_issue(self):
        payload=self.outcome()
        self.assertEqual(ResolutionOutcome.model_validate(payload).issue_state,'UNRESOLVED')
        with self.assertRaises(ValidationError):
            ResolutionOutcome.model_validate({**payload,'issue_state':'RESOLVED'})

    def test_callback_and_owner_must_agree(self):
        payload=self.outcome();payload['callback']=self.callback();payload['callback']['queue_id']='other-team'
        with self.assertRaises(ValidationError):ResolutionOutcome.model_validate(payload)

    def test_no_unverified_case_or_untracked_pending_state(self):
        payload=self.outcome()
        for extra in ({'next_step_state':'CASE_CONFIRMED','case_ref':'case-1'},
                      {'next_step_state':'TRACKED_PENDING'}, {'next_action':'ISSUE_REFUND'}):
            with self.subTest(extra=extra),self.assertRaises(ValidationError):
                ResolutionOutcome.model_validate({**payload,**extra})


class QAContractTests(unittest.TestCase):
    def test_valid_report_roundtrips_without_coercion(self):
        report=QAReport.model_validate(qa_payload())
        self.assertEqual(QAReport.model_validate_json(report.model_dump_json()),report)
        payload=qa_payload();payload['requires_human_review']='false'
        with self.assertRaises(ValidationError):QAReport.model_validate(payload)

    def test_safety_failure_cannot_be_averaged_with_good_tone(self):
        payload=qa_payload();alter_check(payload,'AUTHORIZATION','FAIL')
        payload.update(risk_level='CRITICAL',requires_human_review=True)
        with self.assertRaises(ValidationError):QAReport.model_validate(payload)
        payload['decision']='BLOCK'
        self.assertEqual(QAReport.model_validate(payload).decision,'BLOCK')
        payload['risk_level']='LOW'
        with self.assertRaises(ValidationError):QAReport.model_validate(payload)

    def test_missing_safety_evidence_is_not_a_pass(self):
        payload=qa_payload();alter_check(payload,'PRIVACY','NOT_EVALUABLE')
        payload.update(risk_level='HIGH',requires_human_review=True)
        with self.assertRaises(ValidationError):QAReport.model_validate(payload)
        payload['decision']='NEEDS_REVIEW'
        self.assertEqual(QAReport.model_validate(payload).risk_level,'HIGH')

    def test_unlabeled_live_intent_is_explicit_not_invented_accuracy(self):
        payload=qa_payload();alter_check(payload,'INTENT_ROUTING','NOT_EVALUABLE')
        payload['risk_level']='MEDIUM'
        self.assertEqual(QAReport.model_validate(payload).risk_level,'MEDIUM')
        self.assertTrue(any(c.verdict=='NOT_EVALUABLE' for c in QAReport.model_validate(payload).checks))

    def test_missing_or_duplicate_checks_are_rejected(self):
        for mode in ('missing','duplicate'):
            payload=qa_payload()
            if mode=='missing':payload['checks'].pop()
            else:payload['checks'][0]=copy.deepcopy(payload['checks'][1])
            with self.assertRaises(ValidationError):QAReport.model_validate(payload)

    def test_llm_opinion_cannot_establish_critical_safety(self):
        check=next(c for c in qa_payload()['checks'] if c['name']=='AUTHORIZATION')
        for change in ({'method':'LLM_ADVISORY'},{'severity':'MINOR'},{'evidence':[]}):
            with self.subTest(change=change),self.assertRaises(ValidationError):QACheck.model_validate({**check,**change})

    def test_post_session_audit_cannot_approve_customer_reply(self):
        payload=qa_payload('POST_SESSION')
        self.assertEqual(QAReport.model_validate(payload).decision,'RECORD')
        payload['decision']='APPROVE'
        with self.assertRaises(ValidationError):QAReport.model_validate(payload)
        alter_check(payload,'ACTION_INTEGRITY','FAIL')
        payload.update(decision='RECORD',risk_level='CRITICAL',requires_human_review=True)
        with self.assertRaises(ValidationError):QAReport.model_validate(payload)
        payload['decision']='ESCALATE'
        self.assertEqual(QAReport.model_validate(payload).decision,'ESCALATE')


class ReviewFlowTests(unittest.TestCase):
    def checkpoint(self,**changes):
        return ReviewCheckpoint.model_validate({'bank_id':'BOW','stage':'PRE_SEND_QA','session_ref':'session-001',
            'turn_ref':'turn-001','issue_state':'UNRESOLVED','candidate_response_ref':'sha256-draft-1',
            'context_snapshot_ref':'sha256-context-1','qa':qa_payload(),**changes})

    def test_only_unresolved_or_unknown_issues_activate_resolution(self):
        self.assertEqual(next_review_stage(self.checkpoint(stage='ASSESS_ISSUE')),'RESOLUTION')
        self.assertEqual(next_review_stage(self.checkpoint(stage='ASSESS_ISSUE',issue_state='UNKNOWN')),'RESOLUTION')
        self.assertEqual(next_review_stage(self.checkpoint(stage='ASSESS_ISSUE',issue_state='RESOLVED')),'DRAFT_RESPONSE')

    def test_approval_is_bound_to_exact_turn_draft_and_context(self):
        self.assertEqual(next_review_stage(self.checkpoint()),'DELIVER_RESPONSE')
        for change in ({'bank_id':'LEGACY_DEMO'},{'turn_ref':'other-turn'},{'session_ref':'other-session'},
                       {'candidate_response_ref':'edited-draft'},{'context_snapshot_ref':'changed-access'}):
            with self.subTest(change=change),self.assertRaises(ValueError):next_review_stage(self.checkpoint(**change))

    def test_revision_is_bounded_and_fallback_requires_new_review(self):
        payload=qa_payload();payload['decision']='REVISE'
        self.assertEqual(next_review_stage(self.checkpoint(qa=payload)),'DRAFT_RESPONSE')
        self.assertEqual(next_review_stage(self.checkpoint(qa=payload,rewrite_count=1)),'HUMAN_REVIEW')
        payload['decision']='SAFE_FALLBACK'
        self.assertEqual(next_review_stage(self.checkpoint(qa=payload)),'SAFE_FALLBACK_DRAFT')
        self.assertEqual(next_review_stage(self.checkpoint(qa=payload,fallback_used=True)),'HUMAN_REVIEW')
        with self.assertRaises(ValueError):next_review_stage(self.checkpoint(stage='DELIVER_RESPONSE',qa=payload))

    def test_session_end_runs_audit_without_marking_issue_resolved(self):
        state=self.checkpoint(stage='DELIVER_RESPONSE',session_ended=True)
        self.assertEqual(next_review_stage(state),'POST_SESSION_QA')
        self.assertEqual(state.issue_state,'UNRESOLVED')
        audit=self.checkpoint(stage='POST_SESSION_QA',session_ended=True,qa=qa_payload('POST_SESSION'))
        self.assertEqual(next_review_stage(audit),'AUDIT_RECORDED')
        with self.assertRaises(ValueError):next_review_stage(self.checkpoint(stage='POST_SESSION_QA'))


if __name__=='__main__':unittest.main()
