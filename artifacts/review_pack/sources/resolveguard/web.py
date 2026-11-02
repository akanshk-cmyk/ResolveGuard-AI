"""Local-only synthetic customer UI. Provider calls and cloud export are absent."""
import hashlib
import json
import secrets
import time
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, Request as HttpRequest, Response, HTTPException
from fastapi.responses import FileResponse,JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from typing import Literal
from .contracts import StrictModel,Faults,Request,Identifier
from .conversation import ConversationService,Turn
from .backend import Backend
from .storage import Store
from .model import TunedMockModel
from .presentation import customer_copy,policy_sources

WEB=Path(__file__).resolve().parent/'static'
PROFILES={'customer-one':('SESS-001','Demo Customer One'),
          'customer-two':('SESS-002','Demo Customer Two'),
          'signed-out':('SESS-ANON','Signed-out visitor'),
          'expired':('SESS-EXPIRED','Expired session')}


class DemoSettings(StrictModel):
    profile:Literal['customer-one','customer-two','signed-out','expired']='customer-one'
    queue_failure:Literal['none','primary','all']='none'


class WebTurn(Turn):
    thread_id:Identifier|None=None


def create_app(database=None):
    import os
    database=database or os.environ.get('RESOLVEGUARD_DB','artifacts/web.sqlite3')
    store=Store(database)
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS web_sessions (token_hash TEXT PRIMARY KEY, settings TEXT NOT NULL)')
        if 'active_thread' not in {r['name'] for r in db.execute('PRAGMA table_info(web_sessions)')}:
            db.execute('ALTER TABLE web_sessions ADD COLUMN active_thread TEXT')
    app=FastAPI(title='ResolveGuard synthetic demo',docs_url=None,redoc_url=None)
    app.mount('/static',StaticFiles(directory=WEB),name='static')
    limits={}

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        return JSONResponse(status_code=422,content={'detail':'Please check your message and selection, then try again.'})

    @app.middleware('http')
    async def local_boundaries(request,call_next):
        if request.method=='POST':
            origin=request.headers.get('origin')
            if origin and origin.rstrip('/')!=str(request.base_url).rstrip('/'):
                return JSONResponse(status_code=403,content={'detail':'Please send your message from the ResolveGuard page.'})
            if int(request.headers.get('content-length','0'))>30000:
                return JSONResponse(status_code=413,content={'detail':'Your message is too long. Please shorten it and try again.'})
        response=await call_next(request)
        response.headers.update({'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
            'Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'"})
        return response

    def context(request):
        token=request.cookies.get('resolveguard_demo')
        if not token:raise HTTPException(401,'Please start the demo first.')
        digest=hashlib.sha256(token.encode()).hexdigest()
        with store.connect() as db:
            row=db.execute('SELECT settings FROM web_sessions WHERE token_hash=?',(digest,)).fetchone()
        if not row:raise HTTPException(401,'Please restart the demo to continue.')
        settings=DemoSettings.model_validate(json.loads(row['settings']))
        sid,name=PROFILES[settings.profile]
        faults=Faults(primary_queue_down=settings.queue_failure!='none',backup_queue_down=settings.queue_failure=='all')
        return digest,sid,name,Backend(store,faults,now=datetime.now(timezone.utc).isoformat())

    @app.get('/')
    def home():return FileResponse(WEB/'index.html')

    @app.get('/api/health')
    def health():return {'status':'ok','mode':'synthetic-mock','provider_calls':False}

    @app.post('/api/session')
    def session(settings:DemoSettings,request:HttpRequest,response:Response):
        old=request.cookies.get('resolveguard_demo')
        token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest()
        with store.connect() as db:
            if old:db.execute('DELETE FROM web_sessions WHERE token_hash=?',(hashlib.sha256(old.encode()).hexdigest(),))
            db.execute('INSERT INTO web_sessions(token_hash,settings) VALUES(?,?)',(digest,settings.model_dump_json()))
        response.set_cookie('resolveguard_demo',token,httponly=True,samesite='strict',secure=request.url.scheme=='https')
        return {'name':PROFILES[settings.profile][1],'mode':'synthetic-mock'}

    @app.get('/api/session')
    def current_session(request:HttpRequest):
        binding,sid,name,backend=context(request)
        with store.connect() as db:
            row=db.execute('SELECT settings,active_thread FROM web_sessions WHERE token_hash=?',(binding,)).fetchone()
        return {'name':name,'thread_id':row['active_thread'],**json.loads(row['settings'])}

    def customer_result(result):
        fields=('response','response_state','thread_id','report','case','handoff','draft','citations','execution_mode')
        return {**{key:result[key] for key in fields if key in result},
                'response':customer_copy(result),'source_details':policy_sources(result),
                'selected_transaction_ids':[r['transaction_id'] for r in result.get('records',[]) if r.get('transaction_id')]}

    @app.get('/api/conversation')
    def restore_conversation(request:HttpRequest):
        binding,sid,name,backend=context(request)
        with store.connect() as db:
            row=db.execute('SELECT active_thread FROM web_sessions WHERE token_hash=?',(binding,)).fetchone()
            thread=row['active_thread']
            last=db.execute('SELECT payload FROM turns WHERE thread_id=? AND result IS NOT NULL ORDER BY rowid DESC LIMIT 1',(thread,)).fetchone() if thread else None
        if not last:return {'thread_id':thread,'result':None}
        result=ConversationService(backend,TunedMockModel(4)).send(sid,thread,Turn.model_validate(json.loads(last['payload'])),client_binding=binding)
        return {'thread_id':thread,'result':customer_result(result)}

    @app.post('/api/conversation/reset')
    def reset_conversation(request:HttpRequest):
        binding,sid,name,backend=context(request)
        with store.connect() as db:
            db.execute('UPDATE web_sessions SET active_thread=NULL WHERE token_hash=?',(binding,))
        return {'status':'NEW_CONVERSATION','reports_preserved':True}

    @app.get('/api/transactions')
    def transactions(request:HttpRequest):
        binding,sid,name,backend=context(request)
        req=Request(message='List authorized synthetic transactions',request_key='list',session_id=sid)
        items=[]
        for tx in backend.bank.transactions:
            result=backend.transaction(req,tx['transaction_id'])
            if result['status']=='OK':items.append(result['data'])
        return {'items':items,'name':name}

    @app.post('/api/chat')
    def chat(turn:WebTurn,request:HttpRequest):
        binding,sid,name,backend=context(request)
        now=time.monotonic();recent=[stamp for stamp in limits.get(binding,[]) if now-stamp<60]
        if len(recent)>=30:raise HTTPException(429,'Please wait a moment before sending another message')
        limits[binding]=recent+[now]
        thread=turn.thread_id or 'thread-'+hashlib.sha256((binding+':'+turn.request_key).encode()).hexdigest()[:32]
        try:
            result=ConversationService(backend,TunedMockModel(4)).send(sid,thread,Turn.model_validate(turn.model_dump(exclude={'thread_id'})),client_binding=binding)
        except PermissionError:
            raise HTTPException(403,'This conversation is not available in the current demo session') from None
        except ValueError:
            raise HTTPException(409,'This request was already used for a different message. Please retry your original message.') from None
        # Customer API intentionally omits internal model context, raw spans and fault settings.
        with store.connect() as db:
            db.execute('UPDATE web_sessions SET active_thread=? WHERE token_hash=?',(thread,binding))
        return customer_result(result)

    return app
