import base64
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from resolveguard.backend import Backend
from resolveguard.customer_review import CustomerReview
from resolveguard.dashboard import create_dashboard
from resolveguard.storage import Store


class ReviewerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=Store(self.root/'web.sqlite3');self.review=CustomerReview(self.store)
        self.review.gate({'response':'Which product?'},binding='test-browser',sid='SESS-001',backend=Backend(self.store),bank_id='BOW',request_key='first',access_state='VERIFIED',message='My email is customer@example.test')
        self.token='local-test-admin-token-1234567890'
        self.client=TestClient(create_dashboard(self.root,self.token,review_database=self.store.path));self.client.__enter__()
        self.headers={'Authorization':'Bearer '+self.token}
        self.item=self.client.get('/api/reviewer/sessions',headers=self.headers).json()['items'][0]

    def tearDown(self):self.client.__exit__(None,None,None);self.temp.cleanup()

    def test_auth_scope_and_readonly_role(self):
        self.assertEqual(self.client.get('/api/reviewer/sessions').status_code,401)
        actor=self.client.post('/api/reviewer/staff',headers=self.headers,json={'user_id':'legacy-viewer','role':'VIEWER','banks':['LEGACY_DEMO']}).json()
        headers={'Authorization':'Bearer '+actor['token']}
        self.assertEqual(self.client.get('/api/reviewer/sessions',headers=headers).json()['items'],[])
        self.assertEqual(self.client.get('/api/reviewer/traces/'+self.item['review_id'],headers=headers).status_code,404)
        self.assertEqual(self.client.post('/api/reviewer/notes',headers=headers,json={'review_id':self.item['review_id'],'expected_revision':0,'status':'COMPLETE','note':'Check'}).status_code,403)
        self.client.post('/api/reviewer/staff/legacy-viewer/revoke',headers=self.headers)
        self.assertEqual(self.client.get('/api/reviewer/sessions',headers=headers).status_code,401)

    def test_playback_is_masked_and_records_no_banking_action(self):
        count=self.store.count('case')
        d=self.client.get('/api/reviewer/traces/'+self.item['review_id'],headers=self.headers).json()
        self.assertEqual(d['playback_mode'],'RECORDED_ONLY_NO_TOOL_EXECUTION')
        self.assertNotIn('customer@example.test',json.dumps(d))
        self.assertEqual(self.store.count('case'),count)

    def test_notes_append_only_and_concurrent_revision_is_rejected(self):
        payload={'review_id':self.item['review_id'],'expected_revision':0,'status':'COMPLETE','note':'Evidence checked'}
        self.assertEqual(self.client.post('/api/reviewer/notes',headers=self.headers,json=payload).status_code,200)
        self.assertEqual(self.client.post('/api/reviewer/notes',headers=self.headers,json=payload).status_code,409)
        payload.update(expected_revision=1,status='ESCALATED',note='Correction: additional evidence needed')
        self.assertEqual(self.client.post('/api/reviewer/notes',headers=self.headers,json=payload).status_code,200)
        with self.assertRaises(sqlite3.IntegrityError),self.store.connect() as db:db.execute('DELETE FROM review_notes')
        d=self.client.get('/api/reviewer/traces/'+self.item['review_id'],headers=self.headers).json()
        self.assertEqual(len(d['history']),2)

    def test_export_is_authenticated_encryption_with_separate_password(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        from cryptography.exceptions import InvalidTag
        password='separate-long-password-for-export'
        response=self.client.post('/api/reviewer/exports',headers=self.headers,json={'session_ref':self.item['session_ref'],'password':password,'format':'JSON'})
        self.assertEqual(response.status_code,200,response.text);p=response.json()
        self.assertNotIn(password,response.text)
        salt=base64.b64decode(p['salt']);nonce=base64.b64decode(p['nonce']);cipher=base64.b64decode(p['ciphertext'])
        key=Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(password.encode())
        data=json.loads(AESGCM(key).decrypt(nonce,cipher,b'resolveguard-export-v1'))
        self.assertEqual(data['session_ref'],self.item['session_ref'])
        with self.assertRaises(InvalidTag):AESGCM(key).decrypt(nonce,cipher[:-1]+bytes([cipher[-1]^1]),b'resolveguard-export-v1')

    def test_alert_rules_and_local_acknowledgement(self):
        r=self.client.post('/api/reviewer/alert-rules',headers=self.headers,json={'rule_id':'check-duration','metric':'latency_ms','threshold':0.0,'window':20})
        self.assertEqual(r.status_code,200)
        alert=self.client.get('/api/reviewer/alerts',headers=self.headers).json()['items'][0]
        self.assertEqual(self.client.post('/api/reviewer/alerts/'+alert['alert_id']+'/acknowledge',headers=self.headers).json()['status'],'ACKNOWLEDGED')
