import tempfile
import unittest
from pathlib import Path
from resolveguard.backend import Backend
from resolveguard.contracts import Request
from resolveguard.model import ScriptedMockModel
from resolveguard.storage import Store
from resolveguard.workflow import Workflow


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'state.sqlite3'
        self.backend=Backend(Store(self.path))

    def tearDown(self):self.temp.cleanup()

    def test_created_case_can_be_read_after_restart_but_not_by_other_customer(self):
        made=self.backend.create_case(Request(message='Open fee case',request_key='create',account_id='ACC-001',confirmed=True))
        restarted=Backend(Store(self.path))
        req=Request(message='Show case',request_key='lookup',case_id=made['event_id'])
        self.assertEqual(restarted.case_status(req)['data']['status'],'OPEN')
        other=req.model_copy(update={'session_id':'SESS-002'})
        self.assertEqual(restarted.case_status(other)['status'],'DENIED')

    def test_missing_stepup_blocks_reads_writes_reconciliation_and_case_handoff(self):
        self.backend.assurance_events=[]
        req=Request(message='Show case',request_key='x',session_id='SESS-STEPUP',case_id='CASE-001',account_id='ACC-001',confirmed=True)
        self.assertEqual(self.backend.transaction(req,'TXN-001-01')['reason_code'],'STEP_UP_REQUIRED')
        self.assertEqual(self.backend.case_status(req)['reason_code'],'STEP_UP_REQUIRED')
        self.assertEqual(self.backend.create_case(req)['status'],'DENIED')
        self.assertEqual(self.backend.lookup_request(req)['status'],'DENIED')
        self.assertEqual(self.backend.handoff(req,{},urgent=True)['handoff_status'],'BLOCKED')
        self.assertEqual(self.backend.capture(req)['report_capture_status'],'CAPTURED')

    def test_unsupported_action_does_not_hide_report_or_handoff(self):
        route={'primary_intent':'UNSUPPORTED_REQUEST','potential_fraud_error':True,'human_requested':True,'urgent':False}
        output=Workflow(self.backend,ScriptedMockModel(route=route)).run(Request(
            message='I did not authorize this debit; refund it and get a human',request_key='combined'))
        self.assertIn('cannot transfer funds',output['response'])
        self.assertIn(output['report']['event_id'],output['response'])
        self.assertIn('queue acknowledged',output['response'])

    def test_handoff_reconciliation_rechecks_stored_case_without_caller_case_id(self):
        req=Request(message='Human please',request_key='handoff',session_id='SESS-REP',case_id='CASE-002')
        self.assertEqual(self.backend.handoff(req,{})['handoff_status'],'ACKNOWLEDGED')
        self.backend.bank.delegations[0]['revoked']=True
        result=self.backend.lookup_handoff(req.model_copy(update={'case_id':None}))
        self.assertEqual(result['handoff_status'],'BLOCKED')
        self.assertEqual(result['payload'],{})


if __name__=='__main__':unittest.main()
