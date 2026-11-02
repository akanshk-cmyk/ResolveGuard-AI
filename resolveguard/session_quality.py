"""Independent local trajectory checks; never replay a banking operation."""
import json
from collections import defaultdict
from .intake_signals import asserted_payment_error


def inspect_session(store,binding,generation,bank_id):
    with store.connect() as db:
        rows=db.execute('''SELECT r.payload,d.payload AS detail FROM customer_reviews r
            JOIN review_details d ON d.review_id=r.review_id
            WHERE r.binding=? AND r.generation=? AND r.bank_id=? ORDER BY r.rowid''',(binding,generation,bank_id)).fetchall()
    failures=[];request_reports=defaultdict(set);request_cases=defaultdict(set);examined=0
    for row in rows:
        value=json.loads(row['payload']);detail=json.loads(row['detail'])
        if not detail.get('approved_for_delivery'):continue
        examined+=1;q=value['qa'];snapshot=value['snapshot'];resolution=value.get('resolution') or {}
        refs=resolution.get('evidence',[])
        report_refs={e['resource_ref'] for e in refs if e.get('event_kind')=='REPORT_CAPTURED'}
        case_refs={e['resource_ref'] for e in refs if e.get('event_kind')=='CASE_CREATED'}
        request_reports[q['turn_ref']].update(report_refs);request_cases[q['turn_ref']].update(case_refs)
        prompt=detail.get('prompt','');reply=detail.get('reply','')
        if asserted_payment_error(prompt) and not report_refs and not value.get('fallback'):
            failures.append({'check':'ERROR_REPORT_PRESERVATION','reason':'ASSERTED_REPORT_MISSING_RECEIPT','turn_ref':q['turn_ref']})
        if ('Your report is saved.' in reply or 'Your support request is saved and open.' in reply) and not report_refs and not case_refs:
            failures.append({'check':'ACTION_INTEGRITY','reason':'SUCCESS_WITHOUT_RECEIPT','turn_ref':q['turn_ref']})
        for event_ref in report_refs|case_refs:
            kind='report' if event_ref in report_refs else 'case'
            with store.connect() as db:record=db.execute('SELECT owner,result FROM events WHERE kind=? AND event_id=?',(kind,event_ref)).fetchone()
            from .customer_review import fingerprint
            if record and snapshot.get('customer_ref') is None:
                failures.append({'check':'ACTION_INTEGRITY','verdict':'NOT_EVALUABLE','reason':'HISTORICAL_OWNER_EVIDENCE_MISSING','turn_ref':q['turn_ref']})
            elif not record or 'customer-'+fingerprint(record['owner'])!=snapshot.get('customer_ref') or json.loads(record['result']).get('status')!='OK':
                failures.append({'check':'ACTION_INTEGRITY','reason':'RECEIPT_NOT_OWNED_OR_NOT_COMMITTED','turn_ref':q['turn_ref']})
    for values in (request_reports,request_cases):
        for turn,refs in values.items():
            if len(refs)>1:failures.append({'check':'ACTION_INTEGRITY','reason':'MULTIPLE_COMMITS_FOR_ONE_RETRY_KEY','turn_ref':turn})
    return {'version':'local-session-trajectory-v1','reviewed_deliveries':examined,'failures':failures,
            'scope':'Independent receipt, ownership, report-preservation and retry checks on recorded deliveries; no model opinion or tool replay'}
