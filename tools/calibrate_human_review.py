"""Validate independently completed CSV labels against exact calibration sources."""
import argparse
import csv
import json
from pathlib import Path

from resolveguard.customer_review import fingerprint
from resolveguard.dataset_review import calibration_report

ROOT=Path(__file__).resolve().parents[1]


def import_reviews(cases, rows):
    sources={c['case_id']:c for c in cases}
    reviews=[];seen=set()
    for row in rows:
        cid=row['case_id']
        if cid not in sources or cid in seen:
            raise ValueError('Unknown or duplicate calibration case')
        seen.add(cid)
        if row['source_hash']!=fingerprint(sources[cid]):
            raise ValueError('Calibration source changed; review the current response')
        mark=row.get('human_mark','').strip().upper()
        if not mark:
            continue
        if mark not in {'PASS','FAIL'}:
            raise ValueError('Use PASS or FAIL, or leave an unclear case blank')
        if (not row.get('reviewer','').strip() or not row.get('note','').strip()
                or row.get('human_attestation','').strip().lower()!='true'):
            raise ValueError('A completed label requires a human reviewer, note and explicit true attestation')
        reviews.append({'case_id':cid,'source_hash':row['source_hash'],'verdict':'APPROVED',
                        'expected':{'passed':mark=='PASS'},'actor':row['reviewer'],'note':row['note']})
    return reviews


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--reviews',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output)
    if output.exists():raise FileExistsError('Use a new calibration report path')
    cases=json.loads((ROOT/'data/judge_calibration.json').read_text(encoding='utf-8'))['cases']
    with Path(args.reviews).open(encoding='utf-8-sig',newline='') as handle:
        reviews=import_reviews(cases,list(csv.DictReader(handle)))
    actual=json.loads((ROOT/'artifacts/local_completion/judge_calibration.json').read_text(encoding='utf-8'))
    if actual['dataset_sha256']!=fingerprint(json.loads((ROOT/'data/judge_calibration.json').read_text(encoding='utf-8'))):
        raise ValueError('Judge results do not match the calibration dataset')
    measured={r['case_id']:r.get('judge_passed') for r in actual['rows'] if r.get('status')=='OK'}
    report=calibration_report(cases,reviews,measured)
    report['label_source_sha256']=__import__('hashlib').sha256(Path(args.reviews).read_bytes()).hexdigest()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'human_model_pairs':report['human_model_pairs'],'agreement':report['agreement']}))


if __name__=='__main__':main()
