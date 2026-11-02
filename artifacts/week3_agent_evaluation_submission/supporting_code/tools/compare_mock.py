"""Four controlled mock-rule experiments on identical draft cases; no APIs."""
import argparse,json,sys
import socket
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from resolveguard.evaluation import execute_case,summarize,fingerprint
from resolveguard.model import TunedMockModel


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='artifacts/mock_improvements')
    parser.add_argument('--repeat',type=int,default=3);args=parser.parse_args()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    dataset=json.loads((ROOT/'data/evaluation_40.json').read_text(encoding='utf-8'))
    code_hash=fingerprint({p.name:p.read_text(encoding='utf-8') for p in (ROOT/'resolveguard').glob('*.py')})
    changes=[('baseline','Unmodified mock rules'),
             ('indirect-fraud','Recognize indirect unauthorized activity; predicted fraud recall and report preservation increase'),
             ('human-language','Recognize human/fraud-support phrasing; predicted human flag and routing improve'),
             ('case-language','Recognize ticket creation and duplicate-submit language; predicted case completion improves'),
             ('primary-intent','Prefer requested account facts over incidental rules wording; predicted adversarial routing improves')]
    experiments=[];prior=None;baseline_rows=None
    for stage,(name,hypothesis) in enumerate(changes):
        folder=output/f'v{stage}';folder.mkdir()
        with patch.object(socket.socket,'connect',side_effect=AssertionError('Mock experiments must remain offline')):
            rows=[execute_case(case,folder,'langgraph',repeat,TunedMockModel(stage))
                  for case in dataset['cases'] for repeat in range(args.repeat)]
        summary=summarize(rows,dataset,'langgraph')
        summary['code_sha256']=code_hash
        metric=summary['metrics']
        delta={key:metric[key]-prior[key] for key in ('intent_accuracy','deterministic_journey_pass_rate','fraud_recall')} if prior else {}
        keyed={(r['case_id'],r['repeat_index']):r for r in rows}
        regressions=[] if prior is None else [k[0] for k,row in keyed.items() if old_keyed[k]['passed'] and not row['passed']]
        experiments.append({'version':f'v{stage}','change':name,'hypothesis':hypothesis,
                            'metrics':metric,'delta_from_previous':delta,'regressions':sorted(set(regressions))})
        (folder/'results.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
        (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
        prior=metric;old_keyed=keyed
        if stage==0:baseline_rows=rows
    failed={r['case_id'] for r in baseline_rows if not r['passed']}
    (output/'regression_cases.json').write_text(json.dumps({'status':'Observed mock failures; original human-review status retained',
        'source_dataset_sha256':fingerprint(dataset),'cases':[c for c in dataset['cases'] if c['case_id'] in failed]},indent=2)+'\n',encoding='utf-8')
    report={'status':'MOCK_ONLY: not GLM improvement evidence; labels and provenance pending',
            'dataset_sha256':fingerprint(dataset),'code_sha256':code_hash,'cases':40,'repeats':args.repeat,'experiments':experiments,
            'remaining_failures':sorted({r['case_id'] for r in rows if not r['passed']}),
            'next':'Review policy retrieval failure and human labels; repeat iteration on a real model only after explicit provider setup'}
    (output/'comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
