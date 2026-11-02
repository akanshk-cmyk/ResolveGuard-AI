import json
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from resolveguard.backend import Backend
from resolveguard.contracts import Request
from resolveguard.intake_signals import asserted_payment_error
from resolveguard.model import ScriptedMockModel, TunedMockModel
from resolveguard.storage import Store
from resolveguard.web import create_app
from resolveguard.workflow import Workflow


class ErrorSignalTests(unittest.TestCase):
    def test_asserted_error_phrasing_has_intake_priority(self):
        for message in ('selected charge is incorrectly applied','This payment was applied by mistake',
                        'My debit amount is not correct','I was charged incorrectly','This charge is wrong',
                        "My payment isn't correct"):
            self.assertTrue(asserted_payment_error(message),message)
            route=TunedMockModel(4).classify(message)
            self.assertEqual(route['primary_intent'],'FRAUD_ERROR_REPORT',message)

    def test_general_questions_and_explicit_negation_do_not_assert_error(self):
        for message in ('What does an incorrectly applied charge mean?', 'How do I report an incorrect charge?',
                        'The charge is not incorrect','This payment is not wrong','Show the selected charge'):
            self.assertFalse(asserted_payment_error(message),message)

    def test_server_safety_rule_preserves_report_when_model_misroutes_or_fails(self):
        message='selected charge is incorrectly applied'
        for engine in ('offline','langgraph'):
            for error in (False,True):
                model=ScriptedMockModel(route={'primary_intent':'TRANSACTION_INQUIRY',
                    'potential_fraud_error':False,'human_requested':False,'urgent':False},error=error)
                with tempfile.TemporaryDirectory() as temp:
                    backend=Backend(Store(Path(temp)/'case.sqlite3'))
                    request=Request(message=message,session_id='SESS-ANON',request_key='error-report')
                    result=Workflow(backend,model,engine=engine).run(request)
                    self.assertEqual(result['route']['primary_intent'],'FRAUD_ERROR_REPORT')
                    self.assertEqual(result['report']['report_capture_status'],'CAPTURED')
                    original=backend.store.original('report',backend.owner(request),request.request_key)
                    self.assertEqual(original['original_statement'],message)


class ErrorIntakeConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'web.sqlite3'
        self.client=TestClient(create_app(self.path));self.client.__enter__()
        self.client.post('/api/session',json={})
    def tearDown(self):self.client.__exit__(None,None,None);self.temp.cleanup()
    def ask(self,message,key,**extra):
        response=self.client.post('/api/chat',json={'message':message,'request_key':key,'bank_id':'BOW',**extra})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def test_guest_error_intake_is_saved_before_auth_and_retry_is_not_duplicate(self):
        message='selected charge is incorrectly applied'
        first=self.ask(message,'guest-error',transaction_ids=['BOW-TXN-002-01'])
        # Intake is saved first; selecting a private record may then request sign-in.
        self.assertTrue(first['auth_required']);self.assertEqual(first['cards'],[])
        self.assertEqual(first['report']['report_capture_status'],'CAPTURED')
        replay=self.ask(message,'guest-error',transaction_ids=['BOW-TXN-002-01'])
        self.assertEqual(first['report']['event_id'],replay['report']['event_id'])
        self.assertEqual(first['handoff']['event_id'],replay['handoff']['event_id'])
        with Store(self.path).connect() as db:
            rows=db.execute("SELECT payload FROM events WHERE kind='report'").fetchall()
        self.assertEqual(len(rows),1)
        self.assertEqual(json.loads(rows[0]['payload'])['original_statement'],message)

    def test_signed_in_inquiry_then_error_then_new_comment_are_distinct_turns(self):
        self.client.post('/api/auth/demo-sign-in',json={'profile':'bow-customer-one'})
        tx=self.client.get('/api/transactions?bank_id=BOW').json()['items'][0]['transaction_id']
        inquiry=self.ask('Show selected transaction','inquiry',transaction_ids=[tx])
        report=self.ask('selected charge is incorrectly applied','error',thread_id=inquiry['thread_id'],transaction_ids=[tx])
        self.assertEqual(report['report']['report_capture_status'],'CAPTURED')
        next_turn=self.ask('I was charged incorrectly','next-comment',thread_id=report['thread_id'],transaction_ids=[tx])
        self.assertEqual(next_turn['report']['report_capture_status'],'CAPTURED')
        with Store(self.path).connect() as db:
            statements=[json.loads(r['payload'])['original_statement'] for r in db.execute("SELECT payload FROM events WHERE kind='report'")]
        self.assertEqual(set(statements),{'selected charge is incorrectly applied','I was charged incorrectly'})


if __name__=='__main__':unittest.main()
