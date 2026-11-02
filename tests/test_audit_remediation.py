import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from resolveguard.backend import Backend
from resolveguard.contracts import Request
from resolveguard.evaluation import execute_case, summarize
from resolveguard.full_evaluation import original_bindings
from resolveguard.reply_generation import ReplyGenerator, ReplySettings
from resolveguard.request_context import match_charges
from resolveguard.storage import Store
from resolveguard.web import create_app


class AuditRemediationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'web.sqlite3'
        self.client=TestClient(create_app(self.path,reply_generator=ReplyGenerator(ReplySettings(mode='off'))))
        self.client.__enter__()
        self.client.post('/api/session',json={'profile':'bow-customer-one'})

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.temp.cleanup()

    def ask(self,message,key,**extra):
        return self.client.post('/api/chat',json={'message':message,'request_key':key,'bank_id':'BOW',**extra}).json()

    def test_foreign_typed_account_cannot_reuse_own_selected_payment(self):
        tx=self.client.get('/api/transactions').json()['items'][0]['transaction_id']
        result=self.ask('Show the transaction on account BOW-ACC-003 while signed in as BOW-CUST-003',
                        'foreign',transaction_ids=[tx])
        self.assertEqual(result['response_state'],'ACCESS_DENIED')
        self.assertEqual(result['cards'],[])
        self.assertNotIn('Coffee Shop',result['response'])
        self.assertEqual(self.ask('Show transactions for BOW-ACC-005','foreign2')['response_state'],'ACCESS_DENIED')

    def test_typed_owned_account_and_case_do_not_use_old_dropdown(self):
        result=self.ask('Show transactions for BOW-ACC-001','own',transaction_ids=['BOW-TXN-002-01'])
        self.assertTrue(result['cards'])
        self.assertTrue(all(c['reference'].startswith('BOW-TXN-001-') for c in result['cards']))
        denied=self.ask('Show case BOW-CASE-004','case',transaction_ids=['BOW-TXN-001-01'])
        self.assertEqual(denied['response_state'],'ACCESS_DENIED')
        self.assertFalse(denied['cards'])

    def test_backend_rejects_account_transaction_conflict(self):
        from resolveguard.bow_backend import BowBackend
        backend=BowBackend(Store(self.path))
        req=Request(message='Read',request_key='backend',session_id='BOW-SESS-001',bank_id='BOW',account_id='BOW-ACC-003')
        self.assertEqual(backend.transaction(req,'BOW-TXN-001-01')['reason_code'],'REQUESTED_RESOURCE_MISMATCH')

    def test_transfer_is_explicitly_unavailable_before_signin(self):
        for profile in ('signed-out','bow-customer-one'):
            self.client.post('/api/session',json={'profile':profile})
            result=self.ask('transfer the fund to my account','transfer-'+profile)
            self.assertEqual(result['response_state'],'PROHIBITED_ACTION')
            self.assertIn("can't transfer money",result['response'])
            self.assertFalse(result['auth_required'])

    def test_denied_case_still_honors_human_request_without_private_context(self):
        result=self.ask("What's the status of my case BOW-CASE-004? Connect me to a person.",'case-human')
        self.assertEqual(result['response_state'],'ACCESS_DENIED')
        self.assertEqual(result['handoff']['handoff_status'],'ACKNOWLEDGED')
        self.assertNotIn('case_id',result['handoff']['payload'])
        self.assertFalse(result['cards'])

    def test_topic_switch_requires_product_and_resumes_original_question(self):
        self.ask('What rewards does YOLO Miles Card have?','yolo')
        result=self.ask('What are the reward restrictions?','unspecified')
        self.assertTrue(result['choose_product'])
        self.assertNotIn('2 points',result['response'])
        selected=self.ask('Whatever Debit Plus','choose',product_id='BOW-CARD-002')
        self.assertIn('$8',selected['response'])
        self.assertEqual(selected['answered_question'],'What are the reward restrictions?')
        self.assertTrue(self.ask('What is the current APY?','apy')['choose_product'])

    def test_calendar_charge_matching_handles_signed_amounts_and_year_boundary(self):
        rows=[{'amount_cents':-1800,'posted_on':'2025-12-15','merchant':'SERVICE FEE'},
              {'amount_cents':1800,'posted_on':'2026-01-02','merchant':'SERVICE FEE'},
              {'amount_cents':-1801,'posted_on':'2025-12-15','merchant':'SERVICE FEE'}]
        self.assertEqual(match_charges(rows,'Why did you charge my account 18 dollars last month?','2026-01-05'),rows[:1])
        self.assertEqual(match_charges(rows,'Why was I charged $18 last month?','2026-01-05'),rows[:1])
        result=self.ask('Why did you charge my account 999 dollars last month?','no-match',transaction_ids=['BOW-TXN-001-01'])
        self.assertIn('could not find',result['response'])
        self.assertFalse(result['cards'])

    def test_guest_report_saved_before_minimal_followup_and_no_private_reads(self):
        self.client.post('/api/session',json={'profile':'signed-out'})
        result=self.ask('I do not recognize a debit card charge of $26. Please help me report it.','report')
        self.assertEqual(result['report']['status'],'OK')
        self.assertIn('merchant name and approximate date',result['response'])
        self.assertFalse(result['auth_required'])
        self.assertFalse(result['cards'])
        with Store(self.path).connect() as db:
            details=json.loads(db.execute('SELECT payload FROM review_details ORDER BY rowid DESC LIMIT 1').fetchone()[0])
        self.assertFalse(any(t['name']=='get_transaction' for t in details['workflow']['tools']))

    def test_all_direct_branches_have_actual_correlated_traces(self):
        for i,message in enumerate(['Hello','transfer the fund to my account','Show transactions for BOW-ACC-005',
                                    'What is the current APY?','What is the status of case BOW-CASE-001?']):
            self.ask(message,'trace-'+str(i))
            with Store(self.path).connect() as db:
                detail=json.loads(db.execute('SELECT payload FROM review_details ORDER BY rowid DESC LIMIT 1').fetchone()[0])
            trace=detail['workflow']['trace']
            self.assertTrue(trace['trace_id'])
            ids={s['id'] for s in trace['spans']}
            self.assertTrue(all(s['parent_id'] is None or s['parent_id'] in ids for s in trace['spans']))

    def test_emergency_contract_checks_evidence_not_only_response_state(self):
        data=original_bindings()
        case=next(c for c in data['cases'] if c['case_id']=='RG-087')
        self.assertTrue(case['expected']['emergency_required'])
        row=execute_case(case,Path(self.temp.name)/'eval',engine='langgraph')
        self.assertTrue(row['passed'],row['failure_categories'])
        report=summarize([row],{'cases':[case],'dataset_version':'test'},'langgraph')
        self.assertEqual(report['run_type'],'MOCK_SMOKE_NOT_LIVE_MODEL_BASELINE')
        self.assertFalse(report['provider_calls_observed'])
        self.assertTrue(row['checks']['emergency_evidence_verified'])


if __name__=='__main__':
    unittest.main()
