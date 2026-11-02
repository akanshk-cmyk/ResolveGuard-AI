"""Deterministic active-theft interception. No model calls, financial guarantees or real bank APIs."""
import hashlib
import json
import re
import time
from uuid import uuid4
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .contracts import Request
from .presentation import customer_cards
from .telemetry import Trace, sanitize, utcnow

VERSION='emergency-debit-demo-v1'
DISCLOSURE=('No refund amount or date is guaranteed. Investigation and provisional-credit '
            'terms need confirmation from the support team; approved timelines are not available in this demo.')


def active_theft(message):
    text=message.lower().replace('\u2019',"'")
    if re.search(r'\b(what if|hypothetical|examples?|how would|credit card)\b',text):return False
    active=bool(re.search(r'\b(right now|just now|currently|happening|ongoing|still using|being used|using it now|is using|are using|as we speak|in progress)\b',text))
    unauthorized=bool(re.search(r'\b(unauthori[sz]ed|someone.*using|fraudulent)\b',text))
    theft=unauthorized or bool(re.search(r'\b(stolen|theft)\b',text) and not re.search(r'\b(not stolen|wasn.t stolen)\b',text))
    return active and theft


class CardState(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    status: Literal['OK','DENIED','UNKNOWN']
    state: Literal['LOCKED','NOT_CONFIRMED'] = 'NOT_CONFIRMED'
    operation_id: str | None = None
    account_id: str | None = None

    @model_validator(mode='after')
    def confirmed_state(self):
        if self.status=='OK' and (self.state!='LOCKED' or not self.operation_id or not self.account_id):
            raise ValueError('Missing lock evidence')
        if self.state=='LOCKED' and self.status!='OK':raise ValueError('Lock not confirmed')
        return self


class FraudTicket(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    status: Literal['OK','DENIED','UNKNOWN','NOT_ATTEMPTED']
    reference: str | None = None
    state: Literal['OPEN_FOR_REVIEW'] | None = None
    synthetic: bool = True

    @model_validator(mode='after')
    def committed_ticket(self):
        if self.status=='OK' and (not self.reference or not self.reference.startswith('DEMO-FRAUD-') or self.state!='OPEN_FOR_REVIEW' or not self.synthetic):
            raise ValueError('Missing synthetic dispute evidence')
        return self


def emergency_copy(data,report,handoff):
    lines=["I'm sorry this is happening. Let's focus on securing your card."]
    if data.get('request_conflict'):
        lines.append('This request reference was already used for different information. No new card action was taken. Send a new message for a different report, or contact urgent fraud support.')
    elif data['card_lock']['state']=='LOCKED':
        lines.append('Your demo debit card is locked. The synthetic backend confirmed its current locked state. No real bank card was changed.')
    elif data['card_lock']['status']=='UNKNOWN':
        lines.append('I cannot confirm that your card is locked. Please use your bank\'s secure card controls or contact its fraud support immediately.')
    elif data.get('selection_required'):
        lines.append('Select the affected account or one of its payments so I can identify the correct demo debit card. I have not locked a card.')
    elif data.get('requires_auth'):
        lines.append('I have not locked a card. Secure sign-in and permission for the affected card are required; your report does not need to wait.')
    else:
        lines.append('Your current access does not permit this card action. I have not confirmed a card lock; contact your bank\'s fraud support immediately.')
    if report.get('status')=='OK':lines.append('Your report is saved. Reference: '+report['event_id']+'.')
    else:lines.append('Report capture is not confirmed. Contact fraud support immediately; do not assume it was received.')
    if data['dispute'].get('status')=='OK':
        lines.append('A demo fraud intake ticket is open for review. Reference: '+data['dispute']['reference']+'. It is not a real bank dispute or a confirmed investigation. Pending payments are review candidates, not confirmed fraudulent payments.')
    elif data['card_lock'].get('account_id'):
        lines.append('Fraud ticket creation is not confirmed. Human review is required.')
    if data.get('pending_audit_status')=='PARTIAL':lines.append('I could not retrieve every pending payment. The support team needs to complete that review.')
    if handoff.get('handoff_status')=='ACKNOWLEDGED':lines.append('The demo fraud support queue received your request.')
    else:lines.append('Support delivery is not confirmed. Use your bank\'s approved urgent fraud contact route now.')
    return '\n\n'.join(lines+[DISCLOSURE,'Never share your PIN, CVV, password or one-time code in chat.'])


class EmergencyCards:
    """A new synthetic card-management adapter with explicit write permission.

    One invented debit card per ACTIVE checking account; no PANs are created.
    Representative read permissions deliberately do not authorize card locking.
    """
    def __init__(self,backend):
        self.backend=backend
        self.store=backend.store
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS emergency_cards(bank TEXT,account_id TEXT,state TEXT,updated_at TEXT,PRIMARY KEY(bank,account_id))')
            db.execute('CREATE TABLE IF NOT EXISTS emergency_locks(id TEXT PRIMARY KEY,bank TEXT,owner TEXT,account_id TEXT,result TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS emergency_disputes(id TEXT PRIMARY KEY,bank TEXT,owner TEXT,account_id TEXT,payload TEXT,result TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS emergency_requests(bank TEXT,owner TEXT,request_key TEXT,payload_hash TEXT,PRIMARY KEY(bank,owner,request_key))')
            for table in ('emergency_locks','emergency_disputes','emergency_requests'):
                for operation in ('UPDATE','DELETE'):
                    db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'Emergency history is append-only'); END")

    def reserve(self,req):
        digest=hashlib.sha256(json.dumps(req.model_dump(exclude={'session_id'}),sort_keys=True).encode()).hexdigest()
        owner=self.backend.owner(req) or 'UNAUTHENTICATED'
        with self.store.connect() as db:
            db.execute('INSERT OR IGNORE INTO emergency_requests VALUES(?,?,?,?)',(req.bank_id,owner,req.request_key,digest))
            row=db.execute('SELECT payload_hash FROM emergency_requests WHERE bank=? AND owner=? AND request_key=?',
                           (req.bank_id,owner,req.request_key)).fetchone()
        return row[0]==digest

    def allowed(self,req,account):
        b=self.backend
        session=b.bank._session(req.session_id)
        return bool(req.bank_id==b.bank_id and req.service_id=='resolveguard-agent'
            and not b.assurance_error(req) and session and session['actor_type']=='CUSTOMER'
            and account and account.get('status') in {'ACTIVE','OPEN'}
            and account['customer_id']==session['principal_id']
            and (account.get('product_id','').startswith('BOW-CHK-') if b.bank_id=='BOW'
                 else account.get('product') in {'CHECKING','DEBIT_CHECKING'})
            and b.allowed_account(req,account['account_id'],'CARD_LOCK'))

    def select(self,req):
        accounts=self.backend.bank.accounts
        requested=req.account_id
        if req.transaction_ids:
            selected=[]
            for ident in req.transaction_ids:
                tx=next((t for t in self.backend.bank.transactions if t['transaction_id']==ident),None)
                account=next((a for a in accounts if tx and a['account_id']==tx['account_id']),None)
                # Card inventory authority is independent of payment-read uptime.
                # No transaction fields are returned by this selection lookup.
                if not tx or not self.allowed(req,account):return None,False
                selected.append(tx['account_id'])
            if len(set(selected))!=1 or requested and requested!=selected[0]:return None,False
            requested=selected[0]
        if requested:
            account=next((a for a in accounts if a['account_id']==requested),None)
            return (account,False) if self.allowed(req,account) else (None,False)
        choices=[a for a in accounts if self.allowed(req,a)]
        return (choices[0],False) if len(choices)==1 else (None,len(choices)>1)

    def lock(self,req,account):
        if not self.allowed(req,account):return CardState(status='DENIED').model_dump()
        if not self.reserve(req):return CardState(status='DENIED').model_dump()
        if self.backend.faults.card_lock_timeout:return CardState(status='UNKNOWN',account_id=account['account_id']).model_dump()
        ident='DEMO-LOCK-'+hashlib.sha256(json.dumps([req.bank_id,self.backend.owner(req),req.request_key]).encode()).hexdigest()[:16]
        result=CardState(status='OK',state='LOCKED',operation_id=ident,account_id=account['account_id']).model_dump()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT account_id FROM emergency_locks WHERE id=?',(ident,)).fetchone()
            if old and old['account_id']!=account['account_id']:return CardState(status='DENIED').model_dump()
            db.execute('INSERT INTO emergency_cards VALUES(?,?,?,?) ON CONFLICT(bank,account_id) DO UPDATE SET state=excluded.state,updated_at=excluded.updated_at',
                       (req.bank_id,account['account_id'],'LOCKED',self.backend.now))
            db.execute('INSERT OR IGNORE INTO emergency_locks VALUES(?,?,?,?,?)',(ident,req.bank_id,self.backend.owner(req),account['account_id'],json.dumps(result)))
        return CardState(status='UNKNOWN',operation_id=ident,account_id=account['account_id']).model_dump() if self.backend.faults.card_lock_commit_then_timeout else result

    def state(self,req,account,operation_id):
        if not self.allowed(req,account):return CardState(status='DENIED').model_dump()
        if self.backend.faults.card_state_timeout:return CardState(status='UNKNOWN',account_id=account['account_id']).model_dump()
        with self.store.connect() as db:
            row=db.execute('SELECT l.result,c.state FROM emergency_locks l JOIN emergency_cards c ON c.bank=l.bank AND c.account_id=l.account_id WHERE l.id=? AND l.bank=? AND l.owner=? AND l.account_id=?',
                           (operation_id,req.bank_id,self.backend.owner(req),account['account_id'])).fetchone()
        return json.loads(row['result']) if row and row['state']=='LOCKED' else CardState(status='UNKNOWN',account_id=account['account_id']).model_dump()

    def dispute(self,req,account,pending,report,audit_status='COMPLETE'):
        if not self.allowed(req,account):return {'status':'DENIED'}
        if not self.reserve(req):return {'status':'DENIED'}
        for record in pending:
            actual=self.backend.transaction(req,record.get('transaction_id','missing'))
            fixture=next((t for t in self.backend.bank.transactions if t['transaction_id']==record.get('transaction_id')),None)
            if actual.get('status')!='OK' or not fixture or fixture['account_id']!=account['account_id'] or fixture['status']!='PENDING' or dict(actual['data'],kind='transaction')!=record:
                return {'status':'DENIED'}
        if self.backend.faults.fraud_dispute_timeout:return {'status':'UNKNOWN'}
        ident='DEMO-FRAUD-'+hashlib.sha256(json.dumps([req.bank_id,self.backend.owner(req),req.request_key]).encode()).hexdigest()[:16]
        payload={'report_ref':report.get('event_id'),'pending_candidates':pending,'observed_at':self.backend.now,
                 'pending_audit_status':audit_status,
                 'transaction_timestamp_precision':'SOURCE_DATE_ONLY','review_status':'UNVERIFIED_CANDIDATES'}
        result={'status':'OK','reference':ident,'state':'OPEN_FOR_REVIEW','synthetic':True}
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT account_id FROM emergency_disputes WHERE id=?',(ident,)).fetchone()
            if old and old['account_id']!=account['account_id']:return {'status':'DENIED'}
            db.execute('INSERT OR IGNORE INTO emergency_disputes VALUES(?,?,?,?,?,?)',(ident,req.bank_id,self.backend.owner(req),account['account_id'],json.dumps(payload),json.dumps(result)))
            stored=db.execute('SELECT payload,result FROM emergency_disputes WHERE id=?',(ident,)).fetchone()
        # Retries preserve the original snapshot; new pending data cannot rewrite it.
        return json.loads(stored['result'])


def triage(backend,req,trigger_at,blocked=False):
    started=time.perf_counter()
    start_time=utcnow()
    trace=Trace({'workflow':'HIGH_SEVERITY_FRAUD','version':VERSION,'bank_id':req.bank_id,'trigger_at':trigger_at})
    tools=[]
    with trace.span('fraud.trigger') as span:
        span['outputs']={'intent':'HIGH_SEVERITY_FRAUD','trigger_at':trigger_at,'version':VERSION}
    def call(name,fn,inputs=None):
        with trace.span(name,'tool',inputs or {}) as span:
            try:
                result=fn()
                if name in {'freeze_demo_debit_card','verify_demo_card_state'}:result=CardState.model_validate(result).model_dump()
                if name=='create_demo_fraud_dispute':result=FraudTicket.model_validate(result).model_dump(exclude_none=True)
            except Exception:
                result=CardState(status='UNKNOWN').model_dump() if name in {'freeze_demo_debit_card','verify_demo_card_state'} else {'status':'UNKNOWN'}
            span['outputs']=sanitize(result)
            tools.append({'name':name,'status':result.get('status')})
            return result
    cards=EmergencyCards(backend)
    with trace.span('emergency.reserve') as span:
        reserved=cards.reserve(req)
        span['outputs']={'status':'OK' if reserved else 'CONFLICT'}
    report=call('record_issue_intake',lambda:backend.capture(req),{
        'statement_sha256':hashlib.sha256(req.message.encode()).hexdigest(),
        'reported_transaction_ids':list(req.transaction_ids),'service_id':req.service_id}) if reserved else {'status':'CONFLICT'}
    if report.get('status')=='UNKNOWN':report=call('lookup_report',lambda:backend.lookup_report(req))
    third_party=bool(re.search(r"\b(?:(?:wife|husband|spouse|mother|father|friend|parent|child)'s|her|his|their)\s+(?:debit\s+)?card\b",req.message.replace('\u2019',"'"),re.I))
    account,selection=cards.select(req) if reserved and not blocked and not third_party and not backend.assurance_error(req) else (None,False)
    lock=CardState(status='DENIED').model_dump()
    pending=[]
    audit_status='NOT_ATTEMPTED'
    dispute={'status':'NOT_ATTEMPTED'}
    if account:
        audit_status='COMPLETE'
        lock=call('freeze_demo_debit_card',lambda:cards.lock(req,account),{'account_id':account['account_id'],'operation':'LOCK'})
        state=call('verify_demo_card_state',lambda:cards.state(req,account,lock.get('operation_id')),{'operation_id':lock.get('operation_id')})
        lock=state if state.get('status')=='OK' else CardState(status='UNKNOWN',account_id=account['account_id'],operation_id=lock.get('operation_id')).model_dump()
        for tx in backend.bank.transactions:
            if tx['account_id']==account['account_id'] and tx['status']=='PENDING':
                result=call('get_transaction',lambda ident=tx['transaction_id']:backend.transaction(req,ident),{'transaction_id':tx['transaction_id']})
                if result.get('status')=='OK':pending.append(dict(result['data'],kind='transaction'))
                else:audit_status='PARTIAL'
        dispute=call('create_demo_fraud_dispute',lambda:cards.dispute(req,account,pending,report,audit_status),{'account_id':account['account_id'],'report_ref':report.get('event_id'),'pending_count':len(pending),'audit_status':audit_status})
    handoff=call('handoff_to_human',lambda:backend.handoff(req,report,urgent=True)) if reserved else {'status':'DENIED','handoff_status':'BLOCKED'}
    emergency={'version':VERSION,'severity':'HIGH_SEVERITY_FRAUD','trigger_at':trigger_at,
               'card_lock':lock,'dispute':dispute,'selection_required':selection,
               'pending_audit_status':audit_status,
               'request_conflict':not reserved,
               'requires_auth':bool(not blocked and (backend.assurance_error(req) or req.bank_id!=backend.bank_id)),'synthetic':True}
    output={'response':emergency_copy(emergency,report,handoff),'response_state':'EMERGENCY_FRAUD',
            'triage_intent':'HIGH_SEVERITY_FRAUD',
            'route':{'primary_intent':'FRAUD_ERROR_REPORT','potential_fraud_error':True,
                     'human_requested':bool(re.search(r'\b(human|person|speak to|talk to|support agent|connect me|fraud support)\b',req.message,re.I)),
                     'urgent':True},
            'bank_id':req.bank_id,'data_scope':'RESTRICTED' if account else 'INTAKE','auth_required':False,
            'report':report,'handoff':handoff,'emergency':emergency,'cards':customer_cards({'records':pending,'bank_id':req.bank_id}),
            'source_details':[],'records':pending,'case':{},'execution_mode':'SYNTHETIC_EMERGENCY'}
    with trace.span('emergency.compose') as span:
        span['outputs']={'response':output['response'],'response_state':'EMERGENCY_FRAUD','card_state':lock['state'],
                         'dispute_status':dispute.get('status'),'version':VERSION}
    root_id=str(uuid4())
    for span in trace.spans:
        if span['parent_id'] is None:span['parent_id']=root_id
    trace.spans.insert(0,{'id':root_id,'parent_id':None,'name':'emergency.journey','run_type':'chain',
                         'inputs':{'intent':'HIGH_SEVERITY_FRAUD'},'outputs':{'response_state':'EMERGENCY_FRAUD'},
                         'start_time':start_time,'end_time':utcnow(),'error':None,
                         'latency_ms':round((time.perf_counter()-started)*1000,3)})
    return output,trace.export(),tools


def verify_emergency(candidate,backend,sid,request_key):
    """Recheck durable action evidence and exact emergency wording at delivery."""
    data=candidate.get('emergency',{})
    if data.get('version')!=VERSION or data.get('severity')!='HIGH_SEVERITY_FRAUD' or data.get('synthetic') is not True:return False
    try:
        lock=CardState.model_validate(data['card_lock']).model_dump()
        req=Request(message='Verify emergency outcome',request_key=request_key,session_id=sid,bank_id=candidate['bank_id'])
        account=next((a for a in backend.bank.accounts if a['account_id']==lock.get('account_id')),None)
        service=EmergencyCards(backend)
        if account and not service.allowed(req,account):return False
        if lock['state']=='LOCKED' and service.state(req,account,lock['operation_id'])!=lock:return False
        dispute=data['dispute']
        if dispute.get('status')=='OK':
            with backend.store.connect() as db:
                row=db.execute('SELECT * FROM emergency_disputes WHERE id=? AND bank=? AND owner=? AND account_id=?',
                    (dispute['reference'],req.bank_id,backend.owner(req),lock.get('account_id'))).fetchone()
            if not account or not row or json.loads(row['result'])!=dispute:return False
        expected=emergency_copy(data,candidate.get('report',{}),candidate.get('handoff',{}))
        if candidate.get('auth_required'):
            from .public_support import SIGN_IN_MESSAGE
            suffix='Please complete the additional secure verification to view your account details.' if candidate.get('auth_state')=='STEP_UP_REQUIRED' else SIGN_IN_MESSAGE
            expected+='\n\n'+suffix
        return candidate.get('response')==expected
    except (KeyError,TypeError,ValueError):return False
