"""Replay only ERROR metrics against identical saved public pilot inputs."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from resolveguard.eval_config import ROOT, evaluation_client, load_eval_environment
from resolveguard.ragas_eval import RAGAS_MAX_TOKENS, build_metrics, score_rag
from resolveguard.semantic_evaluation import prepare_samples


async def recover(source: dict) -> dict:
    dataset = json.loads((ROOT/'data/semantic_cases.json').read_text(encoding='utf-8'))
    current = {s['case_id']:s for s in prepare_samples(dataset)}
    pending = []
    for row in source['rows']:
        failed = [name for name, result in row.get('ragas', {}).items() if result['status']=='ERROR']
        if not failed:
            continue
        frozen = current[row['case_id']]
        for key in ('user_input','response','retrieved_contexts','reference'):
            if row[key] != frozen[key]:
                raise ValueError('Recovery inputs differ from current source-backed pilot')
        pending.append((row, failed))
    if not pending:
        raise ValueError('No technical metric failures; valid scores will not be retried')
    usage, rows = [], []
    client = evaluation_client(usage)
    try:
        from langsmith import tracing_context
        with tracing_context(enabled=False):
            metrics = build_metrics(client)
            for row, failed in pending:
                scores = await score_rag(row, {name:metrics[name] for name in failed})
                rows.append({'case_id':row['case_id'], 'ragas':scores})
    finally:
        await client.close()
    return {'status':'COMPLETE' if all(m['status']=='OK' for row in rows for m in row['ragas'].values()) else 'ERROR',
            'scope':'Technical metric recovery only; no valid low scores retried',
            'ragas_max_tokens':RAGAS_MAX_TOKENS, 'rows':rows, 'usage':usage}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True); parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError('Use a new recovery evidence path')
    load_eval_environment()
    os.environ['LANGSMITH_TRACING'] = 'false'
    os.environ['LANGCHAIN_TRACING_V2'] = 'false'
    os.environ['RESOLVEGUARD_CLOUD_TRACING'] = 'false'
    source = Path(args.source)
    report = asyncio.run(recover(json.loads(source.read_text(encoding='utf-8'))))
    report['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps({'status':report['status'], 'output':str(output)}))
    return 0 if report['status']=='COMPLETE' else 2


if __name__=='__main__':
    raise SystemExit(main())
