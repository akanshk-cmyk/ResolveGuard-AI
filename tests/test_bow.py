import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from pydantic import ValidationError
from resolveguard.web import create_app
from resolveguard.bow_data import load_dataset,validate_dataset,Chunk
from resolveguard.bow_knowledge import BowKnowledge
from resolveguard.bow_backend import BowBackend
from resolveguard.backend import Backend
from resolveguard.contracts import Request
from resolveguard.storage import Store


class BowDataTests(unittest.TestCase):
    def test_exact_counts_hashes_and_archival_separation(self):
        data,manifest=load_dataset()
        self.assertEqual({k:len(v) for k,v in data.items()},dict(products=11,policies=19,chunks=61,customers=12,accounts=12,
            transactions=48,sessions=12,cases=12,delegations=2,intake_events=1,evaluations=100))
        self.assertTrue(all(r['execution_status']=='NOT_RUN' for r in data['evaluations']))
        self.assertTrue(all(r['account_id'].startswith('BOW-') for r in data['accounts']))
        self.assertIn('UTC',manifest['timestamp_assumption'])

    def test_tampered_chunk_and_parent_scope_are_rejected(self):
        data,_=load_dataset();chunk=copy.deepcopy(data['chunks'][0]);chunk['chunk_text']='changed'
        with self.assertRaises(ValidationError):Chunk.model_validate(chunk)
        data['chunks'][0]['product_id']='BOW-CHK-002'
        with self.assertRaises(ValueError):validate_dataset(data)

    def test_retrieval_enforces_bank_variant_date_access_and_test_approval(self):
        kb=BowKnowledge()
        rows=kb.retrieve('BOW','BOW-CHK-001','2026-10-30',allow_demo=True)
        self.assertTrue(rows)
        self.assertFalse(any(r['product_id']=='BOW-CHK-002' for r in rows))
        for bank,product,day,access,allow in [('CHASE','BOW-CHK-001','2026-10-30','PUBLIC',True),
            ('BOW','BOW-CHK-001','2027-01-01','PUBLIC',True),('BOW','BOW-CHK-001','2026-09-01','PUBLIC',True),
            ('BOW','BOW-CHK-001','2026-10-30','INTERNAL',True),('BOW','BOW-CHK-001','2026-10-30','PUBLIC',False)]:
            self.assertEqual(kb.retrieve(bank,product,day,access_level=access,allow_demo=allow),[])

    def test_product_specific_fees_and_full_rate_tiers(self):
        kb=BowKnowledge()
        for ident,fee in [('BOW-CHK-001','$6.00'),('BOW-CHK-002','$12.00'),('BOW-CHK-003','$25.00')]:
            result=kb.answer('What is the monthly maintenance fee?',ident,'2026-10-30')
            self.assertIn(fee,result['response']);self.assertTrue(result['source_details'])
            self.assertTrue(all(s['product_id']==ident for s in result['source_details']))
        result=kb.answer('What is the savings interest rate?','BOW-SAV-002','2026-10-30')
        self.assertIn('3.20%',result['response']);self.assertIn('3.50%',result['response']);self.assertIn('$10,000',result['response'])
        self.assertEqual(result['source_details'][0]['effective_date'],'2026-10-01')

    def test_graph_adapter_preserves_savings_category_and_source_bank(self):
        from resolveguard.bow_knowledge import BowPolicyIndex
        from resolveguard.contracts import validate_result
        result=validate_result('policy',BowPolicyIndex('BOW-SAV-001').retrieve('savings APY',as_of='2026-10-30'))
        self.assertTrue(any(c['product']=='SAVINGS' for c in result['chunks']))
        self.assertTrue(all(c['bank_id']=='BOW' for c in result['chunks']))

    def test_ambiguous_rate_product_mismatch_and_cross_bank_fail_closed(self):
        kb=BowKnowledge()
        self.assertTrue(kb.answer('What is the savings rate?',None,'2026-10-30')['choose_product'])
        explicit=kb.answer('Tell me about Whatever Plus Checking','BOW-CHK-001','2026-10-30')
        self.assertEqual(explicit['selected_product_id'],'BOW-CHK-002')
        self.assertTrue(all(s['product_id']=='BOW-CHK-002' for s in explicit['source_details']))
        result=kb.answer('Use Chase fees instead','BOW-CHK-001','2026-10-30')
        self.assertEqual(result['source_details'],[])
        self.assertNotIn('$6',result['response'])


class BowWebTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'web.sqlite3'
        self.client=TestClient(create_app(self.path));self.client.__enter__();self.client.post('/api/session',json={})
    def tearDown(self):self.client.__exit__(None,None,None);self.temp.cleanup()
    def chat(self,message,key='bow-question',**extra):
        return self.client.post('/api/chat',json={'message':message,'request_key':key,'bank_id':'BOW',**extra})
    def login(self,profile='bow-customer-one',pending_id=None):
        return self.client.post('/api/auth/demo-sign-in',json={'profile':profile,'pending_id':pending_id})

    def test_public_bow_catalog_and_apy_work_for_guest(self):
        catalog=self.client.get('/api/bow/catalog').json()
        self.assertEqual(len(catalog['products']),11);self.assertTrue(catalog['workbook_imported'])
        result=self.chat('What is the current savings interest rate for Starter Savings?',product_id='BOW-SAV-001').json()
        self.assertFalse(result['auth_required']);self.assertIn('2.00%',result['response'])
        self.assertEqual(result['bank_id'],'BOW');self.assertIn('Demo terms',result['response'])

    def test_bow_login_resume_uses_only_bow_owned_transactions(self):
        key=self.chat('Show my recent transactions').json()['pending_id']
        self.assertEqual(self.login(pending_id=key).status_code,200)
        result=self.client.post('/api/auth/resume',json={'pending_id':key}).json()
        self.assertTrue(result['cards']);self.assertTrue(all(c['reference'].startswith('BOW-TXN-001') for c in result['cards']))
        self.assertTrue(any(c.get('account_display') for c in result['cards']))

    def test_legacy_login_is_not_bow_identity_and_cannot_resume_bow_request(self):
        self.client.post('/api/session',json={'profile':'customer-one'})
        self.assertEqual(self.client.get('/api/transactions?bank_id=BOW').json()['items'],[])
        key=self.chat('Show my recent transactions').json()['pending_id']
        self.assertEqual(self.login('customer-one',key).status_code,409)

    def test_cross_customer_and_cross_bank_transactions_remain_denied(self):
        self.login()
        for i,ident in enumerate(['BOW-TXN-002-01','TXN-001-01']):
            result=self.chat('Show transaction',f'denied-{i}',transaction_ids=[ident]).json()
            self.assertEqual(result['cards'],[])
            self.assertEqual(result['response_state'],'ACCESS_DENIED')

    def test_bow_fee_guidance_uses_account_product_not_public_selection(self):
        self.login()
        rows=self.client.get('/api/transactions?bank_id=BOW').json()['items']
        fee=next(r for r in rows if 'fee' in r['merchant'].lower())
        result=self.chat('Explain the fee charged to my account',transaction_ids=[fee['transaction_id']],product_id='BOW-CHK-003').json()
        self.assertTrue(result['source_details'])
        self.assertFalse(any(s['product_id']=='BOW-CHK-003' for s in result['source_details']))
        self.assertIn('Everyday',result['response'])

    def test_bow_case_status_and_committed_case_ownership(self):
        self.login()
        cases=self.client.get('/api/cases?bank_id=BOW').json()['items']
        self.assertEqual(cases[0]['case_id'],'BOW-CASE-001')
        draft=self.chat('Please open a support case','draft').json()
        result=self.chat('Send request','confirm',thread_id=draft['thread_id'],action='confirm',draft_id=draft['draft']['draft_id']).json()
        self.assertEqual(result['case']['status'],'OK')
        self.assertIn(result['case']['event_id'],{r['case_id'] for r in self.client.get('/api/cases?bank_id=BOW').json()['items']})

    def test_bow_guest_intake_preserved_with_bank_scope(self):
        result=self.chat('I did not authorize this debit').json()
        self.assertEqual(result['report']['status'],'OK');self.assertFalse(result['auth_required'])
        with Store(self.path).connect() as db:
            import json
            payload=json.loads(db.execute("SELECT payload FROM events WHERE kind='report'").fetchone()['payload'])
        self.assertEqual(payload['bank_id'],'BOW')

    def test_bow_step_up_revocation_and_unauthenticated_fixtures(self):
        self.login('bow-needs-verification')
        self.assertEqual(self.client.get('/api/session').json()['access_state'],'STEP_UP_REQUIRED')
        self.assertEqual(self.client.get('/api/transactions?bank_id=BOW').json()['items'],[])
        self.client.post('/api/session/verification',json={'action':'confirm'})
        self.assertTrue(self.client.get('/api/transactions?bank_id=BOW').json()['items'])
        for profile in ['bow-revoked','bow-unauthenticated']:
            self.client.post('/api/session',json={'profile':profile})
            self.assertEqual(self.client.get('/api/transactions?bank_id=BOW').json()['items'],[])

    def test_backend_itself_rejects_wrong_bank_context(self):
        backend=BowBackend(Store(self.path));req=Request(message='read',request_key='read',session_id='BOW-SESS-001')
        self.assertEqual(backend.transaction(req,'BOW-TXN-001-01')['status'],'DENIED')
        legacy=Backend(Store(self.path));foreign=req.model_copy(update={'bank_id':'BOW','session_id':'SESS-001'})
        self.assertEqual(legacy.transaction(foreign,'TXN-001-01')['status'],'DENIED')
