"""Synthetic backend authority, extending the supplied read-only fixture APIs."""
import json
from pathlib import Path
from resolveguard_synthetic_v04.resolveguard_tools import FixtureBank
from .contracts import Faults, Request, validated_result
from .storage import Store

TX_FIELDS = frozenset({'transaction_id', 'posted_on', 'merchant', 'amount_cents', 'currency', 'status'})
CASE_FIELDS = frozenset({'case_id', 'case_type', 'status', 'created_at', 'owner_queue'})
CASE_WRITE_SERVICES = frozenset({'resolveguard-agent'})  # Local synthetic operation policy.


class Backend:
    bank_id='LEGACY_DEMO'
    def __init__(self, store: Store, faults=None, now='2026-10-30T13:00:00Z'):
        self.store = store
        self.faults = Faults.model_validate(faults) if faults is not None else Faults()
        self.bank = FixtureBank(now=now)
        self.now = now
        extra = json.loads((Path(__file__).resolve().parents[1]/'data/supplemental_fixtures.json').read_text())
        for name in ('sessions', 'transactions', 'cases', 'delegations'):
            getattr(self.bank, name).extend(extra[name])
        self.assurance_events = extra['assurance_events']

    def owner(self, request):
        # Public intake permits known unauthenticated/expired synthetic sessions.
        # Anonymous sessions in a real app must have independent unguessable bindings.
        row = next((x for x in self.bank.sessions if x['session_id'] == request.session_id), None)
        return row['principal_id'] if row else None

    def service(self, request, tool):
        if tool=='create_support_case' and request.service_id not in CASE_WRITE_SERVICES:return False
        aliases = {'record_issue_intake': 'record_error_report', 'lookup_report': 'record_error_report',
                   'create_support_case': 'check_authority', 'lookup_request': 'check_authority',
                   'reconcile_handoff': 'handoff_to_human'}
        return self.bank._check_agent(request.service_id, aliases.get(tool, tool))

    def allowed_account(self, request, account_id, action='TRANSACTION_READ'):
        if request.bank_id!=self.bank_id:return False
        if not self.service(request, 'check_authority'):
            return False
        if action=='CASE_CREATE' and not self.service(request,'create_support_case'):return False
        if self.assurance_error(request):
            return False
        return self.bank._permit(request.session_id, account_id, action)[0]

    def assurance_error(self, request):
        raw=next((r for r in self.bank.sessions if r['session_id']==request.session_id),None)
        if raw and raw.get('authentication_failed'):return 'AUTHENTICATION_FAILED'
        session = self.bank._session(request.session_id)
        if not session:
            return 'AUTHENTICATION_REQUIRED'
        if session.get('requires_step_up') and not any(
            e['session_id'] == request.session_id and e['principal_id'] == session['principal_id']
            and e['verified'] and self.bank._after(e['expires_at']) for e in self.assurance_events
        ):
            return 'STEP_UP_REQUIRED'
        return None

    @validated_result('notice_read')
    def notice_status(self,request):
        """Receipt state from a scoped durable report, never inferred from a case."""
        case=self.case_status(request)
        if case.get('status')!='OK':return {'status':'DENIED','reason_code':'NOTICE_SCOPE_NOT_AUTHORIZED'}
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS demo_notice_links (case_id TEXT PRIMARY KEY,report_id TEXT)')
            link=db.execute('SELECT report_id FROM demo_notice_links WHERE case_id=?',(request.case_id,)).fetchone()
            row=db.execute("SELECT owner,result FROM events WHERE kind='report' AND event_id=?",(link[0],)).fetchone() if link else None
        if not row or row['owner']!=self.owner(request):return {'status':'UNKNOWN','reason_code':'NO_CONFIRMED_NOTICE_RECORD'}
        result=json.loads(row['result'])
        return {'status':'OK','report_ref':result['event_id'],'report_capture_status':result['report_capture_status'],
                'regulatory_notice_status':result['regulatory_notice_status'],'investigation_status':result['investigation_status']}

    @validated_result('transaction')
    def transaction(self, request, transaction_id):
        if request.bank_id!=self.bank_id:
            return {'status':'DENIED','reason_code':'BANK_NOT_CONNECTED','data':None}
        error = self.assurance_error(request)
        if error:
            return {'status': 'DENIED', 'reason_code': error, 'data': None}
        result = self.bank.get_transaction(request.session_id, transaction_id, request.service_id)
        if result['status'] == 'OK' and self.faults.transaction_timeout:
            return {'status': 'UNKNOWN', 'reason_code': 'BACKEND_UNAVAILABLE', 'data': None}
        return result

    @validated_result('case_read')
    def case_status(self, request):
        if request.bank_id!=self.bank_id:
            return {'status':'DENIED','reason_code':'BANK_NOT_CONNECTED','data':None}
        error = self.assurance_error(request)
        if error:
            return {'status': 'DENIED', 'reason_code': error, 'data': None}
        if self.faults.case_state_conflict:
            return {'status':'UNKNOWN','reason_code':'CASE_STATE_CONFLICT','data':None}
        if not self.service(request, 'get_case_status'):
            return {'status': 'DENIED', 'reason_code': 'SERVICE_NOT_AUTHORIZED', 'data': None}
        stored = self.store.find_event('case', request.case_id)
        if stored:
            account = stored['payload']['account_id']
            allowed = self.bank._permit(request.session_id, account, 'CASE_STATUS', request.case_id)[0]
            if not allowed:
                return {'status': 'DENIED', 'reason_code': 'RESOURCE_NOT_AUTHORIZED', 'data': None}
            result = stored['result']
            return {'status': 'OK', 'reason_code': 'ALLOW', 'data': {
                'case_id': result['event_id'], 'case_type': 'SUPPORT_REQUEST',
                'status': result['case_status'], 'created_at': result['committed_at'],
                'owner_queue': 'CUSTOMER_SUPPORT'}}
        result = self.bank.get_case_status(request.session_id, request.case_id, request.service_id)
        return result

    @validated_result('report')
    def capture(self, request):
        owner = self.owner(request)
        if not owner or not self.service(request, 'record_issue_intake'):
            return {'status': 'DENIED', 'reason_code': 'INTAKE_NOT_AUTHORIZED'}
        if self.faults.intake_timeout:
            return {'status': 'UNKNOWN', 'reason_code': 'CAPTURE_UNCONFIRMED'}
        # Store original text locally; model/trace consumers get status fields only.
        payload = {'original_statement': request.message,
                   'reported_transaction_ids': list(request.transaction_ids)}
        if request.bank_id!='LEGACY_DEMO':payload['bank_id']=request.bank_id
        result = self.store.commit('report', owner, request.request_key, payload, {
            'status': 'OK', 'report_capture_status': 'CAPTURED',
            'regulatory_notice_status': 'REVIEW_REQUIRED', 'reported_at': self.now,
            'verification_status': 'VERIFIED' if self.bank._session(request.session_id) else 'PENDING',
            'investigation_status': 'NOT_STARTED', 'customer_confirmation_status': 'UNCONFIRMED',
        })
        if self.faults.intake_commit_then_timeout and result['status'] == 'OK':
            return {'status': 'UNKNOWN', 'reason_code': 'CAPTURE_RESPONSE_LOST'}
        return result

    @validated_result('report')
    def lookup_report(self, request):
        owner = self.owner(request)
        if not owner or not self.service(request, 'lookup_report'):
            return {'status': 'DENIED'}
        payload=self.store.original('report',owner,request.request_key)
        if payload and payload.get('bank_id','LEGACY_DEMO')!=request.bank_id:
            return {'status':'DENIED','reason_code':'BANK_SCOPE_MISMATCH'}
        return self.store.lookup('report', owner, request.request_key)

    @validated_result('case_write')
    def create_case(self, request, connection=None):
        if request.bank_id!=self.bank_id:return {'status':'DENIED','reason_code':'BANK_SCOPE_MISMATCH'}
        if not self.service(request, 'create_support_case'):
            return {'status': 'DENIED', 'reason_code': 'SERVICE_NOT_AUTHORIZED'}
        if not request.confirmed:
            return {'status': 'CONFIRMATION_REQUIRED'}
        if not request.account_id or not self.allowed_account(request, request.account_id, 'CASE_CREATE'):
            return {'status': 'DENIED', 'reason_code': 'RESOURCE_NOT_AUTHORIZED'}
        if self.faults.case_timeout:
            return {'status': 'UNKNOWN'}
        result = self.store.commit('case', self.owner(request), request.request_key,
                                   {'statement': request.message, 'account_id': request.account_id},
                                   {'status': 'OK', 'case_status': 'OPEN', 'committed_at': self.now},connection=connection)
        if self.faults.case_commit_then_timeout and result['status'] == 'OK':
            return {'status': 'UNKNOWN'}
        return result

    @validated_result('case_write')
    def lookup_request(self, request):
        if not self.service(request, 'lookup_request') or not request.account_id or not self.allowed_account(
                request, request.account_id, 'CASE_STATUS'):
            return {'status': 'DENIED'}
        return self.store.lookup('case', self.owner(request), request.request_key)

    @validated_result('handoff')
    def handoff(self, request, report, urgent=False):
        if not self.service(request, 'handoff_to_human') or not self.owner(request):
            return {'status': 'DENIED', 'handoff_status': 'BLOCKED'}
        if self.faults.receiver_denied:
            return {'status': 'DENIED', 'handoff_status': 'BLOCKED', 'payload': {}}
        # Handoffs have a separate authorization boundary, including supplied case context.
        payload = {}
        if request.case_id:
            case = self.case_status(request)
            if case['status'] != 'OK':
                return {'status': 'DENIED', 'handoff_status': 'BLOCKED', 'payload': {}}
            payload['case_id'] = request.case_id
        if report.get('status') == 'OK':
            own_report = self.lookup_report(request)
            if own_report.get('event_id') == report.get('event_id'):
                payload['report_id'] = report['event_id']
        payload = {k: v for k, v in payload.items() if k in self.faults.receiver_fields}
        queue = 'FRAUD_OPERATIONS' if urgent else 'CUSTOMER_SUPPORT'
        alternate = False
        if self.faults.primary_queue_down:
            if urgent and not self.faults.backup_queue_down:
                queue, alternate = 'FRAUD_BACKUP', True
            else:
                return {'status': 'UNKNOWN', 'handoff_status': 'UNAVAILABLE', 'payload': {}}
        if self.faults.handoff_timeout:
            return {'status': 'UNKNOWN', 'handoff_status': 'DELIVERY_UNKNOWN', 'payload': {}}
        stored_payload={'payload':payload,'queue':queue}
        if request.bank_id!='LEGACY_DEMO':stored_payload['bank_id']=request.bank_id
        return self.store.commit('handoff', self.owner(request), request.request_key,
                                 stored_payload,
                                 {'status': 'OK', 'handoff_status': 'ACKNOWLEDGED',
                                  'queue': queue, 'alternate_route': alternate, 'payload': payload})

    @validated_result('handoff')
    def lookup_handoff(self, request):
        if not self.service(request, 'reconcile_handoff') or not self.owner(request):
            return {'status': 'DENIED', 'handoff_status': 'BLOCKED'}
        payload=self.store.original('handoff',self.owner(request),request.request_key)
        if payload and payload.get('bank_id','LEGACY_DEMO')!=request.bank_id:
            return {'status':'DENIED','handoff_status':'BLOCKED','reason_code':'BANK_SCOPE_MISMATCH'}
        result = self.store.lookup('handoff', self.owner(request), request.request_key)
        if result['status'] == 'OK':
            # Recheck current receiver and resource permissions, even after a stored ACK.
            stored_case=result.get('payload',{}).get('case_id')
            mismatch=bool(request.case_id and stored_case and request.case_id!=stored_case)
            target_case=stored_case or request.case_id
            if self.faults.receiver_denied or mismatch or (target_case and self.case_status(
                    request.model_copy(update={'case_id':target_case}))['status'] != 'OK'):
                return {'status': 'DENIED', 'handoff_status': 'BLOCKED', 'payload': {}}
            result['payload'] = {k: v for k, v in result.get('payload', {}).items()
                                 if k in self.faults.receiver_fields}
        else:
            result['handoff_status'] = 'DELIVERY_UNKNOWN'
        return result
