"""Customer-bound, replay-safe conversations with real SQLite graph checkpoints."""
import hashlib
import json
import threading
from contextlib import nullcontext
from datetime import datetime,timedelta
from typing import TypedDict, Literal
from pydantic import Field, model_validator, TypeAdapter
from .contracts import StrictModel, Identifier, Text, TransactionIds, Request, Route
from .backend import Backend
from .model import MockModel
from .telemetry import sanitize
from .workflow import Workflow


class Turn(StrictModel):
    message: Text
    request_key: Identifier
    action: Literal['message','confirm','cancel']='message'
    draft_id: Identifier | None=None
    transaction_ids: TransactionIds=()
    case_id: Identifier | None=None
    account_id: Identifier | None=None
    product: Literal['CHECKING','DEBIT_CHECKING']='DEBIT_CHECKING'

    @model_validator(mode='after')
    def action_requires_draft(self):
        if self.action!='message' and not self.draft_id:
            raise ValueError('Confirmation or cancellation requires a draft reference')
        if self.action!='message' and (self.transaction_ids or self.case_id or self.account_id):
            raise ValueError('Draft actions cannot override the saved resource selection')
        return self


class ConversationState(TypedDict):
    turn_ref: str
    context: dict
    result: dict


class ConfirmationModel:
    """A trusted confirm button selects the case workflow, not a model guess."""
    def __init__(self,base):self.base=base;self.name=base.name;self.is_mock=base.is_mock
    def classify(self,message):
        return Route(primary_intent='SUPPORT_CASE_REQUEST',potential_fraud_error=False,human_requested=False,urgent=False).model_dump()
    def explain(self,context,approved_response):return self.base.explain(context,approved_response)
    @property
    def usage(self):return getattr(self.base,'usage',[])


class ContextModel:
    def __init__(self,base,context):
        self.base=base;self.context=context;self.name=base.name;self.is_mock=base.is_mock
        self.prompt_version=getattr(base,'prompt_version','mock-rules-v0')
    def classify(self,message):
        text=message.lower().strip()
        if text in ('has it posted?','has it posted yet?','show that transaction','what about that transaction?') and self.context.get('transaction_ids'):
            message='Show transaction details. '+message
        if text in ('what is its status?','show that case','what about my case?') and self.context.get('case_id'):
            message='Show case status. '+message
        return self.base.classify(message)
    def explain(self,context,approved_response):return self.base.explain(context,approved_response)
    @property
    def usage(self):return getattr(self.base,'usage',[])


class ConversationService:
    # One process / worker is the supported demo deployment. Database transactions
    # protect writes; these locks serialize graph checkpoints within that worker.
    _locks={}
    _guard=threading.Lock()

    def __init__(self,backend:Backend,model=None):
        self.backend=backend;self.store=backend.store;self.model=model or MockModel()

    def send(self,session_id,thread_id,turn,client_binding='local-cli'):
        from langgraph.checkpoint.sqlite import SqliteSaver
        from langgraph.graph import StateGraph,START,END
        from langsmith import tracing_context
        turn=Turn.model_validate(turn)
        thread_id=TypeAdapter(Identifier).validate_python(thread_id,strict=True)
        client_binding=TypeAdapter(Identifier).validate_python(client_binding,strict=True)
        identity=Request(message=turn.message,request_key=turn.request_key,session_id=session_id)
        owner=self.backend.owner(identity)
        if not owner:raise PermissionError('Unknown synthetic session')
        self.store.bind_thread(thread_id,owner,session_id+':'+client_binding)
        lock_key=(self.store.path,thread_id)
        with self._guard:lock=self._locks.setdefault(lock_key,threading.RLock())
        with lock,tracing_context(enabled=False):
            cached=self.store.begin_turn(thread_id,turn.request_key,turn.model_dump(mode='json'))
            if cached is not None:
                # Never return cached account details after revocation or risk change.
                if self.backend.assurance_error(identity):
                    report=cached.get('report',{})
                    response=f"Your report remains captured as {report['event_id']}. " if report.get('status')=='OK' else ''
                    return {'response_state':'AUTH_REQUIRED','response':response+'Use secure verification to continue.','execution_mode':'MOCK','thread_id':thread_id}
                for record in cached.get('records',[]):
                    if record.get('transaction_id'):
                        permitted=self.backend.transaction(identity,record['transaction_id'])['status']=='OK'
                    else:
                        permitted=self.backend.case_status(identity.model_copy(update={'case_id':record['case_id']}))['status']=='OK'
                    if not permitted:
                        return {'response_state':'ACCESS_DENIED','response':'Current permission does not allow these details.','execution_mode':'MOCK','thread_id':thread_id}
                draft=cached.get('draft',{})
                if draft and not self.backend.allowed_account(identity,draft['account_id'],'CASE_STATUS'):
                    return {'response_state':'ACCESS_DENIED','response':'Current permission does not allow this draft.','execution_mode':'MOCK','thread_id':thread_id}
                committed=cached.get('case',{})
                if committed.get('status')=='OK' and self.backend.case_status(identity.model_copy(update={'case_id':committed['event_id']}))['status']!='OK':
                    return {'response_state':'ACCESS_DENIED','response':'Current permission does not allow this case.','execution_mode':'MOCK','thread_id':thread_id}
                handed_case=cached.get('handoff',{}).get('payload',{}).get('case_id')
                if handed_case and self.backend.case_status(identity.model_copy(update={'case_id':handed_case}))['status']!='OK':
                    return {'response_state':'ACCESS_DENIED','response':'Current permission does not allow this handoff context.','execution_mode':'MOCK','thread_id':thread_id}
                return cached
            def perform(state):
                current=Turn.model_validate(self.store.turn_input(thread_id,state['turn_ref']))
                context=dict(state.get('context',{}))
                try:
                    result,context=self._perform(identity,thread_id,current,context)
                except (ValueError,PermissionError) as exc:
                    result={'response_state':'ACTION_UNAVAILABLE','response':'This action could not be completed. Check your session and draft reference; create a new draft if it expired.',
                            'errors':[type(exc).__name__],'execution_mode':'MOCK'}
                return {'result':sanitize(result),'context':context}
            graph=StateGraph(ConversationState);graph.add_node('perform_turn',perform)
            graph.add_edge(START,'perform_turn');graph.add_edge('perform_turn',END)
            with SqliteSaver.from_conn_string(self.store.path+'.checkpoints') as saver:
                app=graph.compile(checkpointer=saver)
                config={'configurable':{'thread_id':thread_id}}
                snapshot=app.get_state(config)
                if snapshot.next:
                    if snapshot.values.get('turn_ref')!=turn.request_key:
                        raise ValueError('Resume the unfinished request before starting a new one')
                    output=app.invoke(None,config)
                else:
                    output=app.invoke({'turn_ref':turn.request_key},config)
            result={**output['result'],'thread_id':thread_id}
            self.store.finish_turn(thread_id,turn.request_key,result)
            return result

    def _perform(self,identity,thread_id,turn,context):
        owner=self.backend.owner(identity)
        if turn.action in ('confirm','cancel'):
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                draft=self.store.draft(turn.draft_id,thread_id,owner,db)
                if self.backend.assurance_error(identity):raise PermissionError('Secure verification is required before using a draft')
                if draft['status']=='CANCELLED':raise ValueError('This draft was cancelled')
                if draft['status']=='CONFIRMED':
                    # Re-run the same stored request through current permissions;
                    # never replay a stored success after authority is revoked.
                    pass
                elif datetime.fromisoformat(draft['expires_at'])<=datetime.fromisoformat(self.backend.now.replace('Z','+00:00')):
                    raise ValueError('This draft expired; create a new draft')
                if turn.action=='cancel':
                    if draft['status']=='CONFIRMED':raise ValueError('A committed case cannot be cancelled by this demo')
                    db.execute('UPDATE drafts SET status=\'CANCELLED\' WHERE draft_id=?',(turn.draft_id,))
                    context.pop('draft_id',None)
                    return {'response_state':'CANCELLED','response':'Draft cancelled. No support case was created.','execution_mode':'MOCK'},context
                req=Request.from_dict(draft['payload'])
                if not self.backend.allowed_account(req,req.account_id,'CASE_STATUS'):
                    raise PermissionError('Current account permission is required')
                created=self.backend.create_case(req,connection=db)
                # Preserve unknown outcomes and reconcile without claiming creation.
                if created['status']=='UNKNOWN':
                    row=db.execute('SELECT result FROM events WHERE kind=\'case\' AND owner=? AND request_key=?',(owner,req.request_key)).fetchone()
                    if row:
                        from .contracts import validate_stored_event
                        created=validate_stored_event('case',json.loads(row['result']))
                if created['status']=='OK':
                    db.execute('UPDATE drafts SET status=\'CONFIRMED\',result=? WHERE draft_id=?',(json.dumps(created),turn.draft_id))
                    context.update(case_id=created['event_id']);context.pop('draft_id',None)
                    return {'response_state':'CASE_CREATED','response':f"Support case {created['event_id']} is committed with status OPEN.",'case':created,'execution_mode':'MOCK'},context
                return {'response_state':'UNKNOWN','response':'Case creation is unconfirmed. Retry this same draft reference; do not create another submission.','case':created,'execution_mode':'MOCK'},context
        # IDs may be remembered; protected record fields are always fetched again.
        followup=turn.message.lower().strip() in ('has it posted?','has it posted yet?','show that transaction','what about that transaction?')
        case_followup=turn.message.lower().strip() in ('what is its status?','show that case','what about my case?')
        txs=turn.transaction_ids or (tuple(context.get('transaction_ids',())) if followup else ())
        case_id=turn.case_id or (context.get('case_id') if case_followup else None)
        account=turn.account_id
        if not account:
            session=self.backend.bank._session(identity.session_id)
            if session:
                account=next((a['account_id'] for a in self.backend.bank.accounts if a['customer_id']==session['principal_id']),None)
        backend_key='turn-'+hashlib.sha256((thread_id+':'+turn.request_key).encode()).hexdigest()
        req=Request(message=turn.message,request_key=backend_key,session_id=identity.session_id,
                    transaction_ids=txs,case_id=case_id,account_id=account,product=turn.product)
        result=Workflow(self.backend,ContextModel(self.model,context),engine='langgraph').run(req)
        if txs:context['transaction_ids']=list(txs)
        if case_id:context['case_id']=case_id
        if result['report'].get('status')=='OK':context['report_id']=result['report']['event_id']
        if result['response_state']=='CONFIRMATION_REQUIRED':
            if not account or not self.backend.allowed_account(req,account,'CASE_STATUS'):
                return {'response_state':'AUTH_REQUIRED','response':'Use secure verification before creating a case.','execution_mode':'MOCK'},context
            key='DRAFT-'+hashlib.sha256((thread_id+':'+turn.request_key).encode()).hexdigest()[:24]
            payload={**req.model_dump(mode='json'),'request_key':key,'confirmed':True}
            expiry=(datetime.fromisoformat(self.backend.now.replace('Z','+00:00'))+timedelta(minutes=30)).isoformat()
            self.store.save_draft(key,thread_id,owner,payload,expiry)
            result['draft']={'draft_id':key,'summary':sanitize(turn.message),'account_id':account,'expires_at':expiry}
            result['response']='Review this case summary and select Confirm submission or Cancel. No case has been created.'
            context['draft_id']=key
        return result,context
