import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from resolveguard.web import create_app
from resolveguard.storage import Store


class GuestFirstTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.database=Path(self.temp.name)/'guest.sqlite3'
        self.client=TestClient(create_app(self.database));self.client.__enter__()
        self.client.post('/api/session',json={})
    def tearDown(self):
        self.client.__exit__(None,None,None);self.temp.cleanup()
    def ask(self,message,key='question',**extra):
        return self.client.post('/api/chat',json={'message':message,'request_key':key,**extra})
    def sign_in(self,pending_id,profile='customer-one'):
        return self.client.post('/api/auth/demo-sign-in',json={'profile':profile,'pending_id':pending_id})
    def resume(self,pending_id):return self.client.post('/api/auth/resume',json={'pending_id':pending_id})

    def test_new_session_defaults_to_guest(self):
        state=self.client.get('/api/session').json()
        self.assertEqual(state['profile'],'signed-out')
        self.assertEqual(state['access_state'],'AUTH_REQUIRED')
        self.assertIsNone(state['pending_id'])

    def test_public_fee_answer_does_not_read_customer_records(self):
        with patch('resolveguard.backend.Backend.transaction') as tx,patch('resolveguard.backend.Backend.case_status') as case:
            first=self.ask('What is the monthly maintenance fee?').json()
            self.assertTrue(first['choose_product']);self.assertNotIn('$12',first['response'])
            result=self.ask('Checking account','product-choice').json()
        tx.assert_not_called();case.assert_not_called()
        self.assertFalse(result['auth_required']);self.assertEqual(result['data_scope'],'PUBLIC')
        self.assertIn('$12',result['response']);self.assertIn('demo',result['response'])
        self.assertTrue(result['source_details'][0]['effective_date'])
        self.assertEqual(self.client.get('/api/session').json()['profile'],'signed-out')

    def test_public_question_ignores_stale_payment_selection_without_disclosure(self):
        result=self.ask('What are the fee waiver rules?',transaction_ids=['TXN-002-01']).json()
        self.assertFalse(result['auth_required']);self.assertEqual(result['cards'],[])
        self.assertNotIn('TXN-002',result['response'])

    def test_personal_fee_request_is_saved_before_any_account_read(self):
        with patch('resolveguard.backend.Backend.transaction') as tx:
            result=self.ask('Why was I charged $12?').json()
        tx.assert_not_called()
        self.assertEqual(result['response'],'Please sign in securely to view your account details.')
        self.assertTrue(result['pending_id'])
        self.assertEqual(self.resume(result['pending_id']).status_code,403)

    def test_original_fee_request_resumes_after_sign_in_without_new_message(self):
        first=self.ask('Why was I charged $12?').json();key=first['pending_id']
        self.assertEqual(self.sign_in(key).status_code,200)
        result=self.resume(key).json()
        self.assertTrue(result['resumed']);self.assertEqual(result['original_request'],'Why was I charged $12?')
        self.assertEqual(result['cards'][0]['amount'],'$12.00 USD')
        self.assertFalse(result['auth_required'])

    def test_recent_transactions_resume_with_current_customer_permissions(self):
        key=self.ask('Show my recent transactions').json()['pending_id']
        self.sign_in(key)
        result=self.resume(key).json()
        self.assertEqual(len(result['cards']),5)
        self.assertFalse(any(c['reference'].startswith('TXN-002') for c in result['cards']))

    def test_successful_sign_in_does_not_authorise_another_customers_payment(self):
        key=self.ask('Show this transaction',transaction_ids=['TXN-002-01']).json()['pending_id']
        self.sign_in(key)
        result=self.resume(key).json()
        self.assertEqual(result['cards'],[])
        self.assertEqual(result['response_state'],'ACCESS_DENIED')

    def test_pending_request_cannot_be_stolen_or_modified_by_another_browser(self):
        key=self.ask('Show my recent transactions').json()['pending_id']
        with TestClient(self.client.app) as other:
            other.post('/api/session',json={})
            denied=other.post('/api/auth/demo-sign-in',json={'profile':'customer-one','pending_id':key})
            self.assertEqual(denied.status_code,403)
        self.sign_in(key)
        changed=self.client.post('/api/auth/resume',json={'pending_id':key,'message':'Show another account'})
        self.assertEqual(changed.status_code,422)

    def test_additional_verification_blocks_resume_until_backend_confirmation(self):
        key=self.ask('Show my recent transactions').json()['pending_id']
        self.sign_in(key,'needs-verification')
        blocked=self.resume(key).json()
        self.assertTrue(blocked['auth_required']);self.assertEqual(blocked['cards'],[])
        self.client.post('/api/session/verification',json={'action':'cancel'})
        self.assertTrue(self.resume(key).json()['auth_required'])
        self.client.post('/api/session/verification',json={'action':'confirm'})
        self.assertTrue(self.resume(key).json()['cards'])

    def test_already_signed_in_step_up_resumes_without_repeating_sign_in(self):
        self.client.post('/api/session',json={'profile':'needs-verification'})
        key=self.ask('Show my recent transactions').json()['pending_id']
        self.assertTrue(self.resume(key).json()['auth_required'])
        self.client.post('/api/session/verification',json={'action':'confirm'})
        result=self.resume(key).json()
        self.assertTrue(result['resumed']);self.assertTrue(result['cards'])

    def test_cancelling_sign_in_preserves_public_access(self):
        key=self.ask('Show my recent transactions').json()['pending_id']
        self.client.post('/api/auth/cancel',json={'pending_id':key})
        self.assertIsNone(self.client.get('/api/session').json()['pending_id'])
        result=self.ask('What are the fee waiver rules?','public').json()
        self.assertFalse(result['auth_required'])
        self.assertEqual(self.client.get('/api/session').json()['profile'],'signed-out')

    def test_guest_report_preserves_original_and_selectors_without_account_reads(self):
        statement='I did not authorize this debit and want a human'
        with patch('resolveguard.backend.Backend.transaction') as tx:
            result=self.ask(statement,transaction_ids=['TXN-001-01']).json()
        tx.assert_not_called()
        self.assertEqual(result['report']['report_capture_status'],'CAPTURED')
        self.assertEqual(result['report']['verification_status'],'PENDING')
        with Store(self.database).connect() as db:
            payload=json.loads(db.execute("SELECT payload FROM events WHERE kind='report'").fetchone()['payload'])
        self.assertEqual(payload['original_statement'],statement)
        self.assertEqual(payload['reported_transaction_ids'],['TXN-001-01'])
        self.sign_in(result['pending_id']);self.resume(result['pending_id'])
        with Store(self.database).connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE kind='report'").fetchone()[0],1)

    def test_guest_report_without_record_request_does_not_demand_sign_in(self):
        result=self.ask('I was charged twice for the same purchase').json()
        self.assertEqual(result['report']['status'],'OK');self.assertFalse(result['auth_required'])

    def test_missing_rate_is_not_invented_or_hidden_behind_sign_in(self):
        result=self.ask('What is the current savings interest rate?').json()
        self.assertFalse(result['auth_required']);self.assertNotIn('%',result['response'])
        self.assertTrue(result['choose_product'])
        result=self.ask('Original demo savings account','product-choice').json()
        self.assertIn('No approved, current published savings rate',result['response'])

    def test_configured_public_rate_includes_effective_date_and_source(self):
        path=Path(self.temp.name)/'rates.json'
        path.write_text(json.dumps({'published_rates':[{'product':'Sample savings','apy_percent':'1.25',
            'effective_date':'2026-01-01','expires_at':'2027-01-01','source_title':'Fictional published rate fixture',
            'source_url':'https://example.com/sample-rate','approval_status':'APPROVED_FOR_SYNTHETIC_TEST','version':'test-v1'}]}))
        with patch('resolveguard.public_support.RATES',path):
            first=self.ask('What is the current savings interest rate?').json()
            self.assertTrue(first['choose_product'])
            result=self.ask('Sample savings','rate-product').json()
        self.assertIn('1.25% APY',result['response']);self.assertIn('2026-01-01',result['response'])
        self.assertIn('Sample rate only',result['response']);self.assertFalse(result['auth_required'])
        self.assertEqual(result['source_details'][0]['url'],'https://example.com/sample-rate')

    def test_expired_session_retains_public_questions_and_requires_auth_for_records(self):
        self.client.post('/api/session',json={'profile':'expired'})
        self.assertFalse(self.ask('What is the monthly maintenance fee?').json()['auth_required'])
        self.assertTrue(self.ask('Show my recent transactions','private').json()['auth_required'])

    def test_pending_request_survives_application_restart(self):
        key=self.ask('Show my recent transactions').json()['pending_id']
        with TestClient(create_app(self.database)) as restarted:
            restarted.cookies.update(self.client.cookies)
            self.assertEqual(restarted.get('/api/session').json()['pending_id'],key)
            self.assertEqual(restarted.post('/api/auth/demo-sign-in',json={'pending_id':key}).status_code,200)
            self.assertTrue(restarted.post('/api/auth/resume',json={'pending_id':key}).json()['cards'])

    def test_expired_future_unapproved_or_conflicting_rates_are_not_shown(self):
        base={'product':'Sample savings','apy_percent':'1.25','effective_date':'2026-01-01',
              'source_title':'Fictional fixture','source_url':'https://example.com/sample-rate',
              'approval_status':'APPROVED_FOR_SYNTHETIC_TEST','version':'test-v1'}
        path=Path(self.temp.name)/'unavailable-rates.json'
        cases=([dict(base,expires_at='2026-01-02')],[dict(base,effective_date='2099-01-01')],
               [dict(base,approval_status='DRAFT')],[base,dict(base,version='test-v2')])
        for i,rates in enumerate(cases):
            path.write_text(json.dumps({'published_rates':rates}))
            with patch('resolveguard.public_support.RATES',path):
                result=self.ask('What is the current savings interest rate?',f'rate-{i}').json()
            self.assertNotIn('1.25%',result['response'])
            self.assertFalse(result['auth_required'])

    def test_cancelled_or_expired_pending_request_cannot_resume(self):
        key=self.ask('Show my recent transactions').json()['pending_id']
        with Store(self.database).connect() as db:
            db.execute("UPDATE web_auth_requests SET expires_at='2000-01-01T00:00:00+00:00' WHERE pending_id=?",(key,))
        self.assertEqual(self.sign_in(key).status_code,403)
        new=self.ask('Show my recent transactions','new').json()['pending_id']
        self.client.post('/api/auth/cancel',json={'pending_id':new})
        self.assertEqual(self.sign_in(new).status_code,403)
