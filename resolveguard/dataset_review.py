"""Human-label and judge-calibration workflow. Never self-approves references."""
import json
from datetime import datetime,timezone
from pathlib import Path
from typing import Literal
from fastapi import Request,HTTPException
from .contracts import StrictModel,Identifier
from .customer_review import fingerprint


class LabelReview(StrictModel):
    suite:Identifier
    case_id:Identifier
    source_hash:Identifier
    verdict:Literal['APPROVED','REJECTED']
    expected:dict
    note:str
    human_attestation:bool


def install_dataset_review(app,store,staff,static):
    with store.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS dataset_label_reviews (
            review_id TEXT PRIMARY KEY,suite TEXT,case_id TEXT,source_hash TEXT,actor TEXT,
            reviewed_at TEXT,verdict TEXT,expected TEXT,note TEXT)''')
        for operation in ('UPDATE','DELETE'):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS labels_no_{operation.lower()} BEFORE {operation} ON dataset_label_reviews BEGIN SELECT RAISE(ABORT,'Label reviews are append-only'); END")

    def sources():
        from .bow_data import load_dataset
        from .full_evaluation import original_bindings
        root=Path(__file__).resolve().parents[1]
        bow,_=load_dataset()
        semantics=json.loads((root/'data/semantic_cases_expanded_v3.json').read_text())
        calibration=json.loads((root/'data/judge_calibration.json').read_text())
        return {'original-100':original_bindings()['cases'],'BOW-100':bow['evaluations'],
                'semantic-expanded':semantics['cases'],'judge-calibration':calibration['cases']}

    @app.get('/api/reviewer/datasets')
    def datasets(request:Request):
        staff(request,admin=True)
        with store.connect() as db:reviews=[dict(r) for r in db.execute('SELECT * FROM dataset_label_reviews ORDER BY rowid')]
        suites=[]
        for name,rows in sources().items():
            items=[]
            for row in rows:
                cid=row.get('case_id',row.get('eval_id'));digest=fingerprint(row)
                matches=[r for r in reviews if r['suite']==name and r['case_id']==cid and r['source_hash']==digest]
                items.append({'case_id':cid,'source_hash':digest,'source':row,'review':matches[-1] if matches else None})
            suites.append({'suite':name,'items':items})
        return {'suites':suites,'qualification':'PENDING until human-reviewed references and critical checks pass'}

    @app.post('/api/reviewer/datasets/review')
    def review(body:LabelReview,request:Request):
        actor=staff(request,admin=True)
        if not body.human_attestation or not body.note.strip() or len(body.note)>4000:raise HTTPException(422,'A person must attest to the review and provide a note')
        row=next((r for r in sources().get(body.suite,[]) if r.get('case_id',r.get('eval_id'))==body.case_id),None)
        if row is None or fingerprint(row)!=body.source_hash:raise HTTPException(409,'Source changed; reload before reviewing')
        from .reviewer import masked
        item={'suite':body.suite,'case_id':body.case_id,'source_hash':body.source_hash,'actor':actor['user_id'],
              'reviewed_at':datetime.now(timezone.utc).isoformat(),'verdict':body.verdict,'expected':body.expected,'note':masked(body.note)}
        rid='label-'+fingerprint(item)
        with store.connect() as db:db.execute('INSERT INTO dataset_label_reviews VALUES(?,?,?,?,?,?,?,?,?)',
            (rid,body.suite,body.case_id,body.source_hash,actor['user_id'],item['reviewed_at'],body.verdict,json.dumps(body.expected),item['note']))
        return {'review_id':rid,'source_unchanged':True,'qualification':'A label review does not override test failures or approve release'}

    @app.get('/api/reviewer/calibration')
    def calibration(request:Request):
        staff(request,admin=True)
        with store.connect() as db:rows=[dict(r) for r in db.execute("SELECT * FROM dataset_label_reviews WHERE suite='judge-calibration' ORDER BY rowid")]
        cases=sources()['judge-calibration']
        path=Path(__file__).resolve().parents[1]/'artifacts/local_completion/judge_calibration.json'
        if path.exists():
            measured={r['case_id']:r.get('judge_passed') for r in json.loads(path.read_text())['rows']}
            # Source hashes bind human reviews to original examples, not opinions.
            result=calibration_report(cases,rows,measured)
            result['model_results_available']=len(measured)
            return result
        return calibration_report(cases,rows)


def calibration_report(cases,reviews,measured=None):
    pairs=[];comparisons=[];invalid=[]
    for case in cases:
        matching=[r for r in reviews if r['case_id']==case['case_id'] and r['source_hash']==fingerprint(case)]
        prediction=measured.get(case['case_id']) if measured is not None else case.get('judge_passed')
        if prediction is not None and type(prediction) is not bool:
            invalid.append(case['case_id'])
        if matching and matching[-1]['verdict']=='APPROVED' and type(prediction) is bool:
            expected=matching[-1]['expected'];expected=json.loads(expected) if isinstance(expected,str) else expected
            if type(expected.get('passed')) is bool:
                pairs.append((expected['passed'],prediction))
                comparisons.append({'case_id':case['case_id'],'partition':case.get('partition','UNSPECIFIED'),
                                    'human_passed':expected['passed'],'judge_passed':prediction,
                                    'agrees':expected['passed']==prediction,'review_note':matching[-1].get('note','')})
    def measures(selected):
        tp=sum(a and b for a,b in selected);tn=sum(not a and not b for a,b in selected)
        fp=sum(not a and b for a,b in selected);fn=sum(a and not b for a,b in selected)
        return {'true_passes':tp,'true_failures':tn,'false_passes':fp,'false_failures':fn,
                'true_positive_rate':tp/(tp+fn) if tp+fn else None,
                'true_negative_rate':tn/(tn+fp) if tn+fp else None}
    return {'status':'COMPLETE' if pairs and len(pairs)==len(cases) else 'PENDING_HUMAN_CALIBRATION',
            'human_model_pairs':len(pairs),'total':len(cases),'agreement':sum(a==b for a,b in pairs)/len(pairs) if pairs else None,
            **measures(pairs),'comparisons':comparisons,'invalid_judge_case_ids':invalid,
            'partition_metrics':{p:measures([(c['human_passed'],c['judge_passed']) for c in comparisons if c['partition']==p])
                                 for p in sorted({c['partition'] for c in comparisons})},
            'release_gate_enabled':False,'gate_note':'Human agreement does not grant banking permissions or release approval.'}
