"""Boundary tests: coercion, missing evidence, unsafe payloads and stored corruption."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError
from resolveguard.__main__ import main
from resolveguard.backend import Backend
from resolveguard.contracts import Request, Route, Faults, validate_result, RESULT_ADAPTERS
from resolveguard.model import ScriptedMockModel
from resolveguard.storage import Store
from resolveguard.workflow import Workflow


class InputValidationTests(unittest.TestCase):
    def request(self, **kw):
        return {'message':'Show transaction','request_key':'request-1',**kw}

    def test_rejects_string_or_numeric_confirmation(self):
        for value in ('false','true',0,1,None):
            with self.subTest(value=value),self.assertRaises(ValidationError):
                Request.model_validate(self.request(confirmed=value))

    def test_required_text_and_key_are_strict_and_nonblank(self):
        for fields in ({'message':''},{'message':' \n '},{'message':123},
                       {'request_key':''},{'request_key':' '},{'request_key':12}):
            with self.subTest(fields=fields),self.assertRaises(ValidationError):
                Request.model_validate(self.request(**fields))
        with self.assertRaises(ValidationError):Request.model_validate({'message':'hello'})

    def test_identifier_fields_and_lengths_are_validated(self):
        for fields in ({'session_id':None},{'case_id':1},{'account_id':''},
                       {'service_id':False},{'request_key':'x'*201},{'message':'x'*20001}):
            with self.subTest(fields=fields),self.assertRaises(ValidationError):
                Request.model_validate(self.request(**fields))

    def test_request_forbids_injected_roles_tools_and_faults(self):
        for fields in ({'role':'admin'},{'allowed_accounts':['ACC-002']},
                       {'tool':'issue_refund'},{'faults':{'receiver_denied':False}}):
            with self.subTest(fields=fields),self.assertRaises(ValidationError):
                Request.model_validate(self.request(**fields))

    def test_transaction_array_is_explicit_and_items_are_strict(self):
        req=Request.from_dict(self.request(transaction_ids=['TXN-001-01']))
        self.assertEqual(req.transaction_ids,('TXN-001-01',))
        for value in ('TXN-001-01',{'x':'TXN-001-01'},[123],['TXN-001-01']*2,
                      [f'TXN-{i}' for i in range(21)]):
            with self.subTest(value=value),self.assertRaises(ValidationError):
                Request.from_dict(self.request(transaction_ids=value))

    def test_request_preserves_original_whitespace_and_is_immutable(self):
        message='  I did not authorize this debit.\n'
        request=Request(message=message,request_key='x')
        self.assertEqual(request.message,message)
        with self.assertRaises(ValidationError):request.confirmed=True

    def test_route_requires_every_safety_flag(self):
        good={'primary_intent':'TRANSACTION_INQUIRY','potential_fraud_error':False,
              'human_requested':False,'urgent':False}
        for key in good:
            value=dict(good);value.pop(key)
            with self.subTest(key=key),self.assertRaises(ValidationError):Route.model_validate(value)
        for field in ('potential_fraud_error','human_requested','urgent'):
            for val in ('false',0,1,None):
                with self.subTest(field=field,val=val),self.assertRaises(ValidationError):
                    Route.model_validate({**good,field:val})

    def test_route_rejects_unknown_intents_extra_actions_and_inconsistent_fraud(self):
        good={'primary_intent':'TRANSACTION_INQUIRY','potential_fraud_error':False,
              'human_requested':False,'urgent':False}
        for changes in ({'primary_intent':'REFUND_APPROVED'},{'tool':'issue_refund'},
                        {'primary_intent':'FRAUD_ERROR_REPORT'}):
            with self.subTest(changes=changes),self.assertRaises(ValidationError):
                Route.model_validate({**good,**changes})

    def test_fault_controls_reject_unknown_fields_and_bad_assignment(self):
        for value in ({'transaction_timeout':'false'},{'reciever_denied':False},
                      {'receiver_fields':['customer_id']}):
            with self.subTest(value=value),self.assertRaises(ValidationError):Faults.model_validate(value)
        faults=Faults()
        with self.assertRaises(ValidationError):faults.receiver_denied='false'
        self.assertFalse(faults.receiver_denied)


class ResultValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'x.sqlite3'
        self.backend=Backend(Store(self.path))
        self.request=Request(message='I did not authorize this debit',request_key='x',
                             transaction_ids=('TXN-001-01',))

    def tearDown(self):self.temp.cleanup()

    def transaction(self):return self.backend.transaction(self.request,'TXN-001-01')

    def test_money_is_integer_cents_not_float_string_or_bool(self):
        for value in (45.99,4599.0,'4599',True,False):
            result=self.transaction();result['data']['amount_cents']=value
            with self.subTest(value=value),self.assertRaises(ValidationError):validate_result('transaction',result)

    def test_invalid_dates_and_unsupported_states_are_rejected(self):
        for field,value in [('posted_on','2026-02-30'),('posted_on','yesterday'),
                            ('status','APPROVED_BY_CHAT'),('currency','BTC')]:
            result=self.transaction();result['data'][field]=value
            with self.subTest(field=field),self.assertRaises(ValidationError):validate_result('transaction',result)

    def test_unknown_fields_and_success_without_record_are_rejected(self):
        result=self.transaction();result['data']['customer_id']='CUST-002'
        with self.assertRaises(ValidationError):validate_result('transaction',result)
        with self.assertRaises(ValidationError):validate_result('transaction',{'status':'OK','data':None})

    def test_denied_or_unknown_reads_cannot_carry_data(self):
        data=self.transaction()['data']
        for status in ('DENIED','UNKNOWN'):
            with self.subTest(status=status),self.assertRaises(ValidationError):
                validate_result('transaction',{'status':status,'data':data})

    def test_report_success_requires_event_time_and_separate_states(self):
        good=self.backend.capture(self.request)
        for key in ('event_id','reported_at','report_capture_status','regulatory_notice_status',
                    'verification_status','investigation_status','customer_confirmation_status'):
            bad=dict(good);bad.pop(key)
            with self.subTest(key=key),self.assertRaises(ValidationError):validate_result('report',bad)
        with self.assertRaises(ValidationError):
            validate_result('report',{**good,'regulatory_notice_status':'RECEIVED'})
        with self.assertRaises(ValidationError):
            validate_result('report',{**good,'reported_at':'2026-10-30T13:00:00'})

    def test_unknown_case_cannot_include_commit_fields(self):
        with self.assertRaises(ValidationError):
            validate_result('case_write',{'status':'UNKNOWN','event_id':'DEMO-CASE-'+'a'*16})
        with self.assertRaises(ValidationError):
            validate_result('case_write',{'status':'OK','event_id':'DEMO-CASE-'+'a'*16})

    def test_handoff_success_requires_ack_and_minimal_payload(self):
        report=self.backend.capture(self.request)
        good=self.backend.handoff(self.request,report,urgent=True)
        for key in ('handoff_status','event_id','queue','payload'):
            bad=dict(good);bad.pop(key)
            with self.subTest(key=key),self.assertRaises(ValidationError):validate_result('handoff',bad)
        bad=copy.deepcopy(good);bad['payload']['original_statement']='private narrative'
        with self.assertRaises(ValidationError):validate_result('handoff',bad)
        with self.assertRaises(ValidationError):
            validate_result('handoff',{**good,'status':'UNKNOWN','handoff_status':'ACKNOWLEDGED'})

    def test_failed_handoffs_cannot_expose_payload(self):
        for status,handoff in [('DENIED','BLOCKED'),('UNKNOWN','DELIVERY_UNKNOWN')]:
            with self.subTest(status=status),self.assertRaises(ValidationError):
                validate_result('handoff',{'status':status,'handoff_status':handoff,'payload':{'case_id':'CASE-001'}})

    def test_store_rejects_malformed_success_before_commit(self):
        payload={'original_statement':'Original report','reported_transaction_ids':[]}
        with self.assertRaises(ValidationError):
            self.backend.store.commit('report','CUST-001','bad',payload,{'status':'OK'})
        self.assertEqual(self.backend.store.count('report'),0)

    def test_unknown_outcome_cannot_be_stored_as_commit_evidence(self):
        payload={'original_statement':'Original report','reported_transaction_ids':[]}
        with self.assertRaises(ValidationError):
            self.backend.store.commit('report','CUST-001','bad',payload,{'status':'UNKNOWN'})
        self.assertEqual(self.backend.store.count('report'),0)

    def test_corrupt_persisted_result_is_revalidated(self):
        self.backend.capture(self.request)
        with self.backend.store.connect() as db:
            db.execute('UPDATE events SET result=? WHERE kind=?',
                       (json.dumps({'status':'OK','event_id':'fake'}),'report'))
        with self.assertRaises(ValidationError):self.backend.lookup_report(self.request)

    def test_model_construct_cannot_bypass_request_boundary(self):
        unsafe=Request.model_construct(message='hello',request_key='x',confirmed='false')
        with self.assertRaises(ValidationError):Workflow(self.backend).run(unsafe)
        self.assertEqual(self.backend.store.count('case'),0)

    def test_invalid_request_rejected_before_tracing_or_writes(self):
        with patch('resolveguard.workflow.Trace') as trace,self.assertRaises(ValidationError):
            Workflow(self.backend).run({'message':'hello','request_key':'x','confirmed':'false'})
        trace.assert_not_called()

    def test_corrupt_tool_output_fails_closed_in_both_engines(self):
        for engine in ('offline','langgraph'):
            with self.subTest(engine=engine),patch.object(self.backend.bank,'get_transaction',return_value={
                    'status':'OK','reason_code':'ALLOW','data':{'customer_id':'CUST-SECRET','amount_cents':'wrong'}}):
                req=Request(message='Show transaction',request_key='x',transaction_ids=('TXN-001-01',))
                output=Workflow(self.backend,engine=engine).run(req)
                self.assertEqual(output['response_state'],'UNVERIFIED')
                self.assertEqual(output['records'],[])
                self.assertIn('TOOL_SCHEMA_INVALID:get_transaction',output['errors'])
                self.assertNotIn('CUST-SECRET',json.dumps(output))

    def test_missing_model_flag_uses_safe_capture_fallback(self):
        route={'primary_intent':'FRAUD_ERROR_REPORT','potential_fraud_error':True,'human_requested':False}
        output=Workflow(self.backend,ScriptedMockModel(route=route)).run(self.request)
        self.assertEqual(output['report']['report_capture_status'],'CAPTURED')
        self.assertIn('ROUTING_INVALID_OR_UNAVAILABLE',output['errors'])

    def test_cli_validation_error_does_not_echo_rejected_secret(self):
        err=io.StringIO()
        with redirect_stderr(err):
            status=main(['ask','hello','--request-key','password=top-secret'])
        self.assertEqual(status,2)
        self.assertNotIn('top-secret',err.getvalue())
        self.assertIn('VALIDATION_FAILED',err.getvalue())

    def test_policy_contract_rejects_missing_ids_and_false_success(self):
        with self.assertRaises(ValidationError):validate_result('policy',{'status':'OK','chunks':[]})
        with self.assertRaises(ValidationError):
            validate_result('policy',{'status':'OK','chunks':[{'text':'Instructions without provenance'}]})


if __name__=='__main__':unittest.main()
