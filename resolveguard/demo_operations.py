"""Authoritative local simulator for assignments and consented demo callbacks."""
import json
import re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from .customer_review import fingerprint
from .resolution_contracts import PriorityDecision,CallbackCommitment,EvidenceRef


class DemoOperations:
    def __init__(self,store):
        self.store=store
        self.rules=json.loads((Path(__file__).resolve().parents[1]/'data/demo_operations.json').read_text())
        if self.rules['approval']!='SYNTHETIC_TEST_ONLY':raise ValueError('Demo rule scope is invalid')
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS demo_assignments (handoff_ref TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS demo_callbacks (handoff_ref TEXT PRIMARY KEY,payload TEXT NOT NULL)')

    def receipt(self,backend,request,handoff_ref):
        with self.store.connect() as db:row=db.execute("SELECT owner,payload,result FROM events WHERE kind='handoff' AND event_id=?",(handoff_ref,)).fetchone()
        if not row or row['owner']!=backend.owner(request):raise PermissionError('Handoff is not available')
        result=json.loads(row['result']);payload=json.loads(row['payload'])
        if payload.get('bank_id','LEGACY_DEMO')!=request.bank_id or result.get('handoff_status')!='ACKNOWLEDGED' or result.get('queue') not in self.rules['queues']:
            raise PermissionError('No eligible acknowledged demo queue')
        return result

    def assign(self,backend,request,handoff_ref,message):
        receipt=self.receipt(backend,request,handoff_ref)
        tier='P1' if re.search(r'\b(stolen|right now|signing in|active fraud|urgent)\b',message,re.I) else 'P2' if receipt['queue'].startswith('FRAUD') else 'P3'
        version=self.rules['version'];event='priority-'+fingerprint([handoff_ref,version])
        value=PriorityDecision(assigned_tier=tier,queue_id=receipt['queue'],rule_id='DEMO-INTAKE-PRIORITY',rule_version=version,
            evidence=(EvidenceRef(kind='BACKEND_EVENT',reference=event,version=version,event_kind='PRIORITY_ASSIGNED',resource_ref=receipt['queue']),))
        with self.store.connect() as db:
            db.execute('INSERT OR IGNORE INTO demo_assignments VALUES(?,?)',(handoff_ref,value.model_dump_json()))
            return PriorityDecision.model_validate_json(db.execute('SELECT payload FROM demo_assignments WHERE handoff_ref=?',(handoff_ref,)).fetchone()[0])

    def callback(self,backend,request,handoff_ref,*,consented):
        if not consented or backend.assurance_error(request):raise PermissionError('Verified sign-in and explicit consent are required')
        receipt=self.receipt(backend,request,handoff_ref)
        if backend.faults.primary_queue_down and receipt['queue']!='FRAUD_BACKUP' or backend.faults.backup_queue_down and receipt['queue']=='FRAUD_BACKUP':
            raise PermissionError('The demo callback queue is unavailable')
        case_ref=(receipt.get('payload') or {}).get('case_id')
        if case_ref and backend.case_status(request.model_copy(update={'case_id':case_ref})).get('status')!='OK':
            raise PermissionError('Current case authority is required for the callback')
        now=datetime.fromisoformat(backend.now.replace('Z','+00:00'));version=self.rules['version']
        ident='demo-callback-'+fingerprint([handoff_ref,version])
        value=CallbackCommitment(status='CONFIRMED',queue_id=receipt['queue'],commitment_id=ident,
            window_start=(now+timedelta(minutes=self.rules['callback_start_minutes'])).isoformat(),
            window_end=(now+timedelta(minutes=self.rules['callback_end_minutes'])).isoformat(),confirmed_at=now.isoformat(),
            evidence=(EvidenceRef(kind='BACKEND_EVENT',reference=ident,version=version,event_kind='CALLBACK_CONFIRMED',resource_ref=ident),))
        with self.store.connect() as db:
            db.execute('INSERT OR IGNORE INTO demo_callbacks VALUES(?,?)',(handoff_ref,value.model_dump_json()))
        return self.commitment(handoff_ref)

    def commitment(self,handoff_ref):
        with self.store.connect() as db:row=db.execute('SELECT payload FROM demo_callbacks WHERE handoff_ref=?',(handoff_ref,)).fetchone()
        return CallbackCommitment.model_validate_json(row[0]) if row else CallbackCommitment(status='UNCONFIRMED')

    def assign_case(self,backend,request,case_ref):
        result=backend.case_status(request.model_copy(update={'case_id':case_ref}))
        if result.get('status')!='OK' or result['data']['owner_queue'] not in self.rules['queues']:raise PermissionError('No permitted case owner queue')
        queue=result['data']['owner_queue'];version=self.rules['version'];event='priority-'+fingerprint([case_ref,version])
        value=PriorityDecision(assigned_tier='P3',queue_id=queue,rule_id='DEMO-CASE-PRIORITY',rule_version=version,
            evidence=(EvidenceRef(kind='BACKEND_EVENT',reference=event,version=version,event_kind='PRIORITY_ASSIGNED',resource_ref=queue),))
        with self.store.connect() as db:
            db.execute('INSERT OR IGNORE INTO demo_assignments VALUES(?,?)',(case_ref,value.model_dump_json()))
            return PriorityDecision.model_validate_json(db.execute('SELECT payload FROM demo_assignments WHERE handoff_ref=?',(case_ref,)).fetchone()[0])
