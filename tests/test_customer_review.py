import json
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from resolveguard.backend import Backend
from resolveguard.contracts import Request
from resolveguard.customer_review import CustomerReview
from resolveguard.presentation import customer_cards
from resolveguard.storage import Store
from resolveguard.web import create_app


class CustomerReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'review.sqlite3'
        self.store = Store(self.path)
        self.review = CustomerReview(self.store)
        self.backend = Backend(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def gate(self, payload, **extra):
        args = dict(binding='browser-one', sid='SESS-001', backend=self.backend,
                    bank_id='LEGACY_DEMO', request_key='turn-one', access_state='VERIFIED')
        return self.review.gate(payload, **dict(args, **extra))

    def test_forged_report_is_blocked_and_fallback_separately_approved(self):
        payload = {'response': 'Your report is saved', 'report': {'status': 'OK', 'event_id': 'DEMO-REPORT-forged'}}
        result = self.gate(payload)
        self.assertEqual(result['response_state'], 'REVIEW_REQUIRED')
        with self.store.connect() as db:
            rows = [json.loads(r[0]) for r in db.execute('SELECT payload FROM customer_reviews ORDER BY rowid')]
        self.assertEqual([r['qa']['decision'] for r in rows], ['SAFE_FALLBACK', 'APPROVE'])
        self.assertNotIn('Your report is saved', json.dumps(rows))

    def test_real_event_owned_by_another_customer_cannot_be_claimed(self):
        req = Request(message='A payment is wrong', request_key='capture', session_id='SESS-002')
        report = self.backend.capture(req)
        result = self.gate({'response': 'Saved', 'report': report})
        self.assertEqual(result['response_state'], 'REVIEW_REQUIRED')

    def test_changed_card_and_expired_access_are_blocked(self):
        req = Request(message='Read payment', request_key='read', session_id='SESS-001')
        record = next(self.backend.transaction(req, t['transaction_id'])['data'] for t in self.backend.bank.transactions
                      if self.backend.transaction(req, t['transaction_id'])['status'] == 'OK')
        cards = customer_cards({'records': [dict(record, kind='transaction')]})
        candidate = {'response': 'Payment details', 'cards': cards}
        self.assertEqual(self.gate(candidate), candidate)
        cards[0]['amount'] = '$999,999.00 USD'
        self.assertEqual(self.gate(candidate)['response_state'], 'REVIEW_REQUIRED')
        self.assertEqual(self.gate(candidate, access_state='SESSION_EXPIRED')['cards'], [])

    def test_error_report_cannot_be_silently_dropped(self):
        result = self.gate({'response': 'Here are the payment details'}, message='selected charge is incorrectly applied')
        self.assertEqual(result['response_state'], 'REVIEW_REQUIRED')

    def test_resolution_receipt_does_not_resolve_issue_or_promise_callback(self):
        req = Request(message='This charge is wrong', request_key='capture', session_id='SESS-001')
        report = self.backend.capture(req)
        handoff = self.backend.handoff(req, report, urgent=True)
        self.gate({'response': 'Report saved', 'report': report, 'handoff': handoff})
        with self.store.connect() as db:
            payload = json.loads(db.execute('SELECT payload FROM customer_reviews').fetchone()[0])
        self.assertEqual(payload['resolution']['issue_state'], 'UNRESOLVED')
        self.assertEqual(payload['resolution']['callback']['status'], 'UNCONFIRMED')
        self.assertEqual(payload['resolution']['priority']['assigned_tier'],'P2')
        with self.store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM demo_assignments').fetchone()[0],1)

    def test_end_event_survives_worker_restart_and_is_idempotent(self):
        self.gate({'response': 'Which product do you mean?'})
        self.review.close('browser-one')
        restarted = CustomerReview(Store(self.path))
        restarted.process_pending()
        restarted.process_pending()
        with self.store.connect() as db:
            jobs = db.execute('SELECT * FROM session_audit_jobs').fetchall()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['status'], 'DONE')
        self.assertEqual(jobs[0]['attempts'], 1)
        self.assertEqual(json.loads(jobs[0]['result'])[0]['stage'], 'POST_SESSION')
        self.assertEqual(json.loads(jobs[0]['result'])[0]['decision'], 'RECORD')
        self.assertFalse(json.loads(jobs[0]['result'])[0]['requires_human_review'])

    def test_failed_worker_job_is_retained_and_retryable(self):
        self.gate({'response': 'Which product?'})
        self.review.close('browser-one')
        with self.store.connect() as db:
            original = db.execute('SELECT payload FROM customer_reviews').fetchone()[0]
            db.execute("UPDATE customer_reviews SET payload='invalid json'")
        self.review.process_pending()
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM session_audit_jobs').fetchone()[0], 'FAILED')
            db.execute('UPDATE customer_reviews SET payload=?', (original,))
        self.review.process_pending()
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM session_audit_jobs').fetchone()[0], 'DONE')

    def test_public_chat_reset_and_signout_create_session_audits(self):
        with TestClient(create_app(self.path)) as client:
            client.post('/api/session', json={})
            for index in range(2):
                response = client.post('/api/chat', json={'message': 'What is the monthly fee?', 'request_key': f'public-{index}', 'bank_id': 'BOW'})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(response.json()['choose_product'])
                if index == 0:
                    client.post('/api/conversation/reset')
                else:
                    client.post('/api/session', json={})
        with self.store.connect() as db:
            jobs = db.execute('SELECT status FROM session_audit_jobs').fetchall()
        self.assertEqual([r[0] for r in jobs], ['DONE', 'DONE'])

    def test_changed_policy_text_and_cross_bank_sources_are_blocked(self):
        from resolveguard.bow_knowledge import BowKnowledge
        knowledge = BowKnowledge()
        candidate = knowledge.answer('What is the monthly maintenance fee?', 'BOW-CHK-001', '2026-10-30')
        self.assertEqual(self.gate(candidate, bank_id='BOW'), candidate)
        candidate['source_details'][0]['summary'] = 'Invented fee waiver'
        self.assertEqual(self.gate(candidate, bank_id='BOW')['response_state'], 'REVIEW_REQUIRED')
        self.assertEqual(self.gate(candidate, bank_id='LEGACY_DEMO')['response_state'], 'REVIEW_REQUIRED')

    def test_unbacked_callback_promise_is_blocked(self):
        result = self.gate({'response': 'We will call you within two hours.'})
        self.assertEqual(result['response_state'], 'REVIEW_REQUIRED')

    def test_wrong_answer_with_valid_sources_is_blocked(self):
        from resolveguard.bow_knowledge import BowKnowledge
        k=BowKnowledge()
        for question, change in (
            ('What is the monthly maintenance fee?', lambda t:t.replace('$6.00','$999.00')),
            ('What are the fee waiver rules?', lambda t:t.replace(' or ',' and ')),
        ):
            candidate=k.answer(question,'BOW-CHK-001','2026-10-30')
            candidate['response']=change(candidate['response'])
            self.assertEqual(self.gate(candidate,bank_id='BOW',message=question)['response_state'],'REVIEW_REQUIRED')

    def test_idle_boundary_enqueues_once_without_clearing_bank_records(self):
        self.gate({'response': 'Which product?'})
        self.review.expire_idle(idle_seconds=0)
        self.review.expire_idle(idle_seconds=0)
        self.review.process_pending()
        with self.store.connect() as db:
            jobs = db.execute('SELECT trigger,status FROM session_audit_jobs').fetchall()
        self.assertEqual([(r[0], r[1]) for r in jobs], [('IDLE_TIMEOUT', 'DONE')])

    def test_reset_during_request_keeps_late_review_in_original_conversation(self):
        self.review.start_turn('browser-one','late-request')
        self.review.close('browser-one')
        self.review.process_pending()
        with self.store.connect() as db:self.assertEqual(db.execute('SELECT status FROM session_audit_jobs').fetchone()[0],'PENDING')
        self.gate({'response':'Which product?'},request_key='late-request')
        self.review.process_pending()
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT generation FROM customer_reviews').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT status FROM session_audit_jobs').fetchone()[0],'DONE')

    def test_late_changed_evidence_appends_an_audit_revision(self):
        self.gate({'response':'Which product?'})
        self.review.close('browser-one');self.review.process_pending()
        self.gate({'response':'Choose a checking product.'})
        self.review.process_pending()
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM session_audit_reports').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT audit_revision FROM session_audit_jobs').fetchone()[0],2)

    def test_failed_turn_without_reply_requires_review_not_a_clean_audit(self):
        self.review.start_turn('browser-one','failed-request','BOW')
        self.review.fail_turn('browser-one','failed-request');self.review.close('browser-one');self.review.process_pending()
        with self.store.connect() as db:result=json.loads(db.execute('SELECT result FROM session_audit_jobs').fetchone()[0])[0]
        self.assertEqual(result['risk_level'],'HIGH')
        self.assertEqual(result['decision'],'NEEDS_REVIEW')
