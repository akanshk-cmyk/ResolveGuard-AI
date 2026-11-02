import tempfile
import unittest
from pydantic import ValidationError
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from resolveguard.backend import Backend
from resolveguard.storage import Store
from resolveguard.conversation import ConversationService,Turn


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'state.sqlite3'
        self.backend=Backend(Store(self.path));self.service=ConversationService(self.backend)
    def tearDown(self):self.temp.cleanup()
    def send(self,message,key,**kw):
        return self.service.send('SESS-001','thread-1',Turn(message=message,request_key=key,**kw))

    def test_followup_uses_checkpoint_after_restart(self):
        self.send('Show selected transaction','first',transaction_ids=['TXN-001-01'])
        restarted=ConversationService(Backend(Store(self.path)))
        follow=restarted.send('SESS-001','thread-1',Turn(message='Has it posted?',request_key='follow'))
        self.assertIn('TXN-001-01',follow['response'])
        self.assertEqual(follow['records'][0]['status'],'POSTED')

    def test_wrong_customer_or_browser_cannot_restore_thread(self):
        self.send('Show transaction','first',transaction_ids=['TXN-001-01'])
        turn=Turn(message='Has it posted?',request_key='follow')
        with self.assertRaises(PermissionError):self.service.send('SESS-002','thread-1',turn)
        with self.assertRaises(PermissionError):self.service.send('SESS-001','thread-1',turn,client_binding='another-browser')

    def test_case_draft_confirm_after_restart_and_read_new_case(self):
        draft=self.send('Please open a case about this fee','draft',account_id='ACC-001')['draft']['draft_id']
        self.assertEqual(self.backend.store.count('case'),0)
        restarted=ConversationService(Backend(Store(self.path)))
        result=restarted.send('SESS-001','thread-1',Turn(message='Confirm submission',request_key='confirm',action='confirm',draft_id=draft))
        self.assertEqual(result['response_state'],'CASE_CREATED')
        follow=restarted.send('SESS-001','thread-1',Turn(message='What is its status?',request_key='status'))
        self.assertEqual(follow['records'][0]['case_id'],result['case']['event_id'])
        self.assertEqual(self.backend.store.count('case'),1)

    def test_repeated_and_concurrent_confirmations_create_one_case(self):
        draft=self.send('Please open a case about this fee','draft')['draft']['draft_id']
        def confirm(index):
            service=ConversationService(Backend(Store(self.path)))
            return service.send('SESS-001','thread-1',Turn(message='Confirm submission',request_key=f'confirm-{index}',action='confirm',draft_id=draft))
        with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(confirm,range(6)))
        self.assertEqual(len({r['case']['event_id'] for r in results}),1)
        self.assertEqual(self.backend.store.count('case'),1)

    def test_cancelled_or_expired_draft_cannot_create_case(self):
        draft=self.send('Please open a case','draft')['draft']['draft_id']
        self.send('Cancel','cancel',action='cancel',draft_id=draft)
        output=self.send('Confirm','confirm',action='confirm',draft_id=draft)
        self.assertEqual(output['response_state'],'ACTION_UNAVAILABLE')
        self.assertEqual(self.backend.store.count('case'),0)
        draft=self.send('Please open a case again','draft-2')['draft']['draft_id']
        self.backend.now='2026-10-30T14:00:00Z'
        output=self.send('Confirm','expired',action='confirm',draft_id=draft)
        self.assertEqual(output['response_state'],'ACTION_UNAVAILABLE')

    def test_draft_cannot_be_used_in_other_thread(self):
        draft=self.send('Please open a case','draft')['draft']['draft_id']
        output=self.service.send('SESS-001','other-thread',Turn(message='Confirm',request_key='other',action='confirm',draft_id=draft))
        self.assertEqual(output['response_state'],'ACTION_UNAVAILABLE')
        self.assertEqual(self.backend.store.count('case'),0)

    def test_revoked_session_blocks_confirmation_and_cached_details(self):
        first=self.send('Show transaction','read',transaction_ids=['TXN-001-01'])
        draft=self.send('Please open a case','draft')['draft']['draft_id']
        self.backend.bank.sessions[0]['revoked']=True
        repeated=self.send('Show transaction','read',transaction_ids=['TXN-001-01'])
        self.assertNotIn('records',repeated)
        result=self.send('Confirm','confirm',action='confirm',draft_id=draft)
        self.assertEqual(result['response_state'],'ACTION_UNAVAILABLE')
        self.assertEqual(self.backend.store.count('case'),0)

    def test_turn_idempotency_rejects_changed_message(self):
        self.send('I did not authorize this debit','report')
        self.send('I did not authorize this debit','report')
        self.assertEqual(self.backend.store.count('report'),1)
        with self.assertRaises(ValueError):self.send('A different report','report')

    def test_invalid_thread_and_draft_overrides_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.send('SESS-001',' ',Turn(message='hello',request_key='x'))
        with self.assertRaises(ValidationError):
            Turn(message='Confirm',request_key='x',action='confirm',draft_id='DRAFT-x',account_id='ACC-002')

    def test_interrupted_graph_resumes_without_duplicate_report(self):
        original=self.service._perform
        def crash(*args):
            original(*args)
            raise RuntimeError('Simulated crash after side effect')
        with patch.object(self.service,'_perform',side_effect=crash),self.assertRaises(RuntimeError):
            self.send('I did not authorize this debit','report')
        restarted=ConversationService(Backend(Store(self.path)))
        result=restarted.send('SESS-001','thread-1',Turn(message='I did not authorize this debit',request_key='report'))
        self.assertEqual(result['report']['report_capture_status'],'CAPTURED')
        self.assertEqual(self.backend.store.count('report'),1)


if __name__=='__main__':unittest.main()
