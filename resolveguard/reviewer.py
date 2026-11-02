"""Scoped local staff review, immutable application history and encrypted exports.

Local demonstration identity only; no banking permissions are granted here.
"""
import base64
import csv
import hashlib
import io
import json
import re
import secrets
from datetime import datetime, timezone,timedelta
from pathlib import Path
from typing import Literal
from pydantic import Field
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from .contracts import StrictModel, Identifier
from .storage import Store
from .customer_review import CustomerReview, fingerprint
from .telemetry import sanitize


def masked(value):
    value=sanitize(value)
    if isinstance(value,dict):return {k:masked(v) for k,v in value.items()}
    if isinstance(value,list):return [masked(v) for v in value]
    if isinstance(value,str):
        return re.sub(r'\b(?:BOW-)?(?:ACC|CUST|SESS)-[A-Za-z0-9-]+\b',lambda m:'TOKEN-'+hashlib.sha256(m[0].encode()).hexdigest()[:12],value)
    return value


class ReviewNote(StrictModel):
    review_id:Identifier
    expected_revision:int
    status:Literal['UNDER_REVIEW','COMPLETE','ESCALATED','POLICY_VIOLATION']
    note:str


class StaffAccount(StrictModel):
    user_id:Identifier
    role:Literal['VIEWER','REVIEWER','ADMIN']
    banks:list[Literal['BOW','LEGACY_DEMO']]


class ExportRequest(StrictModel):
    session_ref:Identifier
    password:str
    format:Literal['JSON','CSV']='JSON'


class AlertRule(StrictModel):
    rule_id:Identifier
    metric:Literal['failed_checks','denied_access','latency_ms','review_backlog','confusion_count']
    threshold:float=Field(ge=0,allow_inf_nan=False)
    window:int=Field(default=20,ge=1,le=200)


def init_reviewer(store,token):
    CustomerReview(store)
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS review_staff (token_hash TEXT PRIMARY KEY,user_id TEXT UNIQUE,role TEXT,banks TEXT)')
        db.execute('INSERT INTO review_staff(token_hash,user_id,role,banks) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET token_hash=excluded.token_hash',
            (fingerprint(token),'local-demo-admin','ADMIN',json.dumps(['BOW','LEGACY_DEMO'])))
        if 'expires_at' not in {r['name'] for r in db.execute('PRAGMA table_info(review_staff)')}:db.execute('ALTER TABLE review_staff ADD COLUMN expires_at TEXT')
        db.execute('''CREATE TABLE IF NOT EXISTS review_notes (
            event_id TEXT PRIMARY KEY,review_id TEXT,revision INTEGER,actor TEXT,created_at TEXT,
            status TEXT,note TEXT,previous_hash TEXT,event_hash TEXT,UNIQUE(review_id,revision))''')
        for operation in ('UPDATE','DELETE'):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS notes_no_{operation.lower()} BEFORE {operation} ON review_notes BEGIN SELECT RAISE(ABORT,'Review history is append-only'); END")
        db.execute('CREATE TABLE IF NOT EXISTS review_details (review_id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS review_workflow (binding TEXT,request_ref TEXT,payload TEXT,PRIMARY KEY(binding,request_ref))')
        db.execute('CREATE TABLE IF NOT EXISTS review_alert_rules (rule_id TEXT PRIMARY KEY,payload TEXT,actor TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS review_alerts (alert_id TEXT PRIMARY KEY,rule_id TEXT,status TEXT,payload TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS review_export_log (export_id TEXT PRIMARY KEY,actor TEXT,session_ref TEXT,created_at TEXT,manifest_sha256 TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS review_activity (event_id TEXT PRIMARY KEY,actor TEXT,route TEXT,status INTEGER,created_at TEXT)')
        for operation in ('UPDATE','DELETE'):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS activity_no_{operation.lower()} BEFORE {operation} ON review_activity BEGIN SELECT RAISE(ABORT,'Staff activity is append-only'); END")


def install_reviewer(app, database, token):
    store=Store(database);init_reviewer(store,token)
    static=Path(__file__).parent/'static'

    @app.middleware('http')
    async def staff_activity(request,call_next):
        response=await call_next(request)
        if request.url.path.startswith('/api/reviewer/'):
            supplied=request.headers.get('authorization','').removeprefix('Bearer ')
            with store.connect() as db:
                actor=db.execute('SELECT user_id FROM review_staff WHERE token_hash=?',(fingerprint(supplied),)).fetchone()
                category='notes' if '/notes' in request.url.path else 'export' if '/exports' in request.url.path else 'staff' if '/staff' in request.url.path else 'datasets' if '/datasets' in request.url.path else 'alerts' if '/alert' in request.url.path else 'read_evidence'
                db.execute('INSERT INTO review_activity VALUES(?,?,?,?,?)',('activity-'+secrets.token_hex(16),actor[0] if actor else 'UNAUTHENTICATED',category,response.status_code,datetime.now(timezone.utc).isoformat()))
        return response

    def staff(request,write=False,admin=False):
        supplied=request.headers.get('authorization','').removeprefix('Bearer ')
        with store.connect() as db:row=db.execute('SELECT * FROM review_staff WHERE token_hash=?',(fingerprint(supplied),)).fetchone()
        if not row or row['expires_at'] and row['expires_at']<=datetime.now(timezone.utc).isoformat():raise HTTPException(401,'Staff review token required or expired')
        if admin and row['role']!='ADMIN' or write and row['role']=='VIEWER':raise HTTPException(403,'This review permission is not assigned')
        return dict(row,banks=json.loads(row['banks']))

    @app.get('/api/reviewer/identity')
    def identity(request:Request):
        actor=staff(request)
        return {key:actor[key] for key in ('user_id','role','banks','expires_at')}

    @app.get('/api/reviewer/semantic-results')
    def semantic_results(request:Request):
        actor=staff(request)
        if 'BOW' not in actor['banks']:raise HTTPException(403,'BOW review scope required')
        path=Path(database).parent/'local_completion/semantic_expanded_final.json'
        if not path.exists():return {'status':'NOT_RUN'}
        report=json.loads(path.read_text(encoding='utf-8'))
        return {'status':report['status'],'qualification':report['qualification'],'review_flags':report['quality_review_flags'],
                'cases':[{'case_id':r['case_id'],'question':r['user_input'],'answer':r['response'],
                          'metrics':r['ragas'],'judge':r['judge'],'measurement_file':r['measurement_file']} for r in report['rows']]}

    def permitted_rows(actor):
        with store.connect() as db:rows=db.execute('SELECT * FROM customer_reviews ORDER BY rowid DESC LIMIT 2000').fetchall()
        return [dict(r,payload=json.loads(r['payload'])) for r in rows if r['bank_id'] in actor['banks']]

    def one(actor,review_id):
        row=next((r for r in permitted_rows(actor) if r['review_id']==review_id),None)
        if not row:raise HTTPException(404,'Review is not available in your assigned scope')
        return row

    def history(review_id):
        with store.connect() as db:rows=[dict(r) for r in db.execute('SELECT * FROM review_notes WHERE review_id=? ORDER BY revision',(review_id,))]
        previous='0'*64
        for row in rows:
            expected=fingerprint({k:v for k,v in row.items() if k!='event_hash'})
            if row['previous_hash']!=previous or expected!=row['event_hash']:raise HTTPException(409,'Review history integrity check failed')
            previous=row['event_hash']
        return rows

    @app.get('/reviewer')
    def reviewer_page():return FileResponse(static/'reviewer.html')
    @app.get('/reviewer.js')
    def reviewer_script():return FileResponse(static/'reviewer.js')
    @app.get('/api/reviewer/sessions')
    def sessions(request:Request,bank_id:str|None=None,risk:str|None=None,session_ref:str|None=None,date_from:str|None=None,date_to:str|None=None,customer_ref:str|None=None):
        actor=staff(request);rows=permitted_rows(actor);items=[]
        for row in rows:
            q=row['payload']['qa'];snapshot=row['payload'].get('snapshot',{})
            if bank_id and row['bank_id']!=bank_id or risk and q['risk_level']!=risk or session_ref and session_ref not in q['session_ref']:continue
            if date_from and q['reviewed_at'][:10]<date_from or date_to and q['reviewed_at'][:10]>date_to:continue
            if customer_ref and snapshot.get('customer_ref')!=customer_ref:continue
            notes=history(row['review_id'])
            items.append({'review_id':row['review_id'],'session_ref':q['session_ref'],'turn_ref':q['turn_ref'],
                'bank_id':row['bank_id'],'risk':q['risk_level'],'decision':q['decision'],'created_at':q['reviewed_at'],
                'revision':notes[-1]['revision'] if notes else 0,'review_status':notes[-1]['status'] if notes else 'NOT_REVIEWED',
                'generation':row['generation'],'customer_ref':snapshot.get('customer_ref')})
        return {'actor':{'user_id':actor['user_id'],'role':actor['role'],'banks':actor['banks']},'items':items,'scope':'local synthetic review; no banking authority'}

    @app.get('/api/reviewer/traces/{review_id}')
    def details(review_id:str,request:Request):
        actor=staff(request);row=one(actor,review_id)
        with store.connect() as db:
            detail=db.execute('SELECT payload FROM review_details WHERE review_id=?',(review_id,)).fetchone()
            try:
                security=[json.loads(r[0]) for r in db.execute("SELECT payload FROM security_events WHERE json_extract(payload,'$.session_ref')=? AND json_extract(payload,'$.turn_ref')=?",(row['payload']['qa']['session_ref'].split(':g')[0],row['payload']['qa']['turn_ref']))]
            except Exception:security=[]
        return {'summary':row['payload'],'details':json.loads(detail[0]) if detail else {'status':'Historical detail was not captured'},
                'security_events':security,'history':history(review_id),'playback_mode':'RECORDED_ONLY_NO_TOOL_EXECUTION'}

    @app.post('/api/reviewer/notes')
    def note(body:ReviewNote,request:Request):
        actor=staff(request,write=True);one(actor,body.review_id)
        if not body.note.strip() or len(body.note)>4000:raise HTTPException(422,'Add a note of 1 to 4000 characters')
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows=history(body.review_id);revision=rows[-1]['revision'] if rows else 0
            if revision!=body.expected_revision:raise HTTPException(409,'Another reviewer updated this item; reload before saving')
            item={'event_id':'note-'+secrets.token_hex(16),'review_id':body.review_id,'revision':revision+1,
                'actor':actor['user_id'],'created_at':datetime.now(timezone.utc).isoformat(),'status':body.status,'note':masked(body.note),
                'previous_hash':rows[-1]['event_hash'] if rows else '0'*64}
            item['event_hash']=fingerprint(item)
            db.execute('INSERT INTO review_notes VALUES(?,?,?,?,?,?,?,?,?)',tuple(item.values()))
        return item

    @app.get('/api/reviewer/audits/{review_id}')
    def audits(review_id:str,request:Request):
        actor=staff(request);row=one(actor,review_id)
        with store.connect() as db:
            jobs=db.execute('SELECT job_id,status,error FROM session_audit_jobs WHERE binding=? AND generation=?',(row['binding'],row['generation'])).fetchall()
            revisions=[]
            for job in jobs:
                for r in db.execute('SELECT * FROM session_audit_reports WHERE job_id=? ORDER BY revision',(job['job_id'],)):
                    reports=[p for p in json.loads(r['payload']) if p['bank_id'] in actor['banks']]
                    trajectory=[json.loads(t[0]) for t in db.execute('SELECT payload FROM session_trajectory_reports WHERE job_id=? AND revision=? AND bank_id=?',(job['job_id'],r['revision'],row['bank_id']))]
                    revisions.append({'revision':r['revision'],'reports':reports,'trajectory':trajectory,'job_status':job['status']})
        return {'revisions':revisions,'notice':'Earlier audit revisions are retained; no banking tools are replayed'}

    @app.get('/api/reviewer/timeline/{review_id}')
    def timeline(review_id:str,request:Request):
        actor=staff(request);selected=one(actor,review_id);refs={selected['payload']['qa']['session_ref']}
        with store.connect() as db:links=[dict(r) for r in db.execute('SELECT * FROM review_session_links') if r['bank_id'] in actor['banks']]
        for _ in range(len(links)+1):
            before=len(refs)
            for link in links:
                if link['source_ref'] in refs or link['target_ref'] in refs:refs.update((link['source_ref'],link['target_ref']))
            if len(refs)==before:break
        rows=[r for r in permitted_rows(actor) if r['payload']['qa']['session_ref'] in refs]
        result=[]
        with store.connect() as db:
            for row in sorted(rows,key=lambda r:r['payload']['qa']['reviewed_at']):
                value=db.execute('SELECT payload FROM review_details WHERE review_id=?',(row['review_id'],)).fetchone()
                detail=json.loads(value[0]) if value else {}
                result.append({'review_id':row['review_id'],'session_ref':row['payload']['qa']['session_ref'],
                    'timestamp':row['payload']['qa']['reviewed_at'],'prompt':detail.get('prompt','Historical text not captured'),
                    'reply':detail.get('reply','Historical text not captured'),'delivered':detail.get('approved_for_delivery',False),
                    'decision':row['payload']['qa']['decision'],'access_state':detail.get('authorization',{}).get('access_state')})
        return {'turns':result,'mode':'RECORDED_ONLY','notice':'Authentication links preserve request continuity, never account permissions'}

    @app.post('/api/reviewer/staff')
    def create_staff(body:StaffAccount,request:Request):
        staff(request,admin=True)
        if not body.banks:raise HTTPException(422,'Assign at least one bank scope')
        access_token=secrets.token_urlsafe(32)
        with store.connect() as db:
            if db.execute('SELECT 1 FROM review_staff WHERE user_id=?',(body.user_id,)).fetchone():raise HTTPException(409,'Staff identity already exists')
            expires=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
            db.execute('INSERT INTO review_staff VALUES(?,?,?,?,?)',(fingerprint(access_token),body.user_id,body.role,json.dumps(body.banks),expires))
        return {'user_id':body.user_id,'token':access_token,'expires_at':expires,'notice':'Local demo token shown once; keep it private'}

    @app.post('/api/reviewer/staff/{user_id}/revoke')
    def revoke_staff(user_id:str,request:Request):
        staff(request,admin=True)
        if user_id=='local-demo-admin':raise HTTPException(403,'Rotate the configured bootstrap token to change administrator access')
        with store.connect() as db:
            changed=db.execute('UPDATE review_staff SET expires_at=? WHERE user_id=?',(datetime.now(timezone.utc).isoformat(),user_id)).rowcount
        if not changed:raise HTTPException(404,'Local staff identity not found')
        return {'status':'REVOKED'}

    @app.post('/api/reviewer/exports')
    def export(body:ExportRequest,request:Request):
        actor=staff(request,admin=True)
        if len(body.password)<16 or len(body.password)>200:raise HTTPException(422,'Use an export password of 16 to 200 characters')
        rows=[r for r in permitted_rows(actor) if r['payload']['qa']['session_ref']==body.session_ref]
        if not rows:raise HTTPException(404,'Session is not available')
        package={'scope':'synthetic masked review evidence','session_ref':body.session_ref,
                 'reviews':[details(r['review_id'],request) for r in rows]}
        if body.format=='CSV':
            buf=io.StringIO();writer=csv.writer(buf);writer.writerow(['review_id','decision','risk'])
            for r in rows:
                values=[r['review_id'],r['payload']['qa']['decision'],r['payload']['qa']['risk_level']]
                writer.writerow(["'"+v if v.startswith(('=','+','-','@')) else v for v in values])
            raw=buf.getvalue().encode()
        else:raw=json.dumps(package,sort_keys=True).encode()
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        salt=secrets.token_bytes(16);nonce=secrets.token_bytes(12)
        key=Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(body.password.encode())
        cipher=AESGCM(key).encrypt(nonce,raw,b'resolveguard-export-v1')
        result={'schema':'resolveguard-export-v1','format':body.format,'kdf':'scrypt-n16384-r8-p1','salt':base64.b64encode(salt).decode(),
                'nonce':base64.b64encode(nonce).decode(),'ciphertext':base64.b64encode(cipher).decode(),'plaintext_sha256':hashlib.sha256(raw).hexdigest()}
        with store.connect() as db:db.execute('INSERT INTO review_export_log VALUES(?,?,?,?,?)',
            ('export-'+secrets.token_hex(16),actor['user_id'],body.session_ref,datetime.now(timezone.utc).isoformat(),fingerprint(result)))
        return result

    @app.post('/api/reviewer/alert-rules')
    def alert_rule(body:AlertRule,request:Request):
        actor=staff(request,admin=True)
        if not 1<=body.window<=200 or body.threshold<0:raise HTTPException(422,'Choose a positive window and nonnegative threshold')
        with store.connect() as db:db.execute('INSERT INTO review_alert_rules VALUES(?,?,?) ON CONFLICT(rule_id) DO UPDATE SET payload=excluded.payload,actor=excluded.actor',
            (body.rule_id,body.model_dump_json(),actor['user_id']))
        return {'saved':True,'delivery':'LOCAL_OPERATIONS_QUEUE_ONLY'}

    @app.get('/api/reviewer/alerts')
    def alerts(request:Request):
        actor=staff(request);rows=permitted_rows(actor)
        with store.connect() as db:
            rules=[json.loads(r[0]) for r in db.execute('SELECT payload FROM review_alert_rules')]
            for rule in rules:
                window=rows[:rule['window']]
                if rule['metric']=='latency_ms':value=max((r['payload'].get('duration_ms',0) for r in window),default=0)
                elif rule['metric']=='denied_access':value=sum(any(t.get('status') in {'DENIED','BLOCKED'} for t in r['payload'].get('snapshot',{}).get('tool_decisions',[])) or any(c['name']=='AUTHORIZATION' and c['verdict']=='FAIL' for c in r['payload']['qa']['checks']) for r in window)
                elif rule['metric']=='confusion_count':value=sum(r['payload'].get('snapshot',{}).get('confusion_signal',False) for r in window)
                elif rule['metric']=='review_backlog':
                    value=0
                    for r in window:
                        notes=history(r['review_id'])
                        value+=bool(r['payload']['qa']['requires_human_review'] and (not notes or notes[-1]['status']!='COMPLETE'))
                else:value=sum(any(c['verdict']=='FAIL' for c in r['payload']['qa']['checks']) for r in window)
                if window and value>=rule['threshold']:
                    aid='alert-'+fingerprint([rule,window[0]['review_id'],actor['banks']])
                    payload={'metric':rule['metric'],'observed':value,'threshold':rule['threshold'],'review_refs':[r['review_id'] for r in window], 'banks':actor['banks']}
                    db.execute('INSERT OR IGNORE INTO review_alerts VALUES(?,?,?,?)',(aid,rule['rule_id'],'OPEN',json.dumps(payload)))
            items=[dict(r,payload=json.loads(r['payload'])) for r in db.execute('SELECT * FROM review_alerts ORDER BY rowid DESC LIMIT 100')]
        return {'items':[r for r in items if set(r['payload']['banks'])<=set(actor['banks'])]}

    @app.post('/api/reviewer/alerts/{alert_id}/acknowledge')
    def acknowledge(alert_id:str,request:Request):
        staff(request,admin=True)
        with store.connect() as db:
            changed=db.execute("UPDATE review_alerts SET status='ACKNOWLEDGED' WHERE alert_id=?",(alert_id,)).rowcount
        if not changed:raise HTTPException(404,'Alert not found')
        return {'status':'ACKNOWLEDGED'}

    from .dataset_review import install_dataset_review
    install_dataset_review(app,store,staff,static)
