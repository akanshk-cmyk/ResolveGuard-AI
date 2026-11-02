"""Synthetic customer UI; public reply generation is explicitly opt-in."""
import hashlib
import json
import secrets
import time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, Request as HttpRequest, Response, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse,JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from typing import Literal
from .contracts import Faults,Request
from .conversation import ConversationService,Turn
from .backend import Backend
from .storage import Store
from .model import TunedMockModel
from .presentation import customer_copy,policy_sources,customer_cards,format_money,STATUS
from .public_support import public_answer,request_kind,is_public_question,SIGN_IN_MESSAGE

WEB=Path(__file__).resolve().parent/'static'
from .web_contracts import (
    PROFILES, DemoSettings, WebTurn, DemoVerification, DemoSignIn,
    ResumeRequest, NewConversationSettings, DemoCallbackRequest, PublicContext,
)

def create_app(database=None, reply_generator=None):
    import os
    database=database or os.environ.get('RESOLVEGUARD_DB','artifacts/web.sqlite3')
    store=Store(database)
    from .customer_review import CustomerReview
    review=CustomerReview(store)
    from .reply_generation import ReplyGenerator
    replies=reply_generator or ReplyGenerator()
    from .web_storage import initialize_web_storage
    initialize_web_storage(store)
    from contextlib import asynccontextmanager
    import asyncio
    @asynccontextmanager
    async def lifespan(app):
        await asyncio.to_thread(review.process_pending)
        async def audit_worker():
            while True:
                try:
                    await asyncio.to_thread(review.expire_idle)
                    await asyncio.to_thread(review.process_pending)
                except Exception:
                    import logging
                    logging.getLogger(__name__).error('CUSTOMER_AUDIT_WORKER_RETRY_PENDING')
                await asyncio.sleep(30)
        worker=asyncio.create_task(audit_worker())
        try:
            yield
        finally:
            worker.cancel()
            from contextlib import suppress
            with suppress(asyncio.CancelledError):await worker
    app=FastAPI(title='ResolveGuard synthetic demo',docs_url=None,redoc_url=None,lifespan=lifespan)
    app.mount('/static',StaticFiles(directory=WEB),name='static')
    limits={}

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        return JSONResponse(status_code=422,content={'detail':'Please check your message and selection, then try again.'})

    @app.middleware('http')
    async def local_boundaries(request,call_next):
        http_started=time.monotonic()
        if request.method=='POST':
            origin=request.headers.get('origin')
            if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
                return JSONResponse(status_code=403,content={'detail':'Please send your message from the ResolveGuard page.'})
            if int(request.headers.get('content-length','0'))>30000:
                return JSONResponse(status_code=413,content={'detail':'Your message is too long. Please shorten it and try again.'})
        try:
            response=await call_next(request)
        except Exception:
            record_http(request,500,http_started)
            raise
        record_http(request,response.status_code,http_started)
        response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
            'Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'"})
        return response

    def record_http(request,status,started):
        if not request.url.path.startswith('/api/'):return
        from .monitoring import record_observation
        # Route categories only: no query string, submitted fields or credentials.
        category=request.url.path if request.url.path in {'/api/chat','/api/auth/resume','/api/conversation','/api/transactions','/api/cases'} else 'other_api'
        try:
            record_observation({'trace':{'trace_id':str(uuid4()),'spans':[{'latency_ms':(time.monotonic()-started)*1000,'error':status>=500}]},
                'errors':['HTTP_ERROR'] if status>=500 else [],'execution_mode':'SYNTHETIC_HTTP',
                'journey_scope':category,'model_cost_usd':0.0},str(Path(store.path).parent/'operations.sqlite3'))
        except Exception:
            import logging
            logging.getLogger(__name__).warning('HTTP_OBSERVATION_WRITE_FAILED')

    def context(request):
        token=request.cookies.get('resolveguard_demo')
        if not token:raise HTTPException(401,'Please start the demo first.')
        digest=hashlib.sha256(token.encode()).hexdigest()
        with store.connect() as db:
            row=db.execute('SELECT settings,demo_verified,experience_version FROM web_sessions WHERE token_hash=?',(digest,)).fetchone()
        if not row or row['experience_version']!=1:raise HTTPException(401,'Please restart the demo to continue.')
        settings=DemoSettings.model_validate(json.loads(row['settings']))
        sid,name=PROFILES[settings.profile]
        faults=Faults(primary_queue_down=settings.queue_failure!='none',backup_queue_down=settings.queue_failure=='all')
        backend_type=Backend
        if sid.startswith('BOW-'):
            from .bow_backend import BowBackend
            backend_type=BowBackend
        backend=backend_type(store,faults,now=datetime.now(timezone.utc).isoformat())
        backend.demo_verified=bool(row['demo_verified'])
        if settings.profile=='needs-verification' and not row['demo_verified']:
            backend.assurance_events=[]
        return digest,sid,name,backend

    def access_state(sid,backend):
        error=backend.assurance_error(Request(message='Check demo access',request_key='access',session_id=sid,bank_id=backend.bank_id))
        return 'STEP_UP_REQUIRED' if error=='STEP_UP_REQUIRED' else ('SESSION_EXPIRED' if sid=='SESS-EXPIRED' else 'AUTH_REQUIRED') if error else 'VERIFIED'

    @app.get('/')
    def home():return FileResponse(WEB/'index.html')

    @app.get('/api/health')
    def health():return {'status':'ok','mode':'synthetic-mock' if replies.settings.mode=='off' else 'synthetic-public-generation',
                        'provider_calls':replies.settings.mode!='off','reply_mode':replies.settings.mode,
                        'private_reply_framing':replies.settings.mode in {'public_private','all'},
                        'all_feature_reply_framing':replies.settings.mode=='all'}

    @app.get('/api/bow/catalog')
    def bow_catalog():
        from .bow_knowledge import BowKnowledge
        return BowKnowledge().catalog()

    @app.post('/api/public/reset')
    def reset_public(request:HttpRequest):
        binding,sid,name,backend=context(request)
        with store.connect() as db:db.execute('DELETE FROM web_public_context WHERE binding IN (?,?)',(binding,binding+':LEGACY_DEMO'))
        return {'public_context_reset':True}

    def public_bow_turn(binding,turn,backend,knowledge):
        from .public_conversation import public_bow_turn as run_public_turn
        return run_public_turn(binding, turn, backend, knowledge, store=store, review=review)

    @app.post('/api/session')
    def session(settings:DemoSettings,request:HttpRequest,response:Response,background_tasks:BackgroundTasks):
        old=request.cookies.get('resolveguard_demo')
        token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest()
        with store.connect() as db:
            if old:
                old_binding=hashlib.sha256(old.encode()).hexdigest()
                review.close(old_binding,connection=db)
                db.execute('DELETE FROM web_sessions WHERE token_hash=?',(old_binding,))
                db.execute('DELETE FROM web_auth_requests WHERE source_binding=? OR target_binding=?',(old_binding,old_binding))
                db.execute('DELETE FROM web_public_context WHERE binding IN (?,?)',(old_binding,old_binding+':LEGACY_DEMO'))
                db.execute('DELETE FROM web_public_turns WHERE binding IN (?,?)',(old_binding,old_binding+':LEGACY_DEMO'))
                db.execute('DELETE FROM web_generated_replies WHERE binding=?',(old_binding,))
            db.execute('INSERT INTO web_sessions(token_hash,settings,experience_version) VALUES(?,?,1)',(digest,settings.model_dump_json()))
        response.set_cookie('resolveguard_demo',token,httponly=True,samesite='strict',secure=request.url.scheme=='https')
        background_tasks.add_task(review.process_pending)
        return {'name':PROFILES[settings.profile][1],'mode':'synthetic-mock'}

    def pending_request(binding,turn):
        payload=turn.model_dump_json()
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM web_auth_requests WHERE source_binding=? AND request_key=?',(binding,turn.request_key)).fetchone()
            if old:
                if old['payload']!=payload:raise HTTPException(409,'Please retry your original request.')
                return old['pending_id']
            key='pending-'+uuid4().hex
            expires=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat()
            db.execute('INSERT INTO web_auth_requests VALUES(?,?,?,?,?,?)',(key,binding,turn.request_key,payload,None,expires))
            return key

    @app.post('/api/auth/demo-sign-in')
    def demo_sign_in(body:DemoSignIn,request:HttpRequest,response:Response,background_tasks:BackgroundTasks):
        binding,sid,name,backend=context(request)
        token=secrets.token_urlsafe(32);target=hashlib.sha256(token.encode()).hexdigest()
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            pending=db.execute('SELECT * FROM web_auth_requests WHERE pending_id=? AND source_binding=?',(body.pending_id,binding)).fetchone() if body.pending_id else None
            if body.pending_id and (not pending or pending['expires_at']<=datetime.now(timezone.utc).isoformat()):
                raise HTTPException(403,'This sign-in request has expired or is not available. Please ask again.')
            if pending:
                saved=WebTurn.model_validate_json(pending['payload'])
                chosen_bank='BOW' if body.profile.startswith('bow-') else 'LEGACY_DEMO'
                if chosen_bank!=saved.bank_id:raise HTTPException(409,'Choose a sample sign-in for the bank in your saved request.')
            settings=DemoSettings(profile=body.profile)
            db.execute('INSERT INTO web_sessions(token_hash,settings,experience_version) VALUES(?,?,1)',(target,settings.model_dump_json()))
            if pending:
                db.execute('UPDATE web_auth_requests SET target_binding=? WHERE pending_id=?',(target,body.pending_id))
                source_generation=db.execute('SELECT generation FROM review_sessions WHERE binding=?',(binding,)).fetchone()
                source_ref='session-'+binding+':g'+str(source_generation[0] if source_generation else 0)
                db.execute('INSERT OR IGNORE INTO review_session_links VALUES(?,?,?,?)',
                           (source_ref,'session-'+target+':g0',saved.bank_id,'AUTHENTICATION_CONTINUATION_NO_AUTHORITY_TRANSFER'))
            review.close(binding,connection=db)
            db.execute('DELETE FROM web_sessions WHERE token_hash=?',(binding,))
        response.set_cookie('resolveguard_demo',token,httponly=True,samesite='strict',secure=request.url.scheme=='https')
        background_tasks.add_task(review.process_pending)
        return {'demo_only':True,'pending_id':body.pending_id,'additional_verification':body.profile in {'needs-verification','bow-needs-verification'}}

    @app.post('/api/session/verification')
    def verify_demo(body:DemoVerification,request:HttpRequest):
        binding,sid,name,backend=context(request)
        if sid not in {'SESS-STEPUP','BOW-SESS-003'}:
            raise HTTPException(409,'This sample session does not need an extra check.')
        with store.connect() as db:
            db.execute('UPDATE web_sessions SET demo_verified=? WHERE token_hash=?',(int(body.action=='confirm'),binding))
        return {'demo_only':True,'state':'VERIFIED' if body.action=='confirm' else 'STEP_UP_REQUIRED'}

    @app.get('/api/session')
    def current_session(request:HttpRequest):
        binding,sid,name,backend=context(request)
        with store.connect() as db:
            row=db.execute('SELECT settings,active_thread FROM web_sessions WHERE token_hash=?',(binding,)).fetchone()
            pending=db.execute('''SELECT pending_id FROM web_auth_requests WHERE
                (target_binding=? OR (source_binding=? AND target_binding IS NULL)) AND expires_at>?
                ORDER BY expires_at DESC LIMIT 1''',(binding,binding,datetime.now(timezone.utc).isoformat())).fetchone()
        return {'name':name,'thread_id':row['active_thread'],'access_state':access_state(sid,backend),'bank_id':backend.bank_id,
                'session_marker':hashlib.sha256(('display:'+binding).encode()).hexdigest(),
                'pending_id':pending['pending_id'] if pending else None,'demo_only':True,**json.loads(row['settings'])}

    def customer_result(result):
        if result.get('emergency'):
            return {key:value for key,value in result.items() if key not in {'records','trace','tools','model_context'}}
        fields=('response','response_state','thread_id','report','case','handoff','notice','draft','citations','execution_mode','bank_id')
        return {**{key:result[key] for key in fields if key in result},
                'response':customer_copy(result),'source_details':policy_sources(result),'cards':customer_cards(result),
                'presentation_version':'customer-ui-v2',
                'selected_transaction_ids':[r['transaction_id'] for r in result.get('records',[]) if r.get('transaction_id')]}

    def require_sign_in(binding,sid,backend,turn,result=None):
        state=access_state(sid,backend) if turn.bank_id==backend.bank_id else 'AUTH_REQUIRED'
        output=result or {'response':'','cards':[],'source_details':[]}
        key=pending_request(binding,turn) if turn.action=='message' else None
        if key and state=='STEP_UP_REQUIRED':
            # This customer is already signed in; only assurance must increase.
            with store.connect() as db:
                db.execute('UPDATE web_auth_requests SET target_binding=? WHERE pending_id=? AND source_binding=? AND target_binding IS NULL',
                           (binding,key,binding))
        return {**output,'response':(output.get('response','')+'\n\n' if output.get('response') else '')+
                ("Please complete the additional secure verification to view your account details." if state=='STEP_UP_REQUIRED' else SIGN_IN_MESSAGE),
                'response_state':'STEP_UP_REQUIRED' if state=='STEP_UP_REQUIRED' else 'AUTH_REQUIRED',
                'data_scope':'INTAKE' if output.get('report') else 'PUBLIC','auth_required':True,'pending_id':key,
                'cards':[],'auth_state':state}

    def permitted_transactions(sid,backend,turn):
        req=Request(message=turn.message,request_key=turn.request_key,session_id=sid,bank_id=backend.bank_id)
        if turn.account_id and not backend.allowed_account(req,turn.account_id):return []
        rows=[]
        for tx in backend.bank.transactions:
            if turn.account_id and tx['account_id']!=turn.account_id:continue
            result=backend.transaction(req,tx['transaction_id'])
            if result['status']=='OK':rows.append(result['data'])
        return rows

    def execute_turn_unreviewed(turn,request):
        import re
        binding,sid,name,backend=context(request)
        from .security_routing import assess_security, record_security, BLOCK_MESSAGE, EDUCATION_MESSAGE
        security=assess_security(turn.message)
        from .request_context import bind_turn
        try:
            turn=bind_turn(turn)
        except ValueError:
            if request_kind(turn)=='REPORT':
                turn=turn.model_copy(update={'account_id':None,'case_id':None,'transaction_ids':()})
            else:
                return {'response':'Please choose one account or support request so I can check the correct access.',
                        'response_state':'CLARIFICATION_REQUIRED','data_scope':'PUBLIC','auth_required':False,'cards':[],'source_details':[]}
        from .onboarding import is_greeting,WELCOME_MESSAGE
        if turn.action=='message' and is_greeting(turn.message):
            return {'response':WELCOME_MESSAGE,'response_state':'WELCOME','data_scope':'PUBLIC',
                    'bank_id':turn.bank_id,'auth_required':False,'cards':[],'source_details':[]}
        from .fraud_triage import active_theft,triage
        if turn.action=='message' and active_theft(turn.message):
            from .telemetry import utcnow
            trigger=utcnow()
            req=Request(message=turn.message,request_key='emergency-'+hashlib.sha256((binding+':'+turn.request_key).encode()).hexdigest(),
                        session_id='SESS-ANON' if turn.bank_id=='BOW' and backend.bank_id!='BOW' else sid,
                        bank_id=turn.bank_id,account_id=None if security.blocked else turn.account_id,
                        transaction_ids=() if security.blocked else turn.transaction_ids)
            output,trace,tools=triage(backend,req,trigger,blocked=security.blocked)
            output.pop('records',None)
            review.capture_workflow(binding,turn.request_key,{'trace':trace,'tools':tools,'bank_id':turn.bank_id,
                'response_state':'EMERGENCY_FRAUD','execution_mode':'SYNTHETIC_EMERGENCY'})
            if output['emergency']['requires_auth'] and not security.blocked:
                return require_sign_in(binding,sid,backend,turn,output)
            return output
        # Reports take precedence over refusal, but injected restricted reads do not.
        report_requested=request_kind(turn)=='REPORT'
        if security.blocked or security.recommended_action=='PUBLIC_SECURITY_INFORMATION':
            record_security(store,security,binding,turn.request_key,turn.bank_id,
                            'NOT_ATTEMPTED_BLOCKED' if security.blocked else 'NOT_REQUIRED',report_requested)
            if not report_requested:
                review.capture_workflow(binding,turn.request_key,{'bank_id':turn.bank_id,'tools':[{'name':'deny_prohibited_request','status':'BLOCKED','kind':'GUARD'}] if security.blocked else [],'response_state':'SECURITY_BLOCKED' if security.blocked else 'PUBLIC_SECURITY_INFORMATION'})
                return {'response':BLOCK_MESSAGE if security.blocked else EDUCATION_MESSAGE,
                        'response_state':'SECURITY_BLOCKED' if security.blocked else 'PUBLIC_SECURITY_INFORMATION',
                        'data_scope':'PUBLIC','bank_id':turn.bank_id,'auth_required':False,'cards':[],'source_details':[]}
            if security.blocked:
                turn=turn.model_copy(update={'transaction_ids':(), 'account_id':None,'case_id':None})
        if turn.thread_id:
            with store.connect() as db:
                row=db.execute('SELECT binding FROM conversation_threads WHERE thread_id=?',(turn.thread_id,)).fetchone()
            if not row or row['binding']!=sid+':'+binding:
                raise HTTPException(403,'This conversation is not available in the current demo session')
        kind=request_kind(turn)
        if kind=='UNSUPPORTED':
            from .request_context import TRANSFER_MESSAGE
            return {'response':TRANSFER_MESSAGE,'response_state':'PROHIBITED_ACTION','data_scope':'PUBLIC',
                    'bank_id':turn.bank_id,'auth_required':False,'cards':[],'source_details':[]}
        if turn.bank_id=='BOW' and is_public_question(turn) and any(word in turn.message.lower() for word in ('policy','how do','how does')):kind='PUBLIC'
        if turn.bank_id=='BOW':
            from .bow_knowledge import BowKnowledge
            knowledge=BowKnowledge()
            import re
            private_words=re.search(r'\b(my|our|mine|charged|transaction|payment|statement|case|i was|i got|i paid)\b',turn.message.lower())
            if turn.action=='message' and kind!='REPORT' and not private_words and not turn.case_id and not turn.account_id:
                if knowledge.question_topic(turn.message)!='UNKNOWN' or knowledge.named_products(turn.message) or turn.message.lower().strip() in {'1','2','3','first','first one','second','second one','third','third one'}:
                    kind='PUBLIC'
            if kind=='PUBLIC':
                return public_bow_turn(binding,turn,backend,knowledge)
        if kind=='PUBLIC':
            from .public_support import LegacyPublicKnowledge
            return public_bow_turn(binding,turn,backend,LegacyPublicKnowledge())
        if turn.bank_id=='BOW' and kind=='PROTECTED' and any(word in turn.message.lower() for word in ('credit card','yolo','miles card')):
            return {'response':'Credit-card servicing is outside this MVP. Public BOW credit-card product information is available without sign-in.',
                    'response_state':'PROHIBITED_ACTION','data_scope':'PUBLIC','bank_id':'BOW','cards':[],'auth_required':False,'source_details':[]}
        restricted=kind=='PROTECTED'
        state=access_state(sid,backend) if turn.bank_id==backend.bank_id else 'AUTH_REQUIRED'
        if restricted:
            record_security(store,security,binding,turn.request_key,turn.bank_id,
                            'DEFER_TO_RESOURCE_AUTHORIZATION' if state=='VERIFIED' else state,
                            response_category='PROTECTED_BANKING_FLOW' if state=='VERIFIED' else state)
        if restricted and state!='VERIFIED':
            review.capture_workflow(binding,turn.request_key,{'bank_id':turn.bank_id,'tools':[{'name':'secure_sign_in','status':'REQUIRED','executed':False}],'response_state':'AUTH_REQUIRED'})
            return require_sign_in(binding,sid,backend,turn)
        if restricted:
            from .telemetry import Trace
            target_trace=Trace({'workflow':'requested-resource-authorization','bank_id':turn.bank_id,'version':'request-context-v1'})
            decisions=[]
            req=Request(message='Check requested resource',request_key=turn.request_key,session_id=sid,bank_id=turn.bank_id,account_id=turn.account_id,case_id=turn.case_id)
            with target_trace.span('authorization.requested_resource','guard') as span:
                if turn.case_id:
                    check=backend.case_status(req)
                    decisions.append({'name':'get_case_status','status':check['status'],'reason_code':check.get('reason_code')})
                elif turn.account_id:
                    check=backend.bank.check_authority(sid,turn.account_id,'TRANSACTION_READ',req.service_id) if turn.bank_id==backend.bank_id else {'status':'DENIED','reason_code':'BANK_SCOPE_MISMATCH'}
                    decisions.append({'name':'check_authority','status':check['status'],'reason_code':check.get('reason_code')})
                else:check={'status':'OK'}
                span['outputs']={'status':check['status'],'reason_code':check.get('reason_code')}
            if check['status']=='DENIED':
                handoff={}
                # Denying case access must not discard an independent request
                # for a person. Transfer no denied account/case context.
                if TunedMockModel(4).classify(turn.message)['human_requested']:
                    with target_trace.span('handoff_to_human','tool',{'context':'NO_RESTRICTED_RESOURCE'}) as handoff_span:
                        handoff=backend.handoff(req.model_copy(update={'case_id':None,'account_id':None}),{},urgent=False)
                        handoff_span['outputs']={'status':handoff.get('status'),'handoff_status':handoff.get('handoff_status')}
                    decisions.append({'name':'handoff_to_human','status':handoff.get('status')})
                review.capture_workflow(binding,turn.request_key,{'trace':target_trace.export(),'tools':decisions,'bank_id':turn.bank_id,'response_state':'ACCESS_DENIED'})
                response="Your current access does not permit the requested account or support request. I haven't shown its details or substituted another payment."
                if handoff.get('handoff_status')=='ACKNOWLEDGED':
                    response+='\n\nThe demo support team received your request for help. No restricted case details were shared.'
                elif handoff:
                    response+='\n\nA support connection is not confirmed. Please use your bank\'s approved support channel.'
                return {'response':response,'handoff':handoff,'response_state':'ACCESS_DENIED','data_scope':'PUBLIC',
                        'auth_required':False,'cards':[],'source_details':[]}
        if restricted and turn.message.lower().strip()=='show my cases':
            listed=cases(request,bank_id=turn.bank_id)
            records=[dict(r,kind='case') for r in listed['items']]
            return {'response':'Here are your permitted sample support requests.' if records else 'No permitted support requests are available.',
                    'response_state':'AUTHORIZED_READ','cards':customer_cards({'records':records}),
                    'data_scope':'RESTRICTED','auth_required':False,'open_cases':True,'source_details':[]}
        if restricted and 'balance' in turn.message.lower():
            return {'response':'Balance information is not available in this support demo. Please use the bank\'s account overview.',
                    'response_state':'SERVICE_UNAVAILABLE','cards':[],'data_scope':'RESTRICTED','auth_required':False,'source_details':[]}
        # Report intake never waits for sign-in or attempts restricted reads first.
        guest_report=kind=='REPORT' and state!='VERIFIED'
        if guest_report:
            req=Request(message=turn.message,request_key='guest-'+hashlib.sha256((binding+':'+turn.request_key).encode()).hexdigest(),
                        session_id='SESS-ANON' if turn.bank_id=='BOW' and backend.bank_id!='BOW' else sid,transaction_ids=turn.transaction_ids,bank_id=turn.bank_id)
            report=backend.capture(req)
            if report.get('status')=='UNKNOWN':
                recovered=backend.lookup_report(req)
                if recovered.get('status')=='OK':report=recovered
            handoff=backend.handoff(req,report,urgent=True)
            result={'route':{'primary_intent':'FRAUD_ERROR_REPORT'},'report':report,'handoff':handoff,
                    'records':[],'citations':[],'case':{},'response_state':'REPORT_CAPTURED' if report.get('status')=='OK' else 'SUBMISSION_UNCONFIRMED',
                    'execution_mode':'MOCK','bank_id':turn.bank_id}
            output={**customer_result(result),'data_scope':'INTAKE','auth_required':False}
            if report.get('status')=='OK' and not turn.transaction_ids:
                from .request_context import REPORT_FOLLOWUP
                output['response']+='\n\n'+REPORT_FOLLOWUP
            review.capture_workflow(binding,turn.request_key,{**result,'tools':[{'name':'record_issue_intake','status':report.get('status')},{'name':'handoff_to_human','status':handoff.get('status')}]})
            if turn.transaction_ids:
                lookup=turn.model_copy(update={'message':'Show the selected transaction details','thread_id':None})
                return require_sign_in(binding,sid,backend,lookup,output)
            return output
        from .request_context import charge_inquiry, match_charges
        # A new amount/date question is not about an old dropdown selection.
        if (restricted and charge_inquiry(turn.message)
                and re.search(r'\$\s*\d|\b\d+(?:\.\d+)?\s*(?:dollars?|usd)\b|\b(?:last|this) month\b',turn.message,re.I)
                and not re.search(r'\b(selected|this payment|that payment|this transaction|that transaction)\b',turn.message,re.I)):
            turn=turn.model_copy(update={'transaction_ids':()})
        if (restricted and not turn.transaction_ids and not turn.case_id and turn.action=='message'
                and TunedMockModel(4).classify(turn.message)['primary_intent']!='SUPPORT_CASE_REQUEST'):
            text=turn.message.lower()
            if turn.account_id or charge_inquiry(text) or any(s in text for s in ('recent transactions','transaction history','why was i charged','why did i get','my transactions')):
                rows=permitted_transactions(sid,backend,turn)
                if charge_inquiry(text) or 'fee' in text:
                    rows=match_charges(rows,text,backend.now)
                    if not rows:
                        return {'response':'I could not find a permitted payment matching that amount and date. Please check the amount and month, or select the payment you mean.',
                                'response_state':'CLARIFICATION_REQUIRED','data_scope':'RESTRICTED','auth_required':False,'cards':[],'source_details':[]}
                    if len(rows)>1:
                        records=[dict(r,kind='transaction') for r in rows[:5]]
                        return {'response':'More than one permitted sample payment matches. Which payment do you mean?',
                                'response_state':'CLARIFICATION_REQUIRED','cards':customer_cards({'records':records}),
                                'select_payment':True,'request_message':turn.message,'data_scope':'RESTRICTED',
                                'auth_required':False,'source_details':[]}
                else:rows=sorted(rows,key=lambda r:r['posted_on'],reverse=True)[:5]
                if rows:turn=turn.model_copy(update={'transaction_ids':tuple(r['transaction_id'] for r in rows)})
        thread=turn.thread_id or 'thread-'+hashlib.sha256((binding+':'+turn.request_key).encode()).hexdigest()[:32]
        try:
            result=ConversationService(backend,TunedMockModel(4)).send(sid,thread,Turn.model_validate(turn.model_dump(exclude={'thread_id','bank_id','product_id'})),client_binding=binding)
        except PermissionError:
            raise HTTPException(403,'This conversation is not available in the current demo session') from None
        except ValueError:
            raise HTTPException(409,'This request was already used for a different message. Please retry your original message.') from None
        with store.connect() as db:
            db.execute('UPDATE web_sessions SET active_thread=? WHERE token_hash=?',(thread,binding))
        output={**customer_result(result),'data_scope':'INTAKE' if kind in {'REPORT','SUPPORT'} and not result.get('records') else 'RESTRICTED','auth_required':False}
        review.capture_workflow(binding,turn.request_key,result)
        return output

    def gate_output(output,turn,request):
        binding,sid,name,backend=context(request)
        from .customer_review import fingerprint
        with store.connect() as db:
            recorded=db.execute('SELECT payload FROM review_workflow WHERE binding=? AND request_ref=?',
                                (binding,fingerprint(turn.request_key))).fetchone()
        if not recorded or not json.loads(recorded[0]).get('trace'):
            from .telemetry import Trace
            boundary=Trace({'workflow':'response-boundary','bank_id':turn.bank_id,'schema_version':'customer-trace-v2'})
            with boundary.span('authorization.response_boundary') as span:
                span['outputs']={'access_state':access_state(sid,backend),'response_state':output.get('response_state')}
            review.attach_request_trace(binding,turn.request_key,turn.bank_id,boundary.export())
        private=False
        if (replies.settings.mode in {'public_private','all'} and access_state(sid,backend)=='VERIFIED'
                and output.get('data_scope')=='RESTRICTED' and output.get('cards')
                and not any(output.get(k) for k in ('report','case','handoff','draft','notice','callback','auth_required'))):
            # Re-authorize every displayed resource before consulting the model
            # or a cached generated response. Chat claims never grant access.
            req=Request(message='Verify reply access',request_key=turn.request_key,session_id=sid,bank_id=turn.bank_id)
            records=[]
            for card in output['cards']:
                if card.get('kind')=='transaction':
                    found=backend.transaction(req,card.get('reference','missing'))
                elif card.get('kind')=='case':
                    found=backend.case_status(req.model_copy(update={'case_id':card.get('reference')}))
                else:break
                if found.get('status')!='OK':break
                records.append(dict(found['data'],kind=card['kind']))
            private=(len(records)==len(output['cards']) and output['cards']==customer_cards({'records':records,'bank_id':turn.bank_id})
                     and output.get('response')==customer_copy({'records':records}))
        if not output.get('emergency') and output.get('response_state')!='WELCOME' and replies.settings.mode!='off' and (replies.settings.mode=='all' or output.get('response_state')=='PUBLIC_GUIDANCE' or private):
            from .answer_evidence import verify_answer
            from .telemetry import Trace
            # Never send unverified source claims or raw session/customer state.
            if private or not verify_answer(output,turn.bank_id,backend.now[:10],turn.message):
                digest=hashlib.sha256(json.dumps(output,sort_keys=True).encode()).hexdigest()
                with store.connect() as db:
                    db.execute('INSERT OR IGNORE INTO web_generated_replies(binding,request_key,evidence_hash,created_at) VALUES(?,?,?,?)',(binding,turn.request_key,digest,time.time()))
                    reserved=db.execute('SELECT changes()').fetchone()[0]==1
                    cached=db.execute('SELECT * FROM web_generated_replies WHERE binding=? AND request_key=?',(binding,turn.request_key)).fetchone()
                if cached['evidence_hash']!=digest:
                    raise HTTPException(409,'Please send a new question to check the latest details.')
                if cached['result']:
                    output=json.loads(cached['result'])
                elif reserved:
                    trace=Trace({'workflow':'public-reply-generation','bank_id':turn.bank_id})
                    output=replies.run(output,trace,as_of=backend.now[:10],private=private)
                    with store.connect() as db:
                        db.execute('UPDATE web_generated_replies SET result=?,trace=? WHERE binding=? AND request_key=? AND result IS NULL',
                            (json.dumps(output),json.dumps(trace.export()),binding,turn.request_key))
                        output=json.loads(db.execute('SELECT result FROM web_generated_replies WHERE binding=? AND request_key=?',(binding,turn.request_key)).fetchone()[0])
                    review.append_generation(binding,turn.request_key,trace.export(),output.get('generation',{}))
                elif time.time()-cached['created_at']<15:
                    raise HTTPException(409,'This answer is still being prepared. Please retry the same request.')
                else:
                    output=dict(output,generation={'outcome':'FALLBACK','failure_code':'INTERRUPTED_GENERATION_RECOVERED'})
                    with store.connect() as db:
                        db.execute('UPDATE web_generated_replies SET result=? WHERE binding=? AND request_key=? AND result IS NULL',
                                   (json.dumps(output),binding,turn.request_key))
                        output=json.loads(db.execute('SELECT result FROM web_generated_replies WHERE binding=? AND request_key=?',(binding,turn.request_key)).fetchone()[0])
        # Recheck current session/time after the bounded external call.
        binding,sid,name,backend=context(request)
        result=review.gate(output,binding=binding,sid=sid,backend=backend,bank_id=turn.bank_id,
                           request_key=turn.request_key,access_state=access_state(sid,backend),message=turn.message,action=turn.action)
        if access_state(sid,backend)=='SESSION_EXPIRED':review.close(binding,'SESSION_EXPIRED')
        if output.get('emergency'):
            try:
                from .telemetry import Trace
                from .customer_review import fingerprint
                delivery=Trace({'workflow':'emergency.response','request_ref':fingerprint(turn.request_key)})
                with delivery.span('emergency.response_approved') as span:
                    span['outputs']={'response':result['response'],'response_state':result['response_state'],
                                     'delivery_status':'APPROVED_FOR_TRANSPORT'}
                review.append_generation(binding,turn.request_key,delivery.export(),{})
                from .eval_config import cloud_tracing_enabled
                if cloud_tracing_enabled():
                    from .monitoring import observe
                    with store.connect() as db:
                        saved=db.execute('SELECT payload FROM review_workflow WHERE binding=? AND request_ref=?',(binding,fingerprint(turn.request_key))).fetchone()
                    observe({'trace':json.loads(saved[0])['trace'],'execution_mode':'SYNTHETIC_EMERGENCY','errors':[]})
            except Exception:
                import logging
                logging.getLogger(__name__).warning('EMERGENCY_DELIVERY_TELEMETRY_FAILED')
        return result

    def execute_turn(turn,request):
        binding,sid,name,backend=context(request)
        review.start_turn(binding,turn.request_key,turn.bank_id)
        from .telemetry import Trace
        trace=Trace({'workflow':'customer-web-dispatch','bank_id':turn.bank_id,
                     'request_ref':hashlib.sha256(turn.request_key.encode()).hexdigest(),
                     'schema_version':'customer-trace-v2','router_version':'request-context-v1'})
        try:
            with trace.span('web.dispatch',inputs={'action':turn.action}) as span:
                output=execute_turn_unreviewed(turn,request)
                span['outputs']={'response_state':output.get('response_state'),'data_scope':output.get('data_scope'),
                                 'source_refs':[s.get('reference') for s in output.get('source_details',[])],
                                 'auth_required':output.get('auth_required',False)}
            review.attach_request_trace(binding,turn.request_key,turn.bank_id,trace.export())
            return gate_output(output,turn,request)
        except Exception:
            review.fail_turn(binding,turn.request_key)
            review.attach_request_trace(binding,turn.request_key,turn.bank_id,trace.export())
            raise

    @app.post('/api/auth/resume')
    def resume(body:ResumeRequest,request:HttpRequest):
        binding,sid,name,backend=context(request)
        with store.connect() as db:
            row=db.execute('SELECT * FROM web_auth_requests WHERE pending_id=? AND target_binding=?',(body.pending_id,binding)).fetchone()
        if not row or row['expires_at']<=datetime.now(timezone.utc).isoformat():
            raise HTTPException(403,'This saved request has expired or is not available. Please ask again.')
        saved=WebTurn.model_validate_json(row['payload'])
        saved=saved.model_copy(update={'thread_id':None,'request_key':'resume-'+body.pending_id})
        if access_state(sid,backend)!='VERIFIED':
            return gate_output({'response_state':'STEP_UP_REQUIRED','response':'Please complete additional verification to continue.',
                    'auth_required':True,'pending_id':body.pending_id,'auth_state':access_state(sid,backend),'cards':[],'data_scope':'PUBLIC'},saved,request)
        return {**execute_turn(saved,request),'resumed':True,'original_request':saved.message}

    @app.post('/api/auth/cancel')
    def cancel_sign_in(body:ResumeRequest,request:HttpRequest):
        binding,sid,name,backend=context(request)
        with store.connect() as db:
            db.execute('DELETE FROM web_auth_requests WHERE pending_id=? AND (source_binding=? OR target_binding=?)',
                       (body.pending_id,binding,binding))
        return {'cancelled':True,'reports_preserved':True}

    @app.get('/api/conversation')
    def restore_conversation(request:HttpRequest):
        binding,sid,name,backend=context(request)
        with store.connect() as db:
            row=db.execute('SELECT active_thread FROM web_sessions WHERE token_hash=?',(binding,)).fetchone()
            thread=row['active_thread']
            last=db.execute('SELECT payload FROM turns WHERE thread_id=? AND result IS NOT NULL ORDER BY rowid DESC LIMIT 1',(thread,)).fetchone() if thread else None
        if not last:return {'thread_id':thread,'result':None}
        result=ConversationService(backend,TunedMockModel(4)).send(sid,thread,Turn.model_validate(json.loads(last['payload'])),client_binding=binding)
        turn=WebTurn.model_validate({**json.loads(last['payload']),'bank_id':backend.bank_id})
        return {'thread_id':thread,'result':gate_output(customer_result(result),turn,request)}

    @app.post('/api/conversation/reset')
    def reset_conversation(request:HttpRequest,response:Response,background_tasks:BackgroundTasks,settings:NewConversationSettings|None=None):
        if settings and settings.guest:
            session(DemoSettings(),request,response,background_tasks)
            return {'status':'NEW_CONVERSATION','guest':True,'reports_preserved':True}
        binding,sid,name,backend=context(request)
        with store.connect() as db:
            review.close(binding,connection=db)
            db.execute('UPDATE web_sessions SET active_thread=NULL WHERE token_hash=?',(binding,))
            db.execute('DELETE FROM web_auth_requests WHERE source_binding=? OR target_binding=?',(binding,binding))
            db.execute('DELETE FROM web_public_context WHERE binding IN (?,?)',(binding,binding+':LEGACY_DEMO'))
        background_tasks.add_task(review.process_pending)
        return {'status':'NEW_CONVERSATION','reports_preserved':True}

    @app.get('/api/transactions')
    def transactions(request:HttpRequest,offset:int=0,limit:int=5,bank_id:Literal['BOW','LEGACY_DEMO']|None=None):
        if offset<0 or not 1<=limit<=10:raise HTTPException(422,'Please choose a valid page.')
        binding,sid,name,backend=context(request)
        from .account_views import transaction_page
        return transaction_page(sid, backend, name, offset, limit, bank_id, access_state=access_state)

    @app.get('/api/cases')
    def cases(request:HttpRequest,offset:int=0,limit:int=5,bank_id:Literal['BOW','LEGACY_DEMO']|None=None):
        if offset<0 or not 1<=limit<=10:raise HTTPException(422,'Please choose a valid page.')
        binding,sid,name,backend=context(request)
        from .account_views import case_page
        return case_page(sid, backend, name, offset, limit, bank_id, access_state=access_state, store=store)

    @app.post('/api/chat')
    def chat(turn:WebTurn,request:HttpRequest):
        binding,sid,name,backend=context(request)
        now=time.monotonic();recent=[stamp for stamp in limits.get(binding,[]) if now-stamp<60]
        if len(recent)>=30:raise HTTPException(429,'Please wait a moment before sending another message')
        limits[binding]=recent+[now]
        return execute_turn(turn,request)

    @app.post('/api/demo/callback')
    def demo_callback(body:DemoCallbackRequest,request:HttpRequest):
        binding,sid,name,backend=context(request)
        from .demo_operations import DemoOperations
        operations=DemoOperations(store)
        req=Request(message='Request a simulated callback',request_key=body.request_key,session_id=sid,bank_id=backend.bank_id)
        try:
            commitment=operations.callback(backend,req,body.handoff_ref,consented=body.consent)
            handoff=operations.receipt(backend,req,body.handoff_ref)
        except PermissionError:raise HTTPException(403,'Sign in and request a callback only for your own acknowledged support request.') from None
        output={'response':'Demo only: a simulated callback window is recorded from '+commitment.window_start+' to '+commitment.window_end+'. No real telephone call is scheduled.',
                'response_state':'DEMO_CALLBACK_CONFIRMED','bank_id':backend.bank_id,'data_scope':'INTAKE','cards':[],
                'auth_required':False,'source_details':[],'handoff':handoff,'callback':commitment.model_dump(mode='json')}
        return gate_output(output,WebTurn(message=req.message,request_key=req.request_key,bank_id=backend.bank_id),request)

    return app
