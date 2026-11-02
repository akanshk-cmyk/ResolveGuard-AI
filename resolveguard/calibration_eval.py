"""Record actual judge opinions; human calibration remains a separate workflow."""
from .configuration import DEFAULT_CHAT_MODEL
import asyncio
import json
import os
from pathlib import Path
from .eval_config import ROOT,load_eval_environment,evaluation_client
from .judges import grade_response
from .evaluation import fingerprint


async def evaluate_calibration(output):
    load_eval_environment();path=Path(output)
    if path.exists():raise FileExistsError('Choose a new calibration result path')
    source=json.loads((ROOT/'data/judge_calibration.json').read_text());rows=[]
    client=evaluation_client()
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        from langsmith import tracing_context
        with tracing_context(enabled=False):
            for case in source['cases']:
                account='customer balance' in case['question'].lower()
                contexts=case['contexts']+[json.dumps({'case_creation_status':'UNKNOWN','callback_status':'UNCONFIRMED','protective_action_status':'UNCONFIRMED'})]
                sample={'user_input':case['question'],'response':case['response'],'retrieved_contexts':contexts,
                    'reference':'Use only the supplied policy and execution evidence; no unsupported success or permissions.',
                    'authorization':{'data_scope':'ACCOUNT_SPECIFIC' if account else 'PUBLIC',
                        'authenticated':False if account else None,'authorized':False if account else None,'restricted_tools_called':False}}
                try:
                    judge=await asyncio.wait_for(grade_response(sample,client,os.environ.get('RESOLVEGUARD_JUDGE_MODEL',DEFAULT_CHAT_MODEL)),timeout=90)
                    row={'case_id':case['case_id'],'partition':case['partition'],'judge_passed':judge['grade']['passed'],'judge':judge,'status':'OK'}
                except Exception as exc:row={'case_id':case['case_id'],'judge_passed':None,'status':'ERROR','error_type':type(exc).__name__}
                rows.append(row)
                report={'status':'RUNNING' if len(rows)<len(source['cases']) else 'COMPLETE' if all(r['status']=='OK' for r in rows) else 'ERROR',
                        'dataset_sha256':fingerprint(source),'rows':rows,'calibration_status':'PENDING_HUMAN_CALIBRATION',
                        'scope':'Synthetic public policies and synthetic execution facts; no customer fixture records'}
                path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    finally:await client.close()
    return report


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    result=asyncio.run(evaluate_calibration(args.output));print(json.dumps({'status':result['status'],'cases':len(result['rows'])}))
