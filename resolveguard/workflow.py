"""The same workflow steps run in a real LangGraph graph or an offline executor."""
import copy
import re
from contextlib import nullcontext
from typing import TypedDict
from pydantic import ValidationError
from .backend import Backend
from .contracts import Request, Route, WorkflowState, validate_result, Explanation
from .model import MockModel
from .retrieval import PolicyIndex
from .telemetry import Trace, sanitize
from .intake_signals import asserted_payment_error


class GraphState(TypedDict):
    state: WorkflowState


def security_check(state, backend, model, index, trace):
    from .security_routing import assess_security, security_metadata
    assessment = assess_security(state.request.message)
    state.security = security_metadata(assessment)
    with trace.span('security.assess', inputs={'detector_version': state.security['detector_version']}) as span:
        span['outputs'] = dict(state.security, actual_authorization_decision='NOT_ATTEMPTED_BLOCKED' if assessment.blocked else 'DEFER_TO_BACKEND',
                               blocked_tool_calls=['restricted_lookup'] if assessment.blocked else [])


def classify(state, backend, model, index, trace):
    if state.security.get('recommended_action') in {'BLOCK_RESTRICTED_REQUEST','PUBLIC_SECURITY_INFORMATION'}:
        from .model import TunedMockModel
        report = TunedMockModel(4).classify(state.request.message)['potential_fraud_error']
        state.route = Route(primary_intent='FRAUD_ERROR_REPORT' if report else 'UNSUPPORTED_REQUEST' if state.security['recommended_action']=='BLOCK_RESTRICTED_REQUEST' else 'POLICY_LOOKUP',
                            potential_fraud_error=report, human_requested=False, urgent=report)
        return
    with trace.span(('mock' if model.is_mock else 'nebius')+'.classify', 'llm', {'message': sanitize(state.request.message)}) as span:
        try:
            state.route = Route.model_validate(model.classify(sanitize(state.request.message)))
            if asserted_payment_error(state.request.message) and not getattr(model,'trusted_case_confirmation',False):
                state.route=state.route.model_copy(update={'primary_intent':'FRAUD_ERROR_REPORT','potential_fraud_error':True})
            if not state.route.potential_fraud_error:
                if state.route.primary_intent=='OTHER_OR_UNCLEAR' and (state.request.case_id or state.request.transaction_ids):
                    state.route=state.route.model_copy(update={'primary_intent':'CASE_STATUS' if state.request.case_id else 'TRANSACTION_INQUIRY'})
                if state.request.case_id and 'power of attorney' in state.request.message.lower() and 'revoked' in state.request.message.lower():
                    state.route=state.route.model_copy(update={'primary_intent':'CASE_STATUS'})
            span['outputs'] = state.route.model_dump()
            if asserted_payment_error(state.request.message) and not getattr(model,'trusted_case_confirmation',False):
                span['outputs']['safety_rule']='ASSERTED_PAYMENT_ERROR'
        except Exception:
            # Preserve a clearly expressed report even if the mock/schema fails.
            text = state.request.message.lower()
            fraud = asserted_payment_error(state.request.message) or any(x in text for x in ('unauthorized', 'did not authorize', 'do not recognize',
                                            "don't recognize", 'stolen', 'fraud', 'wrong amount'))
            state.route = Route(primary_intent='FRAUD_ERROR_REPORT' if fraud else 'OTHER_OR_UNCLEAR',
                                potential_fraud_error=fraud, human_requested=True, urgent=False)
            state.errors.append('ROUTING_INVALID_OR_UNAVAILABLE')
            span['outputs'] = {'fallback': True, **state.route.model_dump()}


def call(state, trace, name, function, inputs=None):
    with trace.span(name, 'tool', inputs) as span:
        try:
            result = function()
            # Revalidate at graph ingress too, including custom/fault-injected tools.
            kinds = {'get_transaction': 'transaction', 'get_case_status': 'case_read',
                     'get_notice_status':'notice_read',
                     'record_issue_intake': 'report', 'lookup_report': 'report',
                     'create_support_case': 'case_write', 'lookup_request': 'case_write',
                     'handoff_to_human': 'handoff', 'reconcile_handoff': 'handoff',
                     'search_approved_policy': 'policy'}
            if name in kinds:
                result = validate_result(kinds[name], result)
        except ValidationError:
            result = {'status': 'UNKNOWN', 'reason_code': 'TOOL_SCHEMA_INVALID'}
            if name in ('handoff_to_human', 'reconcile_handoff'):
                result.update(handoff_status='DELIVERY_UNKNOWN', payload={})
            if name in ('get_transaction', 'get_case_status'):
                result['data'] = None
            state.errors.append('TOOL_SCHEMA_INVALID:'+name)
        except Exception:
            # Backend faults never become confirmed customer-visible success.
            result = {'status': 'UNKNOWN', 'reason_code': 'TOOL_ERROR'}
            state.errors.append('TOOL_ERROR:'+name)
        span['outputs'] = result
        state.tools.append({'name': name, 'status': result.get('status'),
                            'reason_code': result.get('reason_code')})
        return result


def capture(state, backend, model, index, trace):
    if not state.route.potential_fraud_error:
        return
    state.report = call(state, trace, 'record_issue_intake', lambda: backend.capture(state.request))
    if state.report.get('status') == 'UNKNOWN':
        recovered = call(state, trace, 'lookup_report', lambda: backend.lookup_report(state.request))
        if recovered.get('status') == 'OK':
            state.report = recovered


def needs_lookup(state):
    if re.search(r'\b(full debit card number|debug trace.*otp|payload.*another customer)\b',state.request.message,re.I):return False
    if state.security.get('recommended_action') in {'BLOCK_RESTRICTED_REQUEST','PUBLIC_SECURITY_INFORMATION'}:
        return False
    return state.route.primary_intent in {'TRANSACTION_INQUIRY', 'FEE_INQUIRY', 'CASE_STATUS',
                                          'SUPPORT_CASE_REQUEST', 'FRAUD_ERROR_REPORT'}


def lookup(state, backend, model, index, trace):
    req = state.request
    intent = state.route.primary_intent
    if (intent=='CASE_STATUS' and not req.case_id or intent in {'TRANSACTION_INQUIRY','FEE_INQUIRY'} and not req.transaction_ids):
        state.access_error=backend.assurance_error(req)
        if state.access_error:
            with trace.span('authorization.check') as span:span['outputs']={'allowed':False,'reason_code':state.access_error}
            return
    if intent == 'SUPPORT_CASE_REQUEST':
        state.case = call(state, trace, 'create_support_case', lambda: backend.create_case(req))
        if state.case.get('status') == 'UNKNOWN':
            recovered = call(state, trace, 'lookup_request', lambda: backend.lookup_request(req))
            if recovered.get('status') == 'OK':
                state.case = recovered
        return
    if intent == 'CASE_STATUS' and backend.faults.handoff_status_query:
        state.handoff = call(state, trace, 'reconcile_handoff', lambda: backend.lookup_handoff(req))
        return
    if intent == 'CASE_STATUS' and req.case_id:
        if 'error notice' in req.message.lower():
            state.notice=call(state,trace,'get_notice_status',lambda:backend.notice_status(req))
        result = call(state, trace, 'get_case_status', lambda: backend.case_status(req), {'case_id': req.case_id})
        if result.get('status') == 'OK':
            state.records.append(dict(result['data'], kind='case'))
        return
    if intent in {'TRANSACTION_INQUIRY', 'FEE_INQUIRY', 'FRAUD_ERROR_REPORT'}:
        for transaction_id in req.transaction_ids:
            result = call(state, trace, 'get_transaction', lambda tid=transaction_id: backend.transaction(req, tid),
                          {'transaction_id': transaction_id})
            if result.get('status') == 'OK':
                state.records.append(dict(result['data'], kind='transaction'))


def retrieve(state, backend, model, index, trace):
    if state.security.get('recommended_action') in {'BLOCK_RESTRICTED_REQUEST','PUBLIC_SECURITY_INFORMATION'}:
        return
    if state.route.primary_intent == 'UNSUPPORTED_REQUEST':
        return
    result = call(state, trace, 'search_approved_policy', lambda: index.retrieve(
        sanitize(state.request.message), product=state.request.product,
        jurisdiction=state.request.jurisdiction, as_of=backend.now[:10]))
    if result['status'] == 'CONFLICT':
        state.errors.append('POLICY_CONFLICT')
    # Documents are evidence, never instructions. Block obvious injected instructions.
    for chunk in result.get('chunks', []):
        lower = chunk['text'].lower()
        if any(x in lower for x in ('ignore verification', 'ignore previous instructions',
                                    'reveal all accounts', 'system prompt:', 'bypass authentication')):
            state.errors.append('POLICY_INJECTION_BLOCKED')
            continue
        state.policies.append(chunk)


def handoff(state, backend, model, index, trace):
    if not (state.route.human_requested or state.route.potential_fraud_error):
        return
    state.handoff = call(state, trace, 'handoff_to_human', lambda: backend.handoff(
        state.request, state.report, urgent=state.route.urgent or state.route.potential_fraud_error))
    if state.handoff.get('handoff_status') == 'DELIVERY_UNKNOWN':
        recovered = call(state, trace, 'reconcile_handoff', lambda: backend.lookup_handoff(state.request))
        if recovered.get('status') == 'OK':
            state.handoff = recovered


def canonical_response(state):
    """Use deterministic wording for claims that depend on committed backend state."""
    lines = []
    text=state.request.message.lower()
    if 'debug trace' in text and 'otp' in text:
        state.errors=list(dict.fromkeys(state.errors+['PRIVACY_INCIDENT_REPORTED']))
        return 'PRIVACY_INCIDENT','A possible secret in a trace needs privacy review. Do not repeat the code here. The local operations evidence records this incident signal without the secret.'
    if 'payload' in text and 'another customer' in text:return 'DATA_BLOCKED',"Another customer's information must not be used or shared. Unexpected private fields require review."
    if 'full debit card number' in text:return 'SAFE_GUIDANCE','Full card numbers are not available in chat. Use the approved secure banking channel; do not share your PIN, password or security code here.'
    from .security_routing import BLOCK_MESSAGE, EDUCATION_MESSAGE
    if state.security.get('recommended_action') == 'BLOCK_RESTRICTED_REQUEST':
        if not state.route.potential_fraud_error:
            return 'SECURITY_BLOCKED', BLOCK_MESSAGE
        lines.append(BLOCK_MESSAGE)
    if state.security.get('recommended_action') == 'PUBLIC_SECURITY_INFORMATION' and not state.route.potential_fraud_error:
        return 'PUBLIC_SECURITY_INFORMATION', EDUCATION_MESSAGE
    route = state.route
    status = 'NO_ACTION'
    if route.primary_intent == 'UNSUPPORTED_REQUEST':
        status = 'PROHIBITED_ACTION'
        lines.append('This demo cannot transfer funds, issue refunds, change credentials or decide disputes. Use an approved human support route.')
    if route.primary_intent == 'OTHER_OR_UNCLEAR':
        status = 'SAFE_GUIDANCE'
        lines.append('Please clarify the support request. Do not share passwords, PINs, CVVs or one-time codes; use the secure sign-in flow.')
    if route.potential_fraud_error:
        if state.report.get('status') == 'OK':
            status = 'CAPTURED_REVIEW'
            lines.append(f"Your report was captured as {state.report['event_id']}.")
            lines.append('Legal notice status is under review; an investigation or card block is not confirmed.')
        elif state.report.get('status') == 'CONFLICT':
            status = 'CONFLICT'
            lines.append('This request reference belongs to a different report. Use a new request reference for a new report.')
        else:
            status = 'UNKNOWN'
            lines.append('Report capture is unconfirmed. Use the approved support route; do not assume the report was received.')
    if state.case:
        cs = state.case.get('status')
        status = {'OK': 'CASE_CREATED', 'DENIED': 'ACCESS_DENIED',
                  'CONFIRMATION_REQUIRED': 'CONFIRMATION_REQUIRED', 'CONFLICT': 'CONFLICT'}.get(cs, 'UNKNOWN')
        if cs == 'OK':
            lines.append(f"Support case {state.case['event_id']} is committed with status {state.case['case_status']}.")
        elif cs == 'CONFIRMATION_REQUIRED':
            lines.append('Review and confirm the case submission before it is created.')
        else:
            lines.append('Case creation is not confirmed. Do not submit a new request until this reference is reconciled.')
    for record in state.records:
        if record['kind'] == 'transaction':
            cents = record['amount_cents']
            amount = f"{'-' if cents < 0 else ''}${abs(cents)//100}.{abs(cents)%100:02d}"
            lines.append(f"{record['transaction_id']}: {amount} {record['currency']}, {record['status']}, {record['merchant']}, {record['posted_on']}.")
        else:
            lines.append(f"{record['case_id']}: verified status {record['status']}; created {record['created_at']}.")
    reads = [t for t in state.tools if t['name'] in {'get_transaction', 'get_case_status'}]
    if any(t['status'] == 'DENIED' for t in reads):
        if not route.potential_fraud_error:
            status = ('AUTH_REQUIRED' if any(t['reason_code'] == 'AUTHENTICATION_REQUIRED' for t in reads) else
                      'STEP_UP_REQUIRED' if any(t['reason_code'] == 'STEP_UP_REQUIRED' for t in reads) else 'ACCESS_DENIED')
        lines.append('Restricted details are unavailable for this session. Use secure verification; knowing an identifier does not grant access.')
    elif any(t['status'] == 'UNKNOWN' for t in reads):
        if not route.potential_fraud_error:
            status = 'UNVERIFIED'
        lines.append('The record service is unavailable. Transaction or case details are unverified.')
    elif not state.records and route.primary_intent in {'TRANSACTION_INQUIRY', 'CASE_STATUS', 'FEE_INQUIRY'} and not state.handoff:
        status = 'CLARIFICATION_REQUIRED'
        lines.append('Select the transaction or case to look up through the secure application.')
    if state.policies:
        # Quote evidence verbatim in mock mode, making grounding machine-checkable.
        for chunk in state.policies[:2]:
            lines.append(f"Demo guidance [{chunk['chunk_id']}]: {chunk['text']}")
    elif route.primary_intent == 'POLICY_LOOKUP':
        status = 'UNVERIFIED'
        lines.append('No applicable, consistent policy evidence was found. Ask support for verified guidance.')
    hs = state.handoff.get('handoff_status')
    if hs == 'ACKNOWLEDGED':
        if not route.potential_fraud_error:
            status = 'HANDOFF_VERIFIED'
        lines.append(f"The simulated {state.handoff['queue']} queue acknowledged the handoff.")
    elif hs:
        if not route.potential_fraud_error:
            status = {'BLOCKED': 'HANDOFF_BLOCKED', 'UNAVAILABLE': 'HANDOFF_UNAVAILABLE'}.get(hs, 'DELIVERY_UNKNOWN')
        lines.append({'BLOCKED': 'No restricted context was transferred to an unauthorized receiver.',
                      'UNAVAILABLE': 'The human support connection is unavailable. No transfer is confirmed.'}.get(
                          hs, 'Handoff delivery is unknown. No receiving agent is confirmed.'))
    if not lines:
        status = 'UNVERIFIED'
        lines.append('No verified outcome is available. Use human support.')
    if route.primary_intent=='CASE_STATUS' and 'reported an error yesterday' in text:
        status='RECEIPT_SEPARATE';lines.append('Report capture, legal notice receipt and case visibility are separate. A case status does not confirm legal receipt.')
    if route.primary_intent=='CASE_STATUS' and 'error notice' in text:
        status='VERIFIED_NOTICE_STATE' if state.notice.get('status')=='OK' else 'UNVERIFIED'
        lines.append('Formal notice status: '+state.notice.get('regulatory_notice_status','not confirmed')+'. This is separate from case progress.')
    if route.primary_intent=='POLICY_LOOKUP' and 'write a letter' in text and 'report' in text:
        status='POLICY_EXPLANATION' if state.policies else 'UNVERIFIED';lines.append('Only the approved intake service determines legal receipt. I cannot invent a letter requirement or confirm investigation from a chat request.')
    if route.potential_fraud_error and 'report reached the bank' in text:
        status='RECEIVED_CASE_UNKNOWN' if state.report.get('status')=='OK' else 'UNKNOWN';lines.append('Report capture is separate from case creation. No case creation is confirmed here.')
    if route.potential_fraud_error and 'close' in text and 'claim' in text:
        status='HUMAN_REVIEW';lines.append('I have not closed the claim. A person must review this request; the report remains preserved.')
    if text.startswith(('did you block','have you blocked')):lines.append('No confirmed card-block event is available. Do not assume the card is protected.')
    if state.access_error and not route.potential_fraud_error:
        status='AUTH_REQUIRED' if state.access_error=='AUTHENTICATION_REQUIRED' else 'STEP_UP_REQUIRED' if state.access_error=='STEP_UP_REQUIRED' else 'ACCESS_DENIED'
        lines.append('Secure verification and permission are required before account details can be shown.')
    return status, '\n'.join(lines)


def compose(state, backend, model, index, trace):
    state.response_state, approved = canonical_response(state)
    state.model_context = sanitize({
        'route': state.route.model_dump(), 'records': state.records,
        'policies': [{k: c[k] for k in ('chunk_id', 'text', 'version')} for c in state.policies],
        'report': state.report, 'case': state.case,
        'handoff': {k: v for k, v in state.handoff.items() if k != 'payload'},
    })
    with trace.span('template.explain', 'chain', state.model_context) as span:
        try:
            state.response = Explanation.model_validate({
                'response':approved if state.security.get('recommended_action') in {'BLOCK_RESTRICTED_REQUEST','PUBLIC_SECURITY_INFORMATION'} else model.explain(copy.deepcopy(state.model_context), approved)}).response
        except Exception:
            state.errors.append('GENERATION_UNAVAILABLE')
            state.response = approved
        span['outputs'] = {'response': state.response, 'mock': model.is_mock,
                           'usage': {'input_tokens': None, 'output_tokens': None}}


def verify(state, backend, model, index, trace):
    # The first adapter deliberately supports only a fixed evidence-backed response.
    # Free-form semantic checking is a separate future evaluator, not claimed here.
    status, approved = canonical_response(state)
    if state.response != approved:
        state.errors.append('OUTPUT_REJECTED')
        state.response = approved
    state.response = sanitize(state.response)
    state.response_state = status
    state.output_verified = True


STEPS = [('security_check', security_check), ('classify', classify), ('capture', capture), ('lookup', lookup),
         ('retrieve', retrieve), ('handoff', handoff), ('compose', compose), ('verify', verify)]


class Workflow:
    def __init__(self, backend: Backend, model=None, index=None, engine='offline'):
        self.backend, self.model = backend, model or MockModel()
        self.index = index or PolicyIndex()
        if engine not in ('offline', 'langgraph'):
            raise ValueError('engine must be offline or langgraph')
        self.engine = engine

    def _execute(self, state, trace, name, function):
        with trace.span(name, inputs={'intent': state.route.primary_intent if state.route else None}) as span:
            function(state, self.backend, self.model, self.index, trace)
            span['outputs'] = {'response_state': state.response_state,
                               'error_codes': list(state.errors), 'record_count': len(state.records)}

    def build_graph(self, trace):
        try:
            from langgraph.graph import StateGraph, START, END
        except ImportError as exc:
            raise RuntimeError('LangGraph is not installed. Install requirements.txt or use --engine offline. No LangGraph execution is claimed.') from exc
        builder = StateGraph(GraphState)
        for name, function in STEPS:
            def node(values, n=name, f=function):
                state = values['state']
                self._execute(state, trace, n, f)
                return {'state': state}
            builder.add_node(name, node)
        builder.add_edge(START, 'security_check')
        builder.add_edge('security_check', 'classify')
        builder.add_edge('classify', 'capture')
        builder.add_conditional_edges('capture', lambda values: 'lookup' if needs_lookup(values['state']) else 'retrieve',
                                      {'lookup': 'lookup', 'retrieve': 'retrieve'})
        for a, b in [('lookup', 'retrieve'), ('retrieve', 'handoff'), ('handoff', 'compose'), ('compose', 'verify')]:
            builder.add_edge(a, b)
        builder.add_edge('verify', END)
        # The outer conversation owns checkpoints. Do not inherit its saver into
        # this request-scoped graph or serialize internal dataclasses implicitly.
        return builder.compile(checkpointer=False)

    def run(self, request: Request, metadata=None):
        # Validate before creating traces or performing backend side effects.
        request = Request.model_validate(request)
        from .fraud_triage import active_theft,triage
        if active_theft(request.message):
            from .security_routing import assess_security
            from .telemetry import utcnow
            output,emergency_trace,tools=triage(self.backend,request,utcnow(),blocked=assess_security(request.message).blocked)
            emergency_trace['metadata'].update(sanitize(metadata or {}))
            result=dict(output,trace=emergency_trace,tools=tools,engine='emergency-deterministic',
                        model_context={},citations=[],errors=[],output_verified=False,
                        input_tokens=None,output_tokens=None,model_cost_usd=0.0,cost_status='NO_MODEL_CALLS')
            from .monitoring import observe
            observe(result)  # Existing explicit dual opt-in export; never enables cloud.
            return result
        from .security_routing import assess_security
        if hasattr(self.backend,'policy_index_for') and assess_security(request.message).recommended_action=='CONTINUE_BANKING_FLOW':
            self.index=self.backend.policy_index_for(request)
        usage_start=len(getattr(self.model,'usage',[]))
        trace = Trace({'agent_version': 'workflow-v2-continuity', 'prompt_version': getattr(self.model,'prompt_version','mock-rules-v0'),
                       'bank_id':request.bank_id,
                       'contract_version': 'pydantic-boundaries-v1',
                       'model': self.model.name, 'intended_live_model': 'zai-org/GLM-5.3-Flash',
                       'engine': self.engine, 'environment': 'synthetic-offline' if self.model.is_mock else 'synthetic-provider', **(metadata or {})})
        state = WorkflowState(request=request)
        # Suppress framework auto-export even if a user's ambient env enables it.
        try:
            from langsmith import tracing_context
            tracing_guard = tracing_context(enabled=False)
        except ImportError:
            tracing_guard = nullcontext()
        with tracing_guard, trace.span('resolveguard.journey', inputs={'message': sanitize(request.message),
                                                                      'selected_transactions': request.transaction_ids}) as root:
            if self.engine == 'langgraph':
                state = self.build_graph(trace).invoke({'state': state})['state']
            else:
                for name, function in STEPS:
                    if name == 'lookup' and not needs_lookup(state):
                        continue
                    self._execute(state, trace, name, function)
            result = {
                'route': state.route.model_dump(), 'security': state.security, 'notice':state.notice,'response': state.response,'bank_id':request.bank_id,
                'response_state': state.response_state, 'report': state.report,
                'case': state.case, 'handoff': state.handoff, 'records': state.records,
                'citations': [c['chunk_id'] for c in state.policies],
                'model_context': state.model_context, 'tools': state.tools,
                'errors': state.errors, 'output_verified': state.output_verified,
                'execution_mode': 'MOCK' if self.model.is_mock else 'NEBIUS', 'engine': self.engine,
                'input_tokens': None, 'output_tokens': None,
                'model_cost_usd': 0.0, 'cost_status': 'MOCK_NO_PROVIDER_CALLS',
            }
            if not self.model.is_mock:
                usage=getattr(self.model,'usage',[])[usage_start:]
                result.update(input_tokens=sum(u['input_tokens'] for u in usage) if usage else None,
                              output_tokens=sum(u['output_tokens'] for u in usage) if usage else None,
                              model_cost_usd=sum(u['estimated_cost_usd'] for u in usage) if usage else None,
                              cost_status='ESTIMATED_FROM_REPORTED_USAGE' if usage else 'UNKNOWN_PROVIDER_USAGE')
            root['outputs'] = {k: result[k] for k in ('route', 'response_state', 'errors', 'execution_mode')}
        output = {**result, 'trace': trace.export()}
        from .monitoring import observe
        observe(output)
        return output
