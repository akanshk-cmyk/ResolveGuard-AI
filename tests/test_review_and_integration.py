import copy
import csv
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from resolveguard.backend import Backend
from resolveguard.contracts import Request
from resolveguard.langsmith_integration import client_from_environment, upload_dataset, publish_trace
from resolveguard.storage import Store
from resolveguard.workflow import Workflow
from tools.apply_review import apply_review
from tools.prepare_dataset import read_sheet, WORKBOOK

ROOT=Path(__file__).resolve().parents[1]


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.dataset=json.loads((ROOT/'data/evaluation_40.json').read_text(encoding='utf-8'))
        with (ROOT/'data/review_40.csv').open(encoding='utf-8-sig',newline='') as handle:
            self.rows=list(csv.DictReader(handle))

    def test_prompts_are_exact_source_workbook_text(self):
        originals={r['A']:r['B'] for r in read_sheet(WORKBOOK,'1_Golden Dataset')[1:]}
        for case in self.dataset['cases']:
            self.assertEqual(case['inputs']['message'],originals[case['case_id']])

    def test_pending_review_is_not_auto_approved(self):
        result=apply_review(self.dataset,self.rows)
        self.assertNotEqual(result['provenance_status'],'ATTESTED')
        self.assertTrue(all(c['metadata']['human_review_status']=='PENDING' for c in result['cases']))

    def test_approval_requires_reviewer_and_notes(self):
        self.rows[0]['human_review_status']='APPROVED'
        with self.assertRaisesRegex(ValueError,'reviewer'):
            apply_review(self.dataset,self.rows)

    def test_review_cannot_change_input_silently(self):
        self.rows[0]['prompt']='An easier prompt'
        with self.assertRaisesRegex(ValueError,'source prompt'):
            apply_review(self.dataset,self.rows)

    def test_eight_generated_cases_do_not_meet_below_20_percent(self):
        for i,row in enumerate(self.rows):
            row.update({'human_review_status':'APPROVED','reviewer':'Test reviewer',
                        'review_notes':'Fixture and oracle inspected for this unit test',
                        'prompt_origin':'llm_generated' if i<8 else 'human_authored',
                        'provenance_notes':'Test-only provenance evidence'})
        result=apply_review(self.dataset,self.rows)
        self.assertNotEqual(result['provenance_status'],'ATTESTED')
        self.rows[7]['prompt_origin']='human_authored'
        result=apply_review(self.dataset,self.rows)
        self.assertEqual(result['provenance_status'],'ATTESTED')
        # Source dataset is never mutated by import.
        self.assertTrue(all(c['metadata']['human_review_status']=='PENDING' for c in self.dataset['cases']))


class IntegrationPreparationTests(unittest.TestCase):
    def test_installed_langsmith_sdk_builds_real_run_tree_without_upload(self):
        import importlib.util
        if not importlib.util.find_spec('langsmith'):
            self.skipTest('Optional LangSmith dependency is not installed')
        import socket
        from langsmith import Client
        with tempfile.TemporaryDirectory() as temp:
            trace=Workflow(Backend(Store(Path(temp)/'x.sqlite3'))).run(
                Request(message='I did not authorize this debit',request_key='sdk-check'))['trace']
        client=Client(api_url='https://langsmith.invalid',api_key='not-a-real-key',
                      auto_batch_tracing=False,info={'version':'local-test'},omit_traced_runtime_info=True)
        with patch.object(Client,'create_run') as create,patch.object(Client,'update_run') as update, \
             patch.object(socket.socket,'connect',side_effect=AssertionError('No cloud upload authorized')):
            root=publish_trace(trace,client=client)
        self.assertEqual(create.call_count,len(trace['spans']))
        self.assertEqual(update.call_count,len(trace['spans']))
        self.assertTrue(root.child_runs)

    def test_langgraph_cannot_auto_upload_when_ambient_tracing_enabled(self):
        import importlib.util
        if not importlib.util.find_spec('langgraph'):
            self.skipTest('Optional LangGraph dependency is not installed')
        import socket
        with tempfile.TemporaryDirectory() as temp, \
             patch.dict(os.environ,{'LANGSMITH_TRACING':'true','LANGCHAIN_TRACING_V2':'true',
                                    'LANGSMITH_API_KEY':'not-a-real-key'}), \
             patch.object(socket.socket,'connect',side_effect=AssertionError('No outbound connections')) as connect:
            result=Workflow(Backend(Store(Path(temp)/'x.sqlite3')),engine='langgraph').run(
                Request(message='Show selected transaction',request_key='no-export',transaction_ids=('TXN-001-01',)))
        self.assertEqual(result['engine'],'langgraph')
        self.assertEqual(connect.call_count,0)

    def test_missing_credentials_do_not_initialize_network_client(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(RuntimeError,'LANGSMITH_API_KEY'):
                client_from_environment()

    def test_dataset_export_keeps_ids_but_omits_private_bindings(self):
        dataset=json.loads((ROOT/'data/evaluation_40.json').read_text(encoding='utf-8'))
        class Client:
            def create_dataset(self,**kw):
                self.name=kw['dataset_name'];return SimpleNamespace(id='test-dataset')
            def create_examples(self,**kw):self.examples=kw
        client=Client()
        upload_dataset(dataset,client)
        self.assertEqual(len(client.examples['inputs']),40)
        self.assertEqual(set(client.examples['inputs'][0]),{'case_id','message'})
        self.assertNotIn('session_id',json.dumps(client.examples['inputs']))
        self.assertIn('draft',client.name)

    def test_prepared_trace_export_keeps_child_tree_and_valid_dates(self):
        made=[]
        class FakeRun:
            def __init__(self,**kw):
                self.kw=kw;self.children=[];self.posted=False;made.append(self)
            def create_child(self,**kw):
                child=FakeRun(**kw);self.children.append(child);return child
            def post(self):self.posted=True
            def end(self,**kw):self.ended=kw
            def patch(self):self.patched=True
        fake_module=types.ModuleType('langsmith.run_trees');fake_module.RunTree=FakeRun
        with tempfile.TemporaryDirectory() as temp:
            output=Workflow(Backend(Store(Path(temp)/'x.sqlite3'))).run(
                Request(message='My OTP is 123456',request_key='test'))
        with patch.dict(sys.modules,{'langsmith.run_trees':fake_module}):
            root=publish_trace(output['trace'],client=object())
        self.assertEqual(len(made),len(output['trace']['spans']))
        self.assertTrue(root.children)
        self.assertTrue(all(r.posted and r.patched for r in made))
        self.assertNotIn('123456',str([r.kw for r in made]))


if __name__=='__main__':unittest.main()
