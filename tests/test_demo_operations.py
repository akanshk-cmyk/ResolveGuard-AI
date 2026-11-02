import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from resolveguard.backend import Backend
from resolveguard.contracts import Request
from resolveguard.demo_operations import DemoOperations
from resolveguard.storage import Store
from resolveguard.web import create_app


class DemoOperationsTests(unittest.TestCase):
    def test_authoritative_assignment_and_callback_are_idempotent_and_scoped(self):
        with tempfile.TemporaryDirectory() as temp:
            backend=Backend(Store(Path(temp)/'test.sqlite3'));ops=DemoOperations(backend.store)
            req=Request(message='My card was stolen right now',session_id='SESS-001',request_key='report')
            report=backend.capture(req);handoff=backend.handoff(req,report,urgent=True)
            assigned=ops.assign(backend,req,handoff['event_id'],req.message)
            self.assertEqual(assigned.assigned_tier,'P1')
            self.assertEqual(ops.assign(backend,req,handoff['event_id'],'No urgency'),assigned)
            with self.assertRaises(PermissionError):ops.callback(backend,req,handoff['event_id'],consented=False)
            with self.assertRaises(PermissionError):ops.callback(backend,req.model_copy(update={'session_id':'SESS-002'}),handoff['event_id'],consented=True)
            first=ops.callback(backend,req,handoff['event_id'],consented=True)
            self.assertEqual(first.status,'CONFIRMED')
            self.assertEqual(ops.callback(backend,req,handoff['event_id'],consented=True),first)
            backend.faults.primary_queue_down=True
            with self.assertRaises(PermissionError):ops.callback(backend,req,handoff['event_id'],consented=True)

    def test_guest_cannot_confirm_callback_but_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp,TestClient(create_app(Path(temp)/'web.sqlite3')) as client:
            client.post('/api/session',json={})
            result=client.post('/api/chat',json={'message':'My card was stolen','request_key':'guest-report'}).json()
            self.assertEqual(result['report']['status'],'OK')
            response=client.post('/api/demo/callback',json={'handoff_ref':result['handoff']['event_id'],'request_key':'cb','consent':True})
            self.assertEqual(response.status_code,403)

    def test_verified_customer_can_request_clearly_labelled_demo_callback(self):
        with tempfile.TemporaryDirectory() as temp,TestClient(create_app(Path(temp)/'web.sqlite3')) as client:
            client.post('/api/session',json={'profile':'customer-one'})
            result=client.post('/api/chat',json={'message':'My card was stolen','request_key':'report'}).json()
            response=client.post('/api/demo/callback',json={'handoff_ref':result['handoff']['event_id'],'request_key':'cb','consent':True})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['callback']['status'],'CONFIRMED')
            self.assertIn('No real telephone call',response.json()['response'])

    def test_callback_rechecks_representative_authority_after_revocation(self):
        with tempfile.TemporaryDirectory() as temp:
            backend=Backend(Store(Path(temp)/'test.sqlite3'));ops=DemoOperations(backend.store)
            req=Request(message='Connect me to support about the case',session_id='SESS-POA',request_key='delegated',case_id='CASE-002')
            handoff=backend.handoff(req,{},urgent=False)
            self.assertEqual(handoff['handoff_status'],'ACKNOWLEDGED')
            self.assertEqual(ops.callback(backend,req,handoff['event_id'],consented=True).status,'CONFIRMED')
            for delegation in backend.bank.delegations:delegation['revoked']=True
            with self.assertRaises(PermissionError):ops.callback(backend,req,handoff['event_id'],consented=True)
