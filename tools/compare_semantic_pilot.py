"""Compare the approved answer/evidence fixes without overwriting the pilot baseline."""
import hashlib
import html
import json
from pathlib import Path
from resolveguard.eval_config import ROOT


def main():
    directory=ROOT/'artifacts/semantic_pilot_20261031'
    before_path=directory/'summary.json'; after_path=directory/'run_03.json'
    before=json.loads(before_path.read_text(encoding='utf-8'))
    after=json.loads(after_path.read_text(encoding='utf-8'))
    if before['dataset_sha256']!=after['dataset_sha256'] or before['source_sha256']!=after['source_sha256']:
        raise ValueError('Comparison requires the same reference dataset and workbook snapshot')
    old={r['case_id']:r for r in before['rows']}
    rows=[]
    for row in after['rows']:
        baseline=old[row['case_id']]
        rows.append({'case_id':row['case_id'],'question':row['user_input'],'answer':row['response'],
                     'sources':row['retrieved_chunk_ids'],
                     'before':{'metrics':{k:v['score'] for k,v in baseline['metrics'].items()},
                               'judge_passed':baseline['judge']['grade']['passed']},
                     'after':{'metrics':{k:v['score'] for k,v in row['ragas'].items()},
                              'judge':row['judge'], 'execution_context':row['execution_context']}})
    report={'execution_status':after['status'], 'judge_passes_before':before['judge_passes'],
            'judge_passes_after':sum(r['after']['judge']['grade']['passed'] for r in rows),
            'cases':len(rows), 'references_unchanged':True,
            'baseline_sha256':hashlib.sha256(before_path.read_bytes()).hexdigest(),
            'after_sha256':hashlib.sha256(after_path.read_bytes()).hexdigest(),
            'comparison_limit':'Answers and evidence coverage changed together. Faithfulness now also uses explicit execution-state facts; this is not an isolated model-quality comparison.',
            'review_status':after['review_status'], 'rows':rows}
    (directory/'post_fix_summary.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (directory/'llm_as_judge_results_after.json').write_text(json.dumps({
        'source_file':'run_03.json','source_sha256':report['after_sha256'],
        'judge_model':after['judge_model'],'cases':[{'case_id':r['case_id'],
            'question':r['question'],'answer':r['answer'],'judge':r['after']['judge']} for r in rows]},indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    esc=html.escape
    def pct(value):return 'Unavailable' if value is None else f'{value*100:.1f}%'
    table=''.join('<tr><td>'+esc(r['case_id'])+'</td>'+''.join('<td>'+pct(r['after']['metrics'][m])+'</td>' for m in (
        'context_recall','context_precision','faithfulness','answer_relevance'))+
        '<td>'+('Pass' if r['after']['judge']['grade']['passed'] else 'Needs review')+'</td></tr>' for r in rows)
    answers=''.join('<section><h2>'+esc(r['question'])+'</h2><p class="answer">'+esc(r['answer'])+
        '</p><p>Sources: '+esc(', '.join(r['sources']))+'</p><p>Banking judge: '+esc(str(r['after']['judge']['grade']['policy_compliance']['score']))+'/5 for policy compliance.</p></section>' for r in rows)
    page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>ResolveGuard — verified answer fixes</title>
<style>body{{font:16px/1.6 system-ui;background:#f4f7f6;color:#173336;margin:0}}main{{max-width:1100px;padding:24px;margin:auto}}section{{background:white;padding:20px;margin:18px 0;border:1px solid #d6e1de;border-radius:12px}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #ddd}}table{{border-collapse:collapse;width:100%}}.scroll{{overflow:auto}}.answer{{white-space:pre-wrap}}</style><main>
<h1>ResolveGuard: verified answer fixes</h1><p>Banking judge: {report['judge_passes_before']}/{len(rows)} before → {report['judge_passes_after']}/{len(rows)} after. Execution: {esc(after['status'])}.</p>
<p>Same three questions and draft reference answers. Existing baseline files were preserved. Live evaluation uses {esc(after['judge_model'])} and {esc(after['embedding_model'])}; customer chat remains mock-routed.</p>
<section><h2>Changes</h2><ul><li>Checking-fee answers include product-specific waiver conditions.</li><li>Privacy guidance cites current public privacy policy chunks.</li><li>Execution facts are separate from bank-policy retrieval. Safe access outcomes reach the judge without credentials or customer identifiers.</li></ul></section>
<section><h2>Measured results</h2><div class="scroll"><table><tr><th>Case</th><th>Recall</th><th>Precision</th><th>Faithfulness</th><th>Relevance</th><th>Judge</th></tr>{table}</table></div><p>{esc(report['comparison_limit'])}</p><p>Only three public cases; reference review remains PENDING. These results do not establish production readiness or prove private-account authorization.</p></section>
{answers}<section><h2>Evidence downloads</h2><ul><li><a href="llm_as_judge_results_after.json">Updated LLM-as-judge results</a></li><li><a href="run_03.json">Full measured run</a></li><li><a href="post_fix_summary.json">Before/after comparison JSON</a></li><li><a href="report.html">Original pilot report</a></li></ul></section></main></html>'''
    (directory/'post_fix_report.html').write_text(page,encoding='utf-8')
    print(json.dumps({'status':after['status'],'judge_passes_after':report['judge_passes_after'],'cases':len(rows)}))


if __name__=='__main__':main()
