"""Import actual human annotations into a NEW dataset version. Never auto-approve."""
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path

KNOWN_ORIGINS={'human_authored','llm_generated','synthetic_from_real_seed','public_benchmark'}


def apply_review(dataset, rows):
    ids=[r['case_id'] for r in rows]
    if len(set(ids))!=len(ids) or set(ids)!={c['case_id'] for c in dataset['cases']}:
        raise ValueError('Review rows must match dataset case IDs exactly, without duplicates')
    output=copy.deepcopy(dataset)
    by_id={r['case_id']:r for r in rows}
    for case in output['cases']:
        row=by_id[case['case_id']]
        if row['prompt']!=case['inputs']['message']:
            raise ValueError('Review must not silently change a source prompt')
        if json.loads(row['fixture_inputs'])!=case['inputs'] or json.loads(row['faults'])!=case['faults']:
            raise ValueError('Change fixture bindings in a separately versioned dataset, not in the review import')
        status=row['human_review_status'].upper()
        if status not in ('PENDING','APPROVED','REJECTED'):
            raise ValueError('Review status must be PENDING, APPROVED or REJECTED')
        if status!='PENDING' and (not row['reviewer'].strip() or not row['review_notes'].strip()):
            raise ValueError('A completed human review requires reviewer and review notes')
        expected=json.loads(row['expected_assertions'])
        if set(expected)!=set(case['expected']):
            raise ValueError('Expected assertion keys must be preserved')
        if expected['primary_intent']!=row['expected_intent']:
            raise ValueError('Expected intent and assertion JSON must agree')
        if expected!=case['expected'] and status!='APPROVED':
            raise ValueError('Changes to expected truth require an explicit reviewed annotation')
        case['expected']=expected
        case['metadata'].update({'human_review_status':status,'reviewer':row['reviewer'] or None,
                                 'review_notes':row['review_notes'],
                                 'prompt_origin':row['prompt_origin'],
                                 'provenance_notes':row['provenance_notes']})
    cases=output['cases']
    provenance_known=all(c['metadata']['prompt_origin'] in KNOWN_ORIGINS and
                         c['metadata']['provenance_notes'].strip() for c in cases)
    generated=sum(c['metadata']['prompt_origin']=='llm_generated' for c in cases)
    compliant=provenance_known and generated/len(cases)<.2
    reviewed=all(c['metadata']['human_review_status']=='APPROVED' for c in cases)
    output['provenance_status']='ATTESTED' if compliant else 'UNRESOLVED_OR_GENERATED_SHARE_EXCEEDS_LIMIT'
    output['qualification_status']='REVIEWED_DRAFT_FOR_EVALUATION' if compliant and reviewed else 'DRAFT_REQUIRES_REVIEW_OR_PROVENANCE'
    output['dataset_version']=dataset['dataset_version']+'-reviewed-v2'
    output['review_import_note']='Human annotations supplied externally; no claim of independent expert certification'
    return output


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dataset',default='data/evaluation_40.json')
    parser.add_argument('--review',default='data/review_40.csv')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    target=Path(args.output)
    if target.exists():raise FileExistsError('Review output must be a new versioned file')
    dataset=json.loads(Path(args.dataset).read_text(encoding='utf-8'))
    with Path(args.review).open(encoding='utf-8-sig',newline='') as handle:rows=list(csv.DictReader(handle))
    result=apply_review(dataset,rows)
    result['review_csv_sha256']=hashlib.sha256(Path(args.review).read_bytes()).hexdigest()
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(result['qualification_status']+'; '+result['provenance_status'])


if __name__=='__main__':main()
