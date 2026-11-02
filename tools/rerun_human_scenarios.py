"""Rerun the 22 supplied prompts with explicit synthetic preconditions.

Automated behavioral checks are separate from the preserved human assessments.
No provider calls or human approvals are made by this tool.
"""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from resolveguard.customer_review import fingerprint
from resolveguard.evaluation import fingerprint as code_fingerprint
from resolveguard.reply_generation import ReplyGenerator, ReplySettings
from resolveguard.storage import Store
from resolveguard.web import create_app

ROOT=Path(__file__).resolve().parents[1]


def run(output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    source=ROOT/'artifacts/human_feedback_20261101_batch02/Human_Observations.json'
    observations=json.loads(source.read_text(encoding='utf-8'))
    rows=[];traces=[]
    for number,observation in enumerate(observations,1):
        with TemporaryDirectory() as temp:
            db=Path(temp)/'web.sqlite3'
            with TestClient(create_app(db,reply_generator=ReplyGenerator(ReplySettings(mode='off')))) as client:
                profile='bow-customer-one' if number in {15,16,17} else 'signed-out'
                client.post('/api/session',json={'profile':profile})
                extras={}
                if number in {15,16,17}:
                    extras['transaction_ids']=['BOW-TXN-001-01']
                # Reproduce the reported stale product context before the broad
                # reward question; keep the tested customer prompt unchanged.
                if number==10:
                    client.post('/api/chat',json={'message':'What are the reward restrictions on YOLO Miles Card?',
                                'request_key':'setup-yolo','bank_id':'BOW'})
                body={'message':observation['Customer prompt'],'request_key':f'human22-{number}', 'bank_id':'BOW',**extras}
                response=client.post('/api/chat',json=body)
                result=response.json()
                checks={'http_ok':response.status_code==200}
                turns=[{'input':body,'output':result}]
                if number in {4,7,10}:
                    checks['asks_product']=bool(result.get('choose_product'))
                    checks['no_premature_terms']=not result.get('source_details')
                    product={4:'Whatever Plus Checking',7:'Whatever Starter Savings',10:'Whatever Debit Plus'}[number]
                    follow={'message':product,'request_key':f'human22-{number}-choice','bank_id':'BOW'}
                    selected=client.post('/api/chat',json=follow).json()
                    turns.append({'input':follow,'output':selected})
                    checks['resumes_original_question']=selected.get('answered_question')==body['message']
                    checks['product_answer_has_sources']=bool(selected.get('source_details'))
                elif number in {14,20}:
                    checks['requires_signin']=result.get('auth_required') is True
                    checks['no_private_cards']=not result.get('cards')
                elif number==15:
                    checks['focused_charge_response']='amount and date' in result.get('response','') or bool(result.get('cards'))
                    checks['no_product_policy_substitution']=not result.get('source_details')
                elif number in {16,17}:
                    checks['explicit_denial']=result.get('response_state')=='ACCESS_DENIED'
                    checks['no_substitute_records']=not result.get('cards')
                elif number==18:
                    checks['explicit_transfer_limit']="can't transfer money" in result.get('response','')
                    checks['no_signin_for_unsupported_action']=not result.get('auth_required')
                elif number==19:
                    checks['report_saved']=result.get('report',{}).get('status')=='OK'
                    checks['safe_followup']='merchant name and approximate date' in result.get('response','')
                    checks['intake_not_delayed']=not result.get('auth_required') and not result.get('cards')
                elif number in {21,22}:
                    checks['security_block']=result.get('response_state')=='SECURITY_BLOCKED'
                    checks['no_private_cards']=not result.get('cards')
                    checks['no_auth_continuation']=not result.get('pending_id')
                else:
                    checks['public_no_signin']=not result.get('auth_required')
                    checks['public_no_private_cards']=not result.get('cards')
                    checks['sources_or_bank_isolation']=bool(result.get('source_details')) or 'substituted' in result.get('response','')
                with Store(db).connect() as conn:
                    details=[json.loads(r[0]) for r in conn.execute('SELECT payload FROM review_details ORDER BY rowid')]
                case_traces=[d['workflow']['trace'] for d in details if d.get('workflow',{}).get('trace')]
                for trace in case_traces:trace['metadata'].update(case_id=observation['Review ID'],evaluation_scope='human22-behavioral-rerun')
                checks['trace_linked']=bool(case_traces)
                rows.append({'case_id':observation['Review ID'],'prompt':body['message'],
                             'preconditions':{'profile':profile,'stale_payment':extras.get('transaction_ids'),
                                              'setup_yolo':number==10,'followup_product_assumed':number in {4,7,10}},
                             'original_human_mark':observation['Human mark'],'original_human_comment':observation['Human comment'],
                             'checks':checks,'automated_behavior_passed':all(checks.values()),'turns':turns,
                             'trace_ids':[t['trace_id'] for t in case_traces],
                             'human_reassessment':'PENDING','coverage_limit':'Case-status scenario checks guest auth gate, not a completed authorized case lookup/handoff.' if number==20 else None})
                traces.extend(case_traces)
    summary={'cases':len(rows),'automated_behavior_passed':sum(r['automated_behavior_passed'] for r in rows),
             'code_sha256':code_fingerprint({p.name:p.read_text(encoding='utf-8') for p in (ROOT/'resolveguard').glob('*.py')}),
             'human_marks_unchanged':True,'human_reassessment':'PENDING','source_sha256':fingerprint(observations),
             'mode':'SYNTHETIC_NO_PROVIDER_CALLS','not_a_matched_human_before_after_score':True,
             'preconditions_note':'New isolated fixture runs. Original session IDs and exact product selections were not supplied; declared preconditions are reproducible assumptions.'}
    (output/'results.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (output/'traces.jsonl').write_text(''.join(json.dumps(t)+'\n' for t in traces),encoding='utf-8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    print(json.dumps(run(parser.parse_args().output),indent=2))
