"""Reuse only identical measured inputs; never retry a valid low score."""
import argparse
import hashlib
import json
from pathlib import Path
from resolveguard.evaluation import fingerprint
from resolveguard.semantic_evaluation import prepare_samples
from resolveguard.telemetry import sanitize


def merge(dataset_path,base_path,correction_path,output):
    dataset=json.loads(Path(dataset_path).read_text(encoding='utf-8'))
    base=json.loads(Path(base_path).read_text(encoding='utf-8'))
    correction=json.loads(Path(correction_path).read_text(encoding='utf-8'))
    rows=[]
    for sample in prepare_samples(dataset):
        safe=sanitize(sample);match=None
        for source,path in ((correction,correction_path),(base,base_path)):
            for row in source['rows']:
                keys=('user_input','response','reference','retrieved_contexts','authorization','execution_context','product_id')
                if row['case_id']==sample['case_id'] and all(safe[k]==row[k] for k in keys):
                    match=dict(row,measurement_file=Path(path).name,measurement_inputs_verified=True)
                    break
            if match:break
        if match is None:raise ValueError('No exact-input measurement for '+sample['case_id'])
        rows.append(match)
    result={'status':'COMPLETE' if all(r['status']=='OK' for r in rows) else 'ERROR',
        'dataset_version':dataset['version'],'dataset_sha256':fingerprint(dataset),'reference_review_status':'PENDING',
        'scope':'12 synthetic public-policy cases; retained exact-input measurements with one corrected product binding',
        'rows':rows,'judge_passed':sum(r.get('judge',{}).get('grade',{}).get('passed',False) for r in rows),
        'quality_review_flags':[{'case_id':r['case_id'],'metric':k,'score':v['score']} for r in rows for k,v in r.get('ragas',{}).items() if k in ('context_recall','context_precision','faithfulness') and v.get('score',0)<.98],
        'source_measurements':[{'file':Path(p).name,'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in (base_path,correction_path)],
        'qualification':'BLOCKED_PENDING_HUMAN_REFERENCE_AND_JUDGE_CALIBRATION'}
    path=Path(output)
    if path.exists():raise FileExistsError('Choose a new output path; prior measurements are preserved')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',required=True);p.add_argument('--base',required=True);p.add_argument('--correction',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();r=merge(args.dataset,args.base,args.correction,args.output);print(json.dumps({'status':r['status'],'cases':len(r['rows']),'judge_passed':r['judge_passed']}))
