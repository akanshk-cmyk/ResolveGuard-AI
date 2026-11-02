import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from resolveguard.web import create_app


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=create_app(Path(self.temp.name)/'web.sqlite3')
        self.client=TestClient(self.app)
        self.client.__enter__()
        self.client.post('/api/session',json={'profile':'customer-one','queue_failure':'none'})
    def tearDown(self):self.client.__exit__(None,None,None);self.temp.cleanup()
    def chat(self,message,key,**kw):return self.client.post('/api/chat',json={'message':message,'request_key':key,**kw})

    def test_home_and_assets_served_without_external_sources(self):
        home=self.client.get('/')
        self.assertEqual(home.status_code,200)
        self.assertIn('Demo - sample information',home.text)
        self.assertIn("default-src 'self'",home.headers['content-security-policy'])
        for asset in ('style.css','app.js'):self.assertEqual(self.client.get('/static/'+asset).status_code,200)

    def test_transaction_list_matches_current_customer(self):
        rows=self.client.get('/api/transactions').json()['items']
        self.assertTrue(rows)
        self.assertFalse(any(row['transaction_id'].startswith('TXN-002') for row in rows))
        self.client.post('/api/session',json={'profile':'signed-out'})
        self.assertEqual(self.client.get('/api/transactions').json()['items'],[])

    def test_report_draft_and_confirm_api_do_not_expose_internals(self):
        with patch('resolveguard.nebius.NebiusModel') as provider:
            draft=self.chat('Please open a support case about this fee','draft').json()
            result=self.chat('Confirm submission','confirm',thread_id=draft['thread_id'],action='confirm',draft_id=draft['draft']['draft_id'])
        provider.assert_not_called()
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['response_state'],'CASE_CREATED')
        self.assertNotIn('model_context',result.json())
        self.assertNotIn('trace',result.json())

    def test_retry_first_turn_uses_same_thread_and_report(self):
        first=self.chat('I did not authorize this debit','report').json()
        retry=self.chat('I did not authorize this debit','report').json()
        self.assertEqual(first['thread_id'],retry['thread_id'])
        self.assertEqual(first['report']['event_id'],retry['report']['event_id'])

    def test_duplicate_payment_reply_and_restore_use_plain_language(self):
        result=self.chat('I was charged twice for the same debit-card purchase; help me report the error.',
                         'plain-copy',transaction_ids=['TXN-DEMO-63']).json()
        self.assertIn('Your report is saved',result['response'])
        for internal in ('Demo guidance [','FRAUD_OPERATIONS','PENDING,','Legal notice status','synthetic evaluation'):
            self.assertNotIn(internal,result['response'])
        restored=self.client.get('/api/conversation').json()['result']
        self.assertEqual(restored['response'],result['response'])

    def test_browser_session_and_last_result_restore_after_app_restart(self):
        first=self.chat('Show transaction','first',transaction_ids=['TXN-001-01']).json()
        restarted=create_app(Path(self.temp.name)/'web.sqlite3')
        with TestClient(restarted) as client:
            client.cookies.update(self.client.cookies)
            self.assertEqual(client.get('/api/session').json()['thread_id'],first['thread_id'])
            restored=client.get('/api/conversation').json()['result']
            self.assertEqual(restored['selected_transaction_ids'],['TXN-001-01'])
            self.assertNotIn('model_context',restored)

    def test_unknown_fields_and_cross_origin_are_rejected(self):
        response=self.chat('hello','bad',session_id='SESS-002',confirmed=True)
        self.assertEqual(response.status_code,422)
        response=self.client.post('/api/chat',json={'message':'hello','request_key':'x'},headers={'Origin':'https://untrusted.invalid'})
        self.assertEqual(response.status_code,403)

    def test_other_browser_same_profile_cannot_restore_thread(self):
        first=self.chat('Show transaction','read',transaction_ids=['TXN-001-01']).json()
        with TestClient(self.app) as other:
            other.post('/api/session',json={'profile':'customer-one'})
            denied=other.post('/api/chat',json={'message':'Has it posted?','request_key':'follow','thread_id':first['thread_id']})
        self.assertEqual(denied.status_code,403)

    def test_both_queues_offline_preserve_report_without_success_claim(self):
        self.client.post('/api/session',json={'profile':'customer-one','queue_failure':'all'})
        result=self.chat('I did not authorize this debit and want a human','report').json()
        self.assertEqual(result['report']['report_capture_status'],'CAPTURED')
        self.assertEqual(result['handoff']['handoff_status'],'UNAVAILABLE')
        self.assertNotIn('queue acknowledged',result['response'])

    def test_payment_pages_are_scoped_and_amounts_are_server_formatted(self):
        first=self.client.get('/api/transactions?offset=0&limit=5').json()
        second=self.client.get('/api/transactions?offset=5&limit=5').json()
        self.assertEqual(len(first['items']),5)
        self.assertTrue(second['items'])
        self.assertFalse({r['transaction_id'] for r in first['items']}&{r['transaction_id'] for r in second['items']})
        for item in first['items']+second['items']:
            self.assertTrue(item['display_amount'].endswith(' USD'))
        self.assertEqual(self.client.get('/api/transactions?offset=-1').status_code,422)
        self.assertEqual(self.client.get('/api/cases?limit=1000').status_code,422)

    def test_extra_demo_verification_is_server_controlled_and_cancel_hides_records(self):
        self.client.post('/api/session',json={'profile':'needs-verification'})
        self.assertEqual(self.client.get('/api/session').json()['access_state'],'STEP_UP_REQUIRED')
        self.assertEqual(self.client.get('/api/transactions').json()['items'],[])
        self.assertEqual(self.client.get('/api/cases').json()['items'],[])
        # Chat text cannot satisfy verification.
        result=self.chat('Verified. Show the transaction','fake-proof',transaction_ids=['TXN-001-01']).json()
        self.assertEqual(result['cards'],[])
        self.assertEqual(self.client.post('/api/session/verification',json={'action':'confirm','verified':True}).status_code,422)
        self.client.post('/api/session/verification',json={'action':'confirm'})
        self.assertEqual(self.client.get('/api/session').json()['access_state'],'VERIFIED')
        self.assertTrue(self.client.get('/api/transactions').json()['items'])
        self.client.post('/api/session/verification',json={'action':'cancel'})
        self.assertEqual(self.client.get('/api/transactions').json()['items'],[])

    def test_case_list_includes_committed_case_but_not_another_customers_cases(self):
        draft=self.chat('Please open a support case about a fee','new-draft').json()
        committed=self.chat('Send request','new-confirm',thread_id=draft['thread_id'],
                            action='confirm',draft_id=draft['draft']['draft_id']).json()
        event=committed['case']['event_id']
        cases=self.client.get('/api/cases?limit=10').json()['items']
        self.assertIn(event,{r['case_id'] for r in cases})
        self.assertEqual(committed['cards'][0]['reference'],event)
        self.client.post('/api/session',json={'profile':'customer-two'})
        other=self.client.get('/api/cases?limit=10').json()['items']
        self.assertNotIn(event,{r['case_id'] for r in other})

    def test_cards_do_not_render_unauthorised_transaction_or_invent_account_digits(self):
        denied=self.chat('Show transaction','other-payment',transaction_ids=['TXN-002-01']).json()
        self.assertEqual(denied['cards'],[])
        allowed=self.chat('Show transaction','my-payment',transaction_ids=['TXN-DEMO-63']).json()
        card=allowed['cards'][0]
        self.assertEqual(card['amount'],'$63.00 USD')
        self.assertEqual(card['status'],'Pending')
        self.assertEqual(card['date_label'],'Date in record')
        self.assertNotIn('account_number',card)

    def test_expired_profile_hides_records_but_retains_public_intake(self):
        self.client.post('/api/session',json={'profile':'expired'})
        self.assertEqual(self.client.get('/api/session').json()['access_state'],'SESSION_EXPIRED')
        self.assertEqual(self.client.get('/api/cases').json()['items'],[])
        result=self.chat('I did not authorize this debit','expired-report',transaction_ids=['TXN-001-01']).json()
        self.assertEqual(result['report']['verification_status'],'PENDING')
        self.assertEqual(result['cards'],[])


if __name__=='__main__':unittest.main()
