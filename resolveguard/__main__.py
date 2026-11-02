"""CLI: python -m resolveguard ask / evaluate / index / publish."""
import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from pydantic import ValidationError
from .backend import Backend
from .contracts import Request
from .evaluation import execute_case, summarize, fingerprint
from .retrieval import PolicyIndex
from .storage import Store
from .telemetry import sanitize
from .workflow import Workflow

ROOT = Path(__file__).resolve().parents[1]


def evaluate(args):
    dataset = json.loads(Path(args.dataset).read_text(encoding='utf-8'))
    if args.require_reviewed and (dataset.get('provenance_status') != 'ATTESTED' or
            any(c['metadata']['human_review_status']!='APPROVED' for c in dataset['cases'])):
        raise ValueError('Dataset is not human-reviewed and provenance-attested; cannot claim a golden baseline')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = Path(args.output or ROOT/'artifacts'/('mock-'+stamp))
    output.mkdir(parents=True,exist_ok=False)
    dbs = output/'isolated-state'
    dbs.mkdir()
    rows = []
    for case in dataset['cases']:
        for repeat in range(args.repeat):
            row = execute_case(case,dbs,args.engine,repeat,model=select_model(args.provider))
            # Attach expected/observed evaluation metadata only AFTER inference.
            for attempt in row['attempts']:
                attempt['trace']['metadata'].update(sanitize({
                    'dataset_version':dataset['dataset_version'],'dataset_sha256':fingerprint(dataset),
                    'expected_output':case['expected'],'predicted_output':attempt['route'],
                    'correctness':row['passed'],'failure_categories':row['failure_categories']}))
            rows.append(row)
    summary = summarize(rows,dataset,args.engine)
    summary['code_sha256'] = fingerprint({p.name:p.read_text(encoding='utf-8') for p in (ROOT/'resolveguard').glob('*.py')})
    summary['fixture_sha256'] = fingerprint({str(p.relative_to(ROOT)):p.read_text(encoding='utf-8') for p in
        list((ROOT/'resolveguard_synthetic_v04/fixtures').glob('*.json'))+[ROOT/'data/supplemental_fixtures.json']})
    (output/'results.json').write_text(json.dumps(sanitize(rows),indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    with (output/'scored_results.csv').open('w',newline='',encoding='utf-8-sig') as handle:
        fields=['case_id','repeat_index','scenario_type','expected_intent','actual_intent','pass_fail',
                'failure_categories','latency_ms','trace_id','execution_mode','human_review_status']
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for r in rows:
            writer.writerow({'case_id':r['case_id'],'repeat_index':r['repeat_index'],
                'scenario_type':r['scenario_type'],'expected_intent':r['expected']['primary_intent'],
                'actual_intent':r['actual']['route']['primary_intent'],'pass_fail':'PASS' if r['passed'] else 'FAIL',
                'failure_categories':';'.join(r['failure_categories']),'latency_ms':r['latency_ms'],
                'trace_id':r['actual']['trace']['trace_id'],'execution_mode':r['actual']['execution_mode'],
                'human_review_status':r['human_review_status']})
    with (output/'traces.jsonl').open('w',encoding='utf-8') as handle:
        for r in rows:
            for attempt in r['attempts']:
                handle.write(json.dumps(sanitize(attempt['trace']),ensure_ascii=False)+'\n')
    failure_examples = {}
    for row in rows:
        for category in row['failure_categories']:
            failure_examples.setdefault(category,[]).append(row['case_id'])
    (output/'failure_analysis.json').write_text(json.dumps({
        'status':'Observed mock failures only; human root-cause annotation required',
        'clusters':[{'category':key,'case_run_count':count,'unique_case_count':len(set(failure_examples[key])),
                     'example_case_ids':list(dict.fromkeys(failure_examples[key]))[:3],
                     'estimated_rework_minutes':len(set(failure_examples[key]))*10,
                     'cost_basis':'Illustrative 10-minute baseline rework assumption; not measured financial harm'}
                    for key,count in Counter(f for r in rows for f in r['failure_categories']).most_common()],
        'improvements':'Not applied; preserve this run as mock diagnostic evidence, not a live model baseline.'},indent=2)+'\n',encoding='utf-8')
    if args.ragas or args.judge:
        from .semantic_evaluation import evaluate_semantics
        semantic = evaluate_semantics(str(output/'semantic_results.json'), args.ragas, args.judge)
        if semantic['status'] != 'COMPLETE':
            raise RuntimeError('Semantic metrics contain errors; inspect semantic_results.json')
    if args.langsmith:
        from .cloud_verify import verify_cloud
        verify_cloud(str(output/'cloud_verification.json'))
    print(json.dumps({'output_directory':str(output),**summary},indent=2))
    return 1 if args.strict else 0  # Mock/draft runs always fail a release gate.


def select_model(provider):
    if provider=='nebius':
        import os
        if not os.environ.get('NEBIUS_API_KEY'):
            raise RuntimeError('NEBIUS_API_KEY is required for explicit --provider nebius execution')
        from .nebius import NebiusModel
        return NebiusModel(enabled=True)
    if provider=='mock-v4':
        from .model import TunedMockModel
        return TunedMockModel(4)
    from .model import MockModel
    return MockModel()


def main(argv=None):
    parser=argparse.ArgumentParser(description='ResolveGuard credential-free synthetic demo')
    sub=parser.add_subparsers(dest='command',required=True)
    security=sub.add_parser('evaluate-security')
    security.add_argument('--output',default='artifacts/security_evaluation/results.json')
    ask=sub.add_parser('ask');ask.add_argument('message')
    ask.add_argument('--session',default='SESS-001');ask.add_argument('--transaction',action='append',default=[])
    ask.add_argument('--case');ask.add_argument('--account');ask.add_argument('--confirmed',action='store_true')
    ask.add_argument('--request-key',required=True);ask.add_argument('--db',default='artifacts/demo.sqlite3')
    ask.add_argument('--engine',choices=['offline','langgraph'],default='offline')
    ask.add_argument('--provider',choices=['mock','mock-v4','nebius'],default='mock',help='nebius explicitly enables paid classification requests; default stays local')
    ev=sub.add_parser('evaluate');ev.add_argument('--dataset',default=str(ROOT/'data/evaluation_40.json'))
    ev.add_argument('--engine',choices=['offline','langgraph'],default='offline');ev.add_argument('--output')
    ev.add_argument('--repeat',type=int,default=1);ev.add_argument('--strict',action='store_true')
    ev.add_argument('--require-reviewed',action='store_true')
    ev.add_argument('--provider',choices=['mock','mock-v4','nebius'],default='mock')
    ev.add_argument('--ragas',action='store_true',help='Also run the separate public-policy semantic pilot (paid Nebius calls)')
    ev.add_argument('--judge',action='store_true',help='Grade semantic pilot with the banking rubric (paid Nebius calls)')
    ev.add_argument('--langsmith',action='store_true',help='Publish and read back a three-case hosted mock experiment')
    semantic=sub.add_parser('semantic-eval',help='Explicit paid Nebius RAGAS/judge evaluation')
    semantic.add_argument('--output',required=True)
    semantic.add_argument('--dataset',default=None)
    semantic.add_argument('--ragas',action='store_true');semantic.add_argument('--judge',action='store_true')
    cloud=sub.add_parser('verify-cloud',help='Publish synthetic mock experiment and verify remote nested runs')
    cloud.add_argument('--output',required=True);cloud.add_argument('--limit',type=int,default=3)
    dashboard=sub.add_parser('dashboard',help='Read-only localhost operational dashboard')
    dashboard.add_argument('--port',type=int,default=8766)
    dashboard.add_argument('--artifacts',default=str(ROOT/'artifacts'))
    chat=sub.add_parser('chat',help='Persistent synthetic conversation with saved case drafts')
    chat.add_argument('message');chat.add_argument('--thread',required=True);chat.add_argument('--request-key',required=True)
    chat.add_argument('--session',default='SESS-001');chat.add_argument('--transaction',action='append',default=[])
    chat.add_argument('--case');chat.add_argument('--account');chat.add_argument('--draft-id')
    chat.add_argument('--action',choices=['message','confirm','cancel'],default='message')
    chat.add_argument('--db',default='artifacts/conversation.sqlite3')
    chat.add_argument('--provider',choices=['mock','mock-v4','nebius'],default='mock-v4')
    index=sub.add_parser('index');index.add_argument('--output',default='artifacts/policy_chunks.json')
    publish=sub.add_parser('publish',help='Explicit future network action; never enabled implicitly')
    publish.add_argument('--dataset',default=str(ROOT/'data/evaluation_40.json'))
    publish.add_argument('--traces',required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='evaluate-security':
            from .security_evaluation import evaluate_security
            report=evaluate_security(args.output)
            print(json.dumps({'passed':report['passed'],'total':report['total'],'output':args.output}))
            return 0 if report['passed']==report['total'] else 2
        elif args.command=='ask':
            req=Request(message=args.message,session_id=args.session,transaction_ids=tuple(args.transaction),
                        case_id=args.case,account_id=args.account,confirmed=args.confirmed,request_key=args.request_key)
            result=Workflow(Backend(Store(args.db)),model=select_model(args.provider),engine=args.engine).run(req)
            print(json.dumps(sanitize(result),indent=2,ensure_ascii=False))
        elif args.command=='evaluate':
            if args.repeat<1 or args.repeat>20:
                raise ValueError('--repeat must be between 1 and 20')
            return evaluate(args)
        elif args.command=='chat':
            from .conversation import ConversationService,Turn
            turn=Turn(message=args.message,request_key=args.request_key,transaction_ids=args.transaction,
                      case_id=args.case,account_id=args.account,action=args.action,draft_id=args.draft_id)
            result=ConversationService(Backend(Store(args.db)),select_model(args.provider)).send(args.session,args.thread,turn)
            print(json.dumps(sanitize(result),indent=2,ensure_ascii=False))
        elif args.command=='index':
            path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
            PolicyIndex().save(path);print('Saved versioned local policy chunks to '+str(path))
        elif args.command=='semantic-eval':
            from .semantic_evaluation import evaluate_semantics
            report=evaluate_semantics(args.output,args.ragas,args.judge,args.dataset)
            print(json.dumps({'status':report['status'],'output':args.output}))
            return 0 if report['status']=='COMPLETE' else 2
        elif args.command=='verify-cloud':
            from .cloud_verify import verify_cloud
            print(json.dumps(verify_cloud(args.output,args.limit)))
        elif args.command=='dashboard':
            import os
            import uvicorn
            from .eval_config import load_eval_environment
            from .dashboard import create_dashboard
            load_eval_environment()
            if not os.environ.get('RESOLVEGUARD_DASHBOARD_TOKEN'):
                import secrets
                os.environ['RESOLVEGUARD_DASHBOARD_TOKEN']=secrets.token_urlsafe(32)
                print('Local dashboard access token: '+os.environ['RESOLVEGUARD_DASHBOARD_TOKEN'],flush=True)
            uvicorn.run(create_dashboard(args.artifacts),host='127.0.0.1',port=args.port,access_log=False)
        else:
            from .langsmith_integration import client_from_environment,upload_dataset,publish_trace
            client=client_from_environment()
            dataset=json.loads(Path(args.dataset).read_text(encoding='utf-8'))
            created=upload_dataset(dataset,client)
            for line in Path(args.traces).read_text(encoding='utf-8').splitlines():
                publish_trace(json.loads(line),client)
            print('Published synthetic draft dataset and sanitized mock traces: '+str(created.id))
        return 0
    except ValidationError as exc:
        # Pydantic errors can contain rejected secrets; display field paths/codes only.
        fields = [{'field':'.'.join(str(part) for part in e['loc']), 'code':e['type']}
                  for e in exc.errors(include_input=False,include_context=False,include_url=False)]
        print(json.dumps({'error':'VALIDATION_FAILED','fields':fields}),file=sys.stderr)
        return 2
    except (ValueError,RuntimeError,FileExistsError,PermissionError) as exc:
        print(str(exc),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
