"""Local, deterministic customer-response gate and durable session audit queue.

Stores fingerprints and structured findings, never chat text or account payloads.
Semantic quality remains an offline evaluation responsibility.
"""
import hashlib
import json
import re
import time
from datetime import datetime, timezone

from .contracts import Request
from .presentation import customer_cards, format_money
from .resolution_contracts import (
    CallbackCommitment, EvidenceRef, ResolutionOutcome, QAReport,
    REQUIRED_CHECKS, CRITICAL_CHECKS,
)

VERSION = 'customer-review-v2-answer-evidence'
FALLBACK = 'I could not safely confirm those details. Please retry your original request. If you already sent a report, do not start a duplicate report.'


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class CustomerReview:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS customer_reviews (
                review_id TEXT PRIMARY KEY, binding TEXT NOT NULL, generation INTEGER NOT NULL,
                bank_id TEXT NOT NULL, payload TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS review_sessions (
                binding TEXT PRIMARY KEY, generation INTEGER NOT NULL DEFAULT 0)''')
            db.execute('''CREATE TABLE IF NOT EXISTS session_audit_jobs (
                job_id TEXT PRIMARY KEY, binding TEXT NOT NULL, generation INTEGER NOT NULL,
                trigger TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                result TEXT, error TEXT)''')
            db.execute('CREATE TABLE IF NOT EXISTS review_details (review_id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS review_workflow (binding TEXT,request_ref TEXT,payload TEXT,PRIMARY KEY(binding,request_ref))')
            db.execute('CREATE TABLE IF NOT EXISTS review_turn_epochs (binding TEXT,request_ref TEXT,generation INTEGER,status TEXT,PRIMARY KEY(binding,request_ref))')
            if 'bank_id' not in {r['name'] for r in db.execute('PRAGMA table_info(review_turn_epochs)')}:db.execute('ALTER TABLE review_turn_epochs ADD COLUMN bank_id TEXT')
            db.execute('CREATE TABLE IF NOT EXISTS session_audit_reports (job_id TEXT,revision INTEGER,input_hash TEXT,payload TEXT,PRIMARY KEY(job_id,revision))')
            db.execute('CREATE TABLE IF NOT EXISTS session_trajectory_reports (job_id TEXT,revision INTEGER,bank_id TEXT,payload TEXT,PRIMARY KEY(job_id,revision,bank_id))')
            db.execute('CREATE TABLE IF NOT EXISTS review_session_links (source_ref TEXT,target_ref TEXT,bank_id TEXT,reason TEXT,PRIMARY KEY(source_ref,target_ref))')
            for operation in ('UPDATE','DELETE'):
                db.execute(f"CREATE TRIGGER IF NOT EXISTS audit_reports_no_{operation.lower()} BEFORE {operation} ON session_audit_reports BEGIN SELECT RAISE(ABORT,'Audit reports are append-only'); END")
            columns={r['name'] for r in db.execute('PRAGMA table_info(session_audit_jobs)')}
            if 'input_fingerprint' not in columns:db.execute('ALTER TABLE session_audit_jobs ADD COLUMN input_fingerprint TEXT')
            if 'audit_revision' not in columns:db.execute('ALTER TABLE session_audit_jobs ADD COLUMN audit_revision INTEGER NOT NULL DEFAULT 0')
            db.execute("INSERT OR IGNORE INTO session_audit_reports SELECT job_id,0,'LEGACY_UNFINGERPRINTED',result FROM session_audit_jobs WHERE result IS NOT NULL AND audit_revision=0 AND input_fingerprint IS NULL")

    def start_turn(self,binding,request_key,bank_id='LEGACY_DEMO'):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO review_sessions(binding) VALUES(?)',(binding,))
            generation=db.execute('SELECT generation FROM review_sessions WHERE binding=?',(binding,)).fetchone()[0]
            db.execute('INSERT OR IGNORE INTO review_turn_epochs(binding,request_ref,generation,status,bank_id) VALUES(?,?,?,?,?)',(binding,fingerprint(request_key),generation,'STARTED',bank_id))
            return db.execute('SELECT generation FROM review_turn_epochs WHERE binding=? AND request_ref=?',(binding,fingerprint(request_key))).fetchone()[0]

    def fail_turn(self,binding,request_key):
        with self.store.connect() as db:db.execute("UPDATE review_turn_epochs SET status='FAILED' WHERE binding=? AND request_ref=? AND status='STARTED'",(binding,fingerprint(request_key)))

    def capture_workflow(self,binding,request_key,result):
        from .reviewer import masked
        payload=masked({'trace':result.get('trace'), 'tools':result.get('tools',[]),
                        'response_state':result.get('response_state'),'bank_id':result.get('bank_id')})
        with self.store.connect() as db:
            db.execute('INSERT OR REPLACE INTO review_workflow VALUES(?,?,?)',(binding,fingerprint(request_key),json.dumps(payload)))
        if result.get('trace'):
            from pathlib import Path
            from .monitoring import record_observation
            try:
                metrics=dict(result,execution_mode=result.get('execution_mode','MOCK'),journey_scope='WORKFLOW',
                    errors=list(result.get('errors',[]))+['TOOL_OUTCOME_UNKNOWN' for t in result.get('tools',[]) if t.get('status')=='UNKNOWN'])
                record_observation(metrics,str(Path(self.store.path).parent/'operations.sqlite3'))
            except Exception:
                import logging
                logging.getLogger(__name__).warning('REVIEW_WORKFLOW_OBSERVATION_FAILED')

    def append_generation(self,binding,request_key,trace,metadata):
        """Append generation evidence without replacing retrieval/tool history."""
        from .telemetry import sanitize
        with self.store.connect() as db:
            row=db.execute('SELECT payload FROM review_workflow WHERE binding=? AND request_ref=?',(binding,fingerprint(request_key))).fetchone()
            payload=json.loads(row[0]) if row else {}
            if not payload.get('trace'):payload['trace']=trace
            if payload['trace']['trace_id']!=trace['trace_id']:
                from uuid import uuid4
                spans=payload['trace']['spans']+trace['spans']
                if spans:
                    # A new enclosing span avoids nesting generation beneath an
                    # already-finished retrieval call or inventing its duration.
                    ident=str(uuid4())
                    start=min(s['start_time'] for s in spans)
                    end=max(s['end_time'] for s in spans)
                    for span in spans:
                        if span['parent_id'] is None:span['parent_id']=ident
                    root={'id':ident,'parent_id':None,'name':'customer.response.pipeline','run_type':'chain',
                          'inputs':{},'outputs':{},'start_time':start,'end_time':end,'error':None,
                          'latency_ms':round((datetime.fromisoformat(end)-datetime.fromisoformat(start)).total_seconds()*1000,3)}
                    payload['trace']['spans']=[root]+spans
            payload['generation']=metadata
            db.execute('INSERT OR REPLACE INTO review_workflow VALUES(?,?,?)',(binding,fingerprint(request_key),json.dumps(sanitize(payload))))
        if metadata:
            from pathlib import Path
            from .monitoring import record_observation
            try:
                record_observation({'trace':trace,'generation':metadata,
                    'execution_mode':'NEBIUS_GENERATION','journey_scope':'GENERATION',
                    'input_tokens':metadata.get('input_tokens'),'output_tokens':metadata.get('output_tokens'),
                    'model_cost_usd':None,'errors':[metadata['failure_code']] if metadata.get('failure_code') else []},
                    str(Path(self.store.path).parent/'operations.sqlite3'))
            except Exception:
                import logging
                logging.getLogger(__name__).warning('GENERATION_OBSERVATION_FAILED')

    def attach_request_trace(self, binding, request_key, bank_id, request_trace):
        """Join actual dispatch timing to existing steps; never invent tool spans."""
        from .reviewer import masked
        with self.store.connect() as db:
            row=db.execute('SELECT payload FROM review_workflow WHERE binding=? AND request_ref=?',
                           (binding,fingerprint(request_key))).fetchone()
            payload=json.loads(row[0]) if row else {'bank_id':bank_id,'tools':[]}
            existing=payload.get('trace')
            # Retried turns retain the original execution evidence and append a
            # distinct dispatch span. Actual timestamps and parentage survive.
            spans=request_trace['spans']
            if existing and existing.get('spans'):
                parent=spans[0]['id']
                for span in existing['spans']:
                    if span['parent_id'] is None:span['parent_id']=parent
                spans.extend(existing['spans'])
                # A cached retry can contain older evidence; bound the enclosing
                # dispatch to its actual duration, with historical roots siblings.
                for span in existing['spans']:
                    if span.get('start_time','') < spans[0]['start_time'] and span['parent_id']==parent:
                        span['parent_id']=None
                request_trace['metadata']['prior_workflow_metadata']=existing.get('metadata',{})
            payload['trace']=request_trace
            db.execute('INSERT OR REPLACE INTO review_workflow VALUES(?,?,?)',
                       (binding,fingerprint(request_key),json.dumps(masked(payload))))

    def close(self, binding, trigger='SESSION_ENDED', connection=None):
        """Enqueue an end event atomically with the caller's session reset."""
        from contextlib import nullcontext
        with self.store.connect() if connection is None else nullcontext(connection) as db:
            db.execute('INSERT OR IGNORE INTO review_sessions(binding) VALUES(?)', (binding,))
            generation = db.execute('SELECT generation FROM review_sessions WHERE binding=?', (binding,)).fetchone()[0]
            exists = db.execute('SELECT 1 FROM customer_reviews WHERE binding=? AND generation=?', (binding, generation)).fetchone() or db.execute('SELECT 1 FROM review_turn_epochs WHERE binding=? AND generation=?',(binding,generation)).fetchone()
            if exists:
                job = 'audit-' + fingerprint([binding, generation])
                db.execute('INSERT OR IGNORE INTO session_audit_jobs(job_id,binding,generation,trigger,status) VALUES(?,?,?,?,?)',
                           (job, binding, generation, trigger, 'PENDING'))
            db.execute('UPDATE review_sessions SET generation=generation+1 WHERE binding=?', (binding,))

    def gate(self, candidate, *, binding, sid, backend, bank_id, request_key, access_state, message='', action='message'):
        """Inspect the final payload, then review a stripped fallback if it fails."""
        approved = self._review(candidate, binding, sid, backend, bank_id, request_key, access_state, message=message, action=action)
        if approved:
            return candidate
        fallback = {'response': FALLBACK, 'response_state': 'REVIEW_REQUIRED',
                    'cards': [], 'source_details': [], 'data_scope': 'PUBLIC', 'auth_required': False,
                    'bank_id': bank_id}
        if not self._review(fallback, binding, sid, backend, bank_id, request_key, access_state, fallback=True):
            raise RuntimeError('Safe fallback could not be approved')
        return fallback

    def _review(self, candidate, binding, sid, backend, bank_id, request_key, access_state, fallback=False, message='', action='message'):
        started = time.monotonic()
        generation=self.start_turn(binding,request_key,bank_id)
        failed = set()
        if candidate.get('emergency'):
            from .fraud_triage import verify_emergency
            if not verify_emergency(candidate,backend,sid,request_key):failed.add('ACTION_INTEGRITY')
        req = Request(message='Verify customer response evidence', request_key=request_key,
                      session_id=sid, bank_id=bank_id)
        snapshot = {'bank': bank_id, 'access': access_state, 'as_of': backend.now[:10],
                    'version': VERSION, 'evidence': [], 'sources': []}
        owner=backend.owner(req)
        snapshot['customer_ref']='customer-'+fingerprint(owner) if owner else None
        with self.store.connect() as db:
            captured=db.execute('SELECT payload FROM review_workflow WHERE binding=? AND request_ref=?',(binding,fingerprint(request_key))).fetchone()
        captured=json.loads(captured[0]) if captured else {}
        snapshot['tool_decisions']=captured.get('tools',[])
        snapshot['workflow_trace_ref']=(captured.get('trace') or {}).get('trace_id')
        snapshot['confusion_signal']=bool(re.search(r'\b(still confused|did not help|still need help|not fixed)\b',message,re.I))
        references = []
        for kind in ('report', 'case', 'handoff'):
            value = candidate.get(kind) or {}
            if value.get('status') != 'OK':
                continue
            with self.store.connect() as db:
                row = db.execute('SELECT owner,result,payload FROM events WHERE kind=? AND event_id=?',
                                 (kind, value.get('event_id'))).fetchone()
            actual = json.loads(row['result']) if row else None
            # All claimed fields must match a durable event owned by this principal.
            payload = json.loads(row['payload']) if row else {}
            bank_matches = (backend.case_status(req.model_copy(update={'case_id': value.get('event_id')})).get('status') == 'OK') if row and kind == 'case' else payload.get('bank_id', 'LEGACY_DEMO') == bank_id
            valid = row and row['owner'] == backend.owner(req) and bank_matches and all(
                key == 'replayed' or actual.get(key) == item for key, item in value.items())
            if not valid:
                failed.add('ACTION_INTEGRITY')
                continue
            event_kind = {'report': 'REPORT_CAPTURED', 'case': 'CASE_CREATED', 'handoff': 'HANDOFF_ACKNOWLEDGED'}[kind]
            if kind == 'handoff' and actual.get('handoff_status') != 'ACKNOWLEDGED':
                continue
            references.append(EvidenceRef(kind='BACKEND_EVENT', reference=value['event_id'],
                              version=VERSION, event_kind=event_kind, resource_ref=value['event_id']))
            snapshot['evidence'].append(fingerprint(actual))

        from .intake_signals import asserted_payment_error
        if not fallback and action == 'message' and asserted_payment_error(message) and not candidate.get('report'):
            failed.add('ERROR_REPORT_PRESERVATION')

        cards = candidate.get('cards', [])
        authorized_records=[]
        for card in cards:
            if access_state != 'VERIFIED' or bank_id != backend.bank_id:
                failed.add('AUTHORIZATION')
                continue
            if card.get('kind') == 'transaction':
                result = backend.transaction(req, card.get('reference', 'missing'))
                record = dict(result.get('data') or {}, kind='transaction')
            elif card.get('kind') == 'case':
                result = backend.case_status(req.model_copy(update={'case_id': card.get('reference')}))
                record = dict(result.get('data') or {}, kind='case')
            else:
                failed.add('TOOL_CORRECTNESS')
                continue
            if result.get('status') != 'OK':
                failed.add('AUTHORIZATION')
            else:
                authorized_records.append(record)
                expected = customer_cards({'records': [record], 'bank_id': bank_id})[0]
                # Creation cards have different labels but must share authoritative ID/status.
                fields = ('reference', 'status') if card.get('title') == 'Support request created' else expected.keys()
                if any(card.get(key) != expected.get(key) for key in fields):
                    failed.add('TOOL_CORRECTNESS')
                snapshot['evidence'].append(fingerprint(result))

        if candidate.get('notice',{}).get('status')=='OK' or candidate.get('response_state')=='VERIFIED_NOTICE_STATE':
            case_ref=next((r['case_id'] for r in authorized_records if r.get('kind')=='case'),None)
            actual=backend.notice_status(req.model_copy(update={'case_id':case_ref})) if case_ref else None
            if actual is None or actual.get('status')!='OK' or candidate.get('notice')!=actual:failed.add('ACTION_INTEGRITY')
        if candidate.get('callback'):
            from .demo_operations import DemoOperations
            href=(candidate.get('handoff') or {}).get('event_id')
            actual=DemoOperations(self.store).commitment(href).model_dump(mode='json') if href else None
            if access_state!='VERIFIED' or candidate['callback']!=actual:failed.add('ACTION_INTEGRITY')

        if candidate.get('selected_transaction_ids') and access_state != 'VERIFIED':
            failed.add('AUTHORIZATION')
        if candidate.get('source_details'):
            snapshot['sources'] = [{'reference': s.get('reference'), 'version': s.get('version'),
                                    'content_hash': fingerprint(s)} for s in candidate['source_details']]
            if bank_id == 'BOW':
                from .bow_knowledge import BowKnowledge
                knowledge = BowKnowledge()
                for source in candidate['source_details']:
                    chunk = knowledge.chunk_map.get(source.get('reference'))
                    # Catalog comparisons are checked by their source-specific builder.
                    if source.get('reference', '').startswith('BOW-CATALOG:'):
                        product = knowledge.product_map.get(source.get('product_id'))
                        linked = [c for c in knowledge.retrieve('BOW', source.get('product_id'), backend.now[:10], allow_demo=True, limit=100)
                                  if c['topic'] == 'product_terms' and c['chunk_id'] in {s.get('reference') for s in candidate['source_details']}]
                        if not product or not linked or source['reference'] != 'BOW-CATALOG:'+product['product_id']+':'+knowledge.version or source.get('content_hash') != fingerprint(product) or source.get('version') != knowledge.version:
                            failed.add('GROUNDING')
                        elif source.get('bank_id')!='BOW' or source.get('access_level')!='PUBLIC' or source.get('approval_status')!='SYNTHETIC_APPROVED_FOR_TEST_ONLY' or source.get('effective_date')!=product['effective_date'] or product['effective_date']>backend.now[:10]:
                            failed.add('GROUNDING')
                        elif source.get('summary') not in {knowledge.product_summary(product),('Annual card fee' if product['product_type'] in {'debit_card', 'credit_card'} else 'Monthly maintenance fee')+': '+format_money(product['monthly_fee_cents_or_annual_card_fee_cents'])+'.'}:
                            failed.add('GROUNDING')
                        elif 'record' in source and source['record']!=product:
                            failed.add('GROUNDING')
                        elif source.get('expires_on')!=(min(c['expires_on'] for c in linked if c.get('expires_on')) if any(c.get('expires_on') for c in linked) else None):
                            failed.add('GROUNDING')
                    elif not chunk or knowledge.sources([chunk['chunk_id']])[0] != source:
                        failed.add('GROUNDING')
                    elif any(row['bank_id'] != 'BOW' or row['access_level'] != 'PUBLIC' or row['approval_status'] != 'SYNTHETIC_APPROVED_FOR_TEST_ONLY'
                             for row in (chunk, knowledge.policy_map[chunk['doc_id']])):
                        failed.add('GROUNDING')
                    elif chunk['effective_date'] > backend.now[:10] or chunk['expires_on'] and backend.now[:10] >= chunk['expires_on']:
                        failed.add('GROUNDING')
            else:
                from .retrieval import PolicyIndex
                chunks = {c['chunk_id']: c for c in PolicyIndex().chunks}
                for source in candidate['source_details']:
                    if source.get('url'):
                        from . import public_support
                        valid_rates = []
                        for raw in json.loads(public_support.RATES.read_text(encoding='utf-8'))['published_rates']:
                            try:
                                rate = public_support.PublishedRate.model_validate(raw)
                            except ValueError:
                                continue
                            answer = public_support._public_evidence_answer('savings interest rate' if 'savings' in rate.product.lower() else 'checking interest rate', backend.now[:10], product_name=rate.product)
                            valid_rates.extend(answer['source_details'])
                        if source not in valid_rates:
                            failed.add('GROUNDING')
                        continue
                    c = chunks.get(source.get('reference'))
                    if not c or c['approval_status'] != 'APPROVED_FOR_SYNTHETIC_TEST' or c['version'] != source.get('version') or c['effective_date'] > backend.now[:10] or c['expires_at'] and backend.now[:10] >= c['expires_at']:
                        failed.add('GROUNDING')
            snapshot['evidence'].append(fingerprint(candidate['source_details']))

        # The UI must never display full credentials or raw authorization objects.
        encoded = json.dumps(candidate)
        # A committed opaque reference can be all digits by chance. Exempt only
        # complete IDs backed by the ownership/evidence checks above; a standalone
        # PAN (including the same digits elsewhere) remains blocked.
        privacy_encoded=encoded
        verified_refs=[r.reference for r in references]
        if candidate.get('emergency') and 'ACTION_INTEGRITY' not in failed:
            if candidate['emergency']['card_lock'].get('status')=='OK':
                verified_refs.append(candidate['emergency']['card_lock'].get('operation_id'))
            if candidate['emergency']['dispute'].get('status')=='OK':
                verified_refs.append(candidate['emergency']['dispute'].get('reference'))
        for reference in verified_refs:
            if isinstance(reference,str) and re.fullmatch(r'DEMO-(?:REPORT|HANDOFF|CASE|LOCK|FRAUD)-[0-9a-f]{16}',reference):
                privacy_encoded=privacy_encoded.replace(reference,'[VERIFIED_REFERENCE]')
        if re.search(r'\b\d{13,19}\b', privacy_encoded) or any(key in candidate for key in ('model_context', 'authorization', 'system_prompt')):
            failed.add('PRIVACY')
        if re.search(r'\b(?:your (?:refund|investigation|callback) (?:is|has been) (?:confirmed|started|completed)|we will call you (?:within|at)|your (?:issue|problem) is resolved)\b', candidate.get('response', ''), re.I):
            failed.add('ACTION_INTEGRITY')
        if not isinstance(candidate.get('response'), str) or not candidate['response'].strip():
            failed.add('CUSTOMER_EXPERIENCE')
        from .answer_evidence import verify_answer
        answer_failures = verify_answer(candidate, bank_id, backend.now[:10], message,authorized_records)
        if answer_failures:
            failed.add('GROUNDING')
        snapshot['answer_checks'] = {'version':'controlled-answer-v1','failures':answer_failures}
        ref = 'snapshot-' + fingerprint(snapshot)
        evidence = (EvidenceRef(kind='RUNTIME_CHECK', reference=ref, version=VERSION),)
        candidate_ref = 'candidate-' + fingerprint(candidate)
        report_id = 'qa-' + fingerprint([binding,generation,request_key,candidate_ref,ref])
        # Deterministic checks describe bounded invariants, not semantic proof.
        checks = tuple(dict(name=name, verdict='FAIL' if name in failed else 'NOT_EVALUABLE' if name == 'INTENT_ROUTING' else 'PASS',
                            severity='CRITICAL' if name in CRITICAL_CHECKS else 'MAJOR',
                            method='DETERMINISTIC', reason_code='INVARIANT_FAILED' if name in failed else 'BOUNDED_INVARIANT_CHECKED',
                            explanation='No independent intent label is available online.' if name == 'INTENT_ROUTING' else 'Local backend, source and response-boundary invariants; not an independent semantic assessment.',
                            evidence=evidence) for name in sorted(REQUIRED_CHECKS))
        critical = bool(failed & CRITICAL_CHECKS)
        report = QAReport(bank_id=bank_id, report_id=report_id, session_ref='session-' + binding+':g'+str(generation),
                          turn_ref='turn-' + fingerprint(request_key), stage='PRE_SEND', trigger='DRAFT_READY',
                          reviewed_at=datetime.now(timezone.utc).isoformat(), rubric_version=VERSION,
                          candidate_response_ref=candidate_ref, context_snapshot_ref=ref, checks=checks,
                          decision='SAFE_FALLBACK' if failed else 'APPROVE',
                          risk_level='CRITICAL' if critical else 'MEDIUM',
                          requires_human_review=critical or candidate.get('response_state')=='PRIVACY_INCIDENT')
        resolution = None
        if candidate.get('report') or candidate.get('case') or candidate.get('handoff') or candidate.get('auth_required') or candidate.get('response_state') in {'SUBMISSION_UNCONFIRMED', 'SERVICE_UNAVAILABLE'} or re.search(r'\b(unresolved|not resolved|still wrong|still need help|still not fixed|human|call me)\b', message, re.I):
            handoff = next((e for e in references if e.event_kind == 'HANDOFF_ACKNOWLEDGED'), None)
            case = next((e for e in references if e.event_kind == 'CASE_CREATED'), None)
            from .demo_operations import DemoOperations
            operations=DemoOperations(self.store)
            priority=operations.assign(backend,req,handoff.resource_ref,message) if handoff else operations.assign_case(backend,req,case.resource_ref) if case else None
            commitment=operations.commitment(handoff.resource_ref) if handoff else CallbackCommitment(status='UNCONFIRMED')
            resolution = ResolutionOutcome(bank_id=bank_id, issue_state='UNRESOLVED',
                next_step_state='CASE_CONFIRMED' if case else 'HANDOFF_ACKNOWLEDGED' if handoff else 'UNKNOWN',
                next_action='CHECK_CASE' if case else 'WAIT_FOR_UPDATE' if handoff else 'REQUEST_CUSTOMER_INPUT',
                case_ref=case.resource_ref if case else None, handoff_ref=handoff.resource_ref if handoff else None,
                next_owner=candidate['handoff'].get('queue') if handoff else priority.queue_id if priority else None,
                priority=priority,callback=commitment, evidence=tuple(references))
        payload = {'qa': report.model_dump(mode='json'), 'resolution': resolution.model_dump(mode='json') if resolution else None,
                   'fallback': fallback, 'snapshot': snapshot,
                   'duration_ms': round((time.monotonic()-started)*1000, 3)}
        from .review_flow import ReviewCheckpoint, next_review_stage
        checkpoint = ReviewCheckpoint(bank_id=bank_id, stage='PRE_SEND_QA', session_ref=report.session_ref,
            turn_ref=report.turn_ref, issue_state='UNRESOLVED' if resolution else 'UNKNOWN',
            candidate_response_ref=candidate_ref, context_snapshot_ref=ref, qa=report, fallback_used=fallback)
        payload['next_stage'] = next_review_stage(checkpoint)
        with self.store.connect() as db:
            db.execute('INSERT OR IGNORE INTO review_sessions(binding) VALUES(?)', (binding,))
            db.execute('INSERT OR IGNORE INTO customer_reviews VALUES(?,?,?,?,?)',
                       (report_id+'-'+str(generation), binding, generation, bank_id, json.dumps(payload)))
            from .reviewer import masked
            workflow=db.execute('SELECT payload FROM review_workflow WHERE binding=? AND request_ref=?',(binding,fingerprint(request_key))).fetchone()
            detail={'prompt':masked(message),'reply':masked(candidate.get('response','')),
                    'workflow':json.loads(workflow[0]) if workflow else {'status':'Direct web path; see access/source/receipt checks'},
                    'authorization':{'access_state':access_state,'bank_id':bank_id},'generation':generation,
                    'candidate_ref':candidate_ref,'presentation_version':candidate.get('presentation_version'),
                    'approved_for_delivery':not failed,'scope':'MASKED_SYNTHETIC_LOCAL_REVIEW'}
            db.execute('INSERT OR IGNORE INTO review_details VALUES(?,?)',(report_id+'-'+str(generation),json.dumps(detail)))
            db.execute("UPDATE review_turn_epochs SET status='COMPLETED' WHERE binding=? AND request_ref=?",(binding,fingerprint(request_key)))
        return payload['next_stage'] == 'DELIVER_RESPONSE'

    def process_pending(self):
        """Idempotent local worker; failed jobs remain available for retry."""
        with self.store.connect() as db:
            jobs = db.execute('SELECT * FROM session_audit_jobs').fetchall()
        for job in jobs:
            try:
                with self.store.connect() as db:
                    rows = db.execute('SELECT payload FROM customer_reviews WHERE binding=? AND generation=? ORDER BY rowid',
                                      (job['binding'], job['generation'])).fetchall()
                    turns=[dict(r) for r in db.execute('SELECT status,bank_id FROM review_turn_epochs WHERE binding=? AND generation=?',(job['binding'],job['generation']))]
                    states=[r['status'] for r in turns]
                    if 'STARTED' in states:continue
                    reports = [json.loads(row['payload'])['qa'] for row in rows]
                    source_hash=fingerprint([reports,turns])
                    if job['status']=='DONE' and job['input_fingerprint']==source_hash:continue
                    revision=job['audit_revision']+1
                    audits = []
                    banks={r['bank_id'] for r in reports}|{r['bank_id'] for r in turns if r['status']=='FAILED' and r['bank_id'] in {'BOW','LEGACY_DEMO'}}
                    for bank in sorted(banks):
                        selected = [r for r in reports if r['bank_id'] == bank]
                        from .session_quality import inspect_session
                        trajectory=inspect_session(self.store,job['binding'],job['generation'],bank)
                        checks = []
                        for name in sorted(REQUIRED_CHECKS):
                            items = [c for r in selected for c in r['checks'] if c['name'] == name]
                            if not items:
                                items=[{'name':name,'verdict':'NOT_EVALUABLE','severity':'CRITICAL' if name in CRITICAL_CHECKS else 'MAJOR','method':'DETERMINISTIC',
                                    'reason_code':'TURN_FAILED_BEFORE_REVIEW','explanation':'A failed turn has no complete response evidence.',
                                    'evidence':[EvidenceRef(kind='RUNTIME_CHECK',reference=job['job_id'],version=VERSION).model_dump(mode='json')]}]
                            checks.append(next((c for c in items if c['verdict'] == 'FAIL'),next((c for c in items if c['verdict']=='NOT_EVALUABLE'),items[-1])))
                        for finding in trajectory['failures']:
                            checks=[dict(c,verdict=finding.get('verdict','FAIL'),reason_code=finding['reason'],explanation='Independent post-session evidence check found missing or inconsistent evidence.') if c['name']==finding['check'] else c for c in checks]
                        if 'FAILED' in states:
                            checks=[dict(c,verdict='NOT_EVALUABLE',reason_code='TURN_FAILED_BEFORE_REVIEW',explanation='A failed turn has no complete response evidence.') if c['name'] in CRITICAL_CHECKS and c['verdict']!='FAIL' else c for c in checks]
                        critical = any(c['verdict'] == 'FAIL' and c['name'] in CRITICAL_CHECKS for c in checks)
                        critical_unknown=any(c['verdict']=='NOT_EVALUABLE' and c['name'] in CRITICAL_CHECKS for c in checks)
                        failed = any(c['verdict'] == 'FAIL' for c in checks)
                        unknown = any(c['verdict'] != 'PASS' for c in checks)
                        manual_required=failed or critical_unknown or any(r['requires_human_review'] for r in selected)
                        audit = QAReport(bank_id=bank, report_id=job['job_id']+'-r'+str(revision)+'-'+bank,
                            session_ref='session-'+job['binding']+':g'+str(job['generation']), stage='POST_SESSION', trigger=job['trigger'],
                            reviewed_at=datetime.now(timezone.utc).isoformat(), rubric_version=VERSION, checks=tuple(checks),
                            decision='ESCALATE' if critical else 'NEEDS_REVIEW' if manual_required else 'RECORD',
                            risk_level='CRITICAL' if critical else 'HIGH' if critical_unknown else 'MEDIUM' if unknown else 'LOW', requires_human_review=manual_required)
                        audits.append(audit.model_dump(mode='json'))
                        db.execute('INSERT OR IGNORE INTO session_trajectory_reports VALUES(?,?,?,?)',(job['job_id'],revision,bank,json.dumps(trajectory)))
                    db.execute('INSERT OR IGNORE INTO session_audit_reports VALUES(?,?,?,?)',(job['job_id'],revision,source_hash,json.dumps(audits)))
                    db.execute("UPDATE session_audit_jobs SET status='DONE',attempts=attempts+1,result=?,error=NULL,input_fingerprint=?,audit_revision=? WHERE job_id=?",
                               (json.dumps(audits),source_hash,revision,job['job_id']))
            except Exception as exc:
                with self.store.connect() as db:
                    db.execute("UPDATE session_audit_jobs SET status='FAILED',attempts=attempts+1,error=? WHERE job_id=? AND status!='DONE'",
                               (type(exc).__name__, job['job_id']))

    def expire_idle(self, idle_seconds=1800):
        """Explicit local inactivity boundary; a request timeout is never an end."""
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            sessions = db.execute('''SELECT s.binding,s.generation,r.payload FROM review_sessions s
                JOIN customer_reviews r ON r.binding=s.binding AND r.generation=s.generation
                WHERE r.rowid=(SELECT MAX(rowid) FROM customer_reviews WHERE binding=s.binding AND generation=s.generation)''').fetchall()
            now = datetime.now(timezone.utc)
            for row in sessions:
                timestamp = json.loads(row['payload'])['qa']['reviewed_at']
                if (now-datetime.fromisoformat(timestamp)).total_seconds() >= idle_seconds:
                    self.close(row['binding'], 'IDLE_TIMEOUT', connection=db)


if __name__ == '__main__':
    import argparse
    from .storage import Store
    parser = argparse.ArgumentParser(description='Retry local customer-session audits; no network calls.')
    parser.add_argument('--database', default='artifacts/web.sqlite3')
    args = parser.parse_args()
    worker = CustomerReview(Store(args.database))
    worker.expire_idle()
    worker.process_pending()
