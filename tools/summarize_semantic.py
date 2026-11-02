"""Readable pilot report, retaining initial failures and explicit recovery lineage."""
import argparse
import copy
import csv
import hashlib
import html
import json
from pathlib import Path

METRICS = ('context_recall','context_precision','faithfulness','answer_relevance')
NOTES = [
    'The monthly-fee answer states $6 without the waiver conditions. The banking judge marked policy completeness for review.',
    'The waiver answer includes capability and privacy guidance absent from its retrieved product terms. A low faithfulness score here signals incomplete supporting evidence; it is not proof that the guidance is false.',
    'These are three public-information cases with draft references. They do not establish production readiness or test private-account authorization, fraud handling or the full 100-case BOW suite.',
    'The existing application generated the answers using templates. GLM-5.3-Flash evaluated them; this is not a benchmark of live GLM answer generation.',
    'Run 01 is retained before correcting evaluator metadata and judge output limits. Run 02 is the corrected pilot. Later recovery replays technical ERROR metrics only; its valid low scores are retained unchanged. These evaluator changes do not demonstrate an improvement to application answers.',
]


def summarize(directory: Path, recovery_name: str | None = None) -> dict:
    source = directory/'run_02.json'
    original = json.loads(source.read_text(encoding='utf-8'))
    rows = copy.deepcopy(original['rows'])
    files = [directory/'run_01.json', source]
    failed_recovery = directory/'metric_recovery_01.json'
    if failed_recovery.exists():
        files.append(failed_recovery)
    if recovery_name:
        recovery_path = directory/recovery_name
        recovery = json.loads(recovery_path.read_text(encoding='utf-8'))
        if recovery['source_sha256'] != hashlib.sha256(source.read_bytes()).hexdigest():
            raise ValueError('Recovery does not reference this frozen source run')
        for recovered in recovery['rows']:
            row = next(r for r in rows if r['case_id']==recovered['case_id'])
            for metric, value in recovered['ragas'].items():
                if row['ragas'][metric]['status'] != 'ERROR':
                    raise ValueError('Cannot replace a valid metric score')
                row['ragas'][metric] = value
        files.append(recovery_path)
    scores = [{ 'case_id':r['case_id'], 'question':r['user_input'],
                'metrics':r['ragas'], 'judge':r.get('judge', {})} for r in rows]
    complete = all(all(r['metrics'][m]['status']=='OK' for m in METRICS) and 'grade' in r['judge'] for r in scores)
    models = {}
    for path in files:
        for event in json.loads(path.read_text(encoding='utf-8')).get('usage', []):
            model = event.get('model', 'unknown')
            counts = models.setdefault(model, {'requests':0,'input_tokens':0,'output_tokens':0,'missing_usage_requests':0})
            counts['requests'] += 1
            if type(event.get('input_tokens')) is int and type(event.get('output_tokens')) is int:
                counts['input_tokens'] += event['input_tokens']; counts['output_tokens'] += event['output_tokens']
            else:
                counts['missing_usage_requests'] += 1
    result = {'execution_status':'COMPLETE_WITH_RECOVERY' if complete and recovery_name else 'COMPLETE' if complete else 'INCOMPLETE',
              'review_status':original['review_status'], 'judge_passes':sum(r['judge'].get('grade', {}).get('passed', False) for r in scores),
              'case_count':len(scores), 'judge_model':original['judge_model'], 'embedding_model':original['embedding_model'],
              'source_sha256':original['source_sha256'], 'dataset_sha256':original['dataset_sha256'],
              'evidence_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
              'usage_including_failed_attempts':models, 'rows':scores, 'review_notes':NOTES}
    (directory/'summary.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    with (directory/'scores.csv').open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.writer(handle)
        writer.writerow(['case_id', *METRICS, 'judge_pass', 'tone_score', 'policy_score', 'guardrail_score'])
        for row in scores:
            grade = row['judge'].get('grade', {})
            writer.writerow([row['case_id'], *[row['metrics'][m]['score'] for m in METRICS], grade.get('passed'),
                             *[grade.get(k, {}).get('score') for k in ('tone_empathy','policy_compliance','guardrail_integrity')]])
    esc = html.escape
    table = []
    details = []
    for row in scores:
        grade = row['judge'].get('grade', {})
        cells = ''.join('<td>'+('Unavailable' if row['metrics'][m]['score'] is None else f"{row['metrics'][m]['score']*100:.1f}%")+'</td>' for m in METRICS)
        table.append(f"<tr><td>{esc(row['case_id'])}</td>{cells}<td>{'Pass' if grade.get('passed') else 'Needs review'}</td></tr>")
        dimensions = ''.join(f"<li><strong>{esc(key.replace('_',' ').capitalize())}: {value['score']}/5.</strong> {esc(value['reasoning'])}</li>" for key,value in grade.items() if isinstance(value,dict))
        details.append(f"<details><summary>{esc(row['case_id'])}: {esc(row['question'])}</summary><ul>{dimensions}</ul></details>")
    document = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ResolveGuard semantic pilot</title><style>body{{font:16px/1.6 system-ui;background:#f4f7f6;color:#173336;margin:0}}main{{max-width:1100px;margin:auto;padding:24px}}section,details{{background:white;padding:20px;margin:20px 0;border:1px solid #d6e1de;border-radius:10px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #ddd}}.scroll{{overflow:auto}}summary{{cursor:pointer}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}</style><main>
<h1>ResolveGuard: three-case semantic pilot</h1><p>Execution: <strong>{esc(result['execution_status'])}</strong>. Banking rubric: {result['judge_passes']}/{len(scores)} pass. Reference review: {esc(original['review_status'])}.</p>
<p>Live evaluator: {esc(original['judge_model'])}. Embeddings: {esc(original['embedding_model'])}. LangSmith publishing remained off.</p>
<section><h2>Measured scores</h2><p>Scores range from 0–100%; higher is better. These are individual draft test cases, not a production quality estimate.</p><div class="scroll"><table><tr><th>Case</th><th>Context recall</th><th>Context precision</th><th>Faithfulness</th><th>Answer relevance</th><th>Banking judge</th></tr>{''.join(table)}</table></div></section>
<section><h2>What needs attention</h2><ul>{''.join('<li>'+esc(note)+'</li>' for note in NOTES)}</ul></section>
{''.join(details)}<section><h2>API usage, including failed attempts</h2><pre>{esc(json.dumps(models,indent=2))}</pre><p>Token usage is provider-reported. Billing has not been reconciled.</p></section>
<section><h2>Evidence</h2><ul>{''.join('<li><a href="'+esc(p.name)+'">'+esc(p.name)+'</a></li>' for p in files)}</ul><p>Source-linked scores are also available in <a href="scores.csv">scores.csv</a> and <a href="summary.json">summary.json</a>.</p></section></main></html>'''
    (directory/'report.html').write_text(document, encoding='utf-8')
    return result


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path); parser.add_argument('--recovery')
    args = parser.parse_args()
    result = summarize(args.directory, args.recovery)
    print(json.dumps({'status':result['execution_status'], 'judge_passes':result['judge_passes'], 'cases':result['case_count']}))
