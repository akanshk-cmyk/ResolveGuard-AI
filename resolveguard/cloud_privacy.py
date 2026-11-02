"""Cloud projection: no customer text, account records, tool payloads or secrets."""
from uuid import UUID


def cloud_trace(trace: dict) -> dict:
    projected = {'trace_id':str(UUID(trace['trace_id'])), 'spans':[]}
    # Metadata values may contain arbitrary customer-provided text: omit entirely.
    projected['metadata'] = {'projection': 'execution-structure-only-v1'}
    names = {'resolveguard.journey', 'classify', 'capture', 'lookup', 'retrieve',
             'handoff', 'compose', 'verify', 'mock.classify', 'nebius.classify',
             'template.explain', 'get_transaction', 'get_case_status',
             'record_issue_intake', 'search_approved_policy', 'handoff_to_human',
             'lookup_request', 'create_support_case','fraud.trigger','freeze_demo_debit_card',
             'verify_demo_card_state','create_demo_fraud_dispute','emergency.compose',
             'emergency.response_approved','customer.response.pipeline','emergency.journey'}
    for source in trace['spans']:
        projected['spans'].append({
            'id':str(UUID(source['id'])),
            'parent_id':str(UUID(source['parent_id'])) if source['parent_id'] else None,
            'name':source['name'] if source['name'] in names else 'workflow.step',
            'run_type':source['run_type'] if source['run_type'] in {'chain','tool','llm'} else 'chain',
            'start_time':source['start_time'], 'end_time':source['end_time'],
            'latency_ms':source['latency_ms'],
            'inputs':{}, 'outputs':{'execution_error':bool(source.get('error'))},
            'error':'STEP_FAILED' if source.get('error') else None})
        if source['name'] in {'fraud.trigger','freeze_demo_debit_card','verify_demo_card_state',
                              'create_demo_fraud_dispute','emergency.compose','emergency.response_approved'}:
            output=source.get('outputs') or {}
            enums={'status':{'OK','DENIED','UNKNOWN','NOT_ATTEMPTED'},
                   'state':{'LOCKED','NOT_CONFIRMED'},'card_state':{'LOCKED','NOT_CONFIRMED'},
                   'intent':{'HIGH_SEVERITY_FRAUD'},
                   'response_state':{'EMERGENCY_FRAUD','AUTH_REQUIRED','STEP_UP_REQUIRED','REVIEW_REQUIRED'}}
            for key,allowed in enums.items():
                if isinstance(output.get(key),str) and output[key] in allowed:
                    projected['spans'][-1]['outputs'][key]=output[key]
    return projected
