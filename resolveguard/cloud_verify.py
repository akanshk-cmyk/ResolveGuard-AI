"""Opt-in cloud experiment with read-back evidence, never false local verification."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from .eval_config import ROOT, load_eval_environment
from .evaluation import fingerprint


def verify_cloud(output: str, limit: int = 3) -> dict:
    load_eval_environment()
    from .langsmith_integration import client_from_environment, upload_dataset, evaluate_in_langsmith
    from langsmith import tracing_context
    if not 1 <= limit <= 5:
        raise ValueError('Cloud smoke subset must contain 1-5 cases')
    path = Path(output)
    if path.exists():
        raise FileExistsError('Use a new cloud evidence path')
    dataset = json.loads((ROOT/'data/evaluation_40.json').read_text(encoding='utf-8'))
    dataset['cases'] = dataset['cases'][:limit]
    # Each smoke verification is an independent experiment, not an overwrite.
    dataset['verification_nonce'] = datetime.now(timezone.utc).isoformat()
    report = {'status':'NOT_VERIFIED', 'dataset_sha256':fingerprint(dataset),
              'cases':limit, 'provider':'MOCK', 'uploaded_content':'No prompts or financial records; execution structure and boolean checks only'}
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        client = client_from_environment()
        created = upload_dataset(dataset, client)
        report['dataset_id'] = str(created.id)
        # Explicit local target + hosted experiment, not remotely hosted inference.
        with tracing_context(enabled=True, client=client):
            experiment = evaluate_in_langsmith(created.name, dataset, client=client)
            experiment.wait()
        experiment_name = experiment.experiment_name
        report['experiment_name'] = experiment_name
        client.flush()
        remote_examples = list(client.list_examples(dataset_id=created.id))
        runs = list(client.list_runs(project_name=experiment_name, is_root=True))
        if len(remote_examples) != limit or len(runs) != limit:
            raise RuntimeError('Remote example/run count mismatch; retry verification after indexing')
        children = []
        step_names = set()
        for run in runs:
            tree = client.read_run(run.id, load_child_runs=True)
            if not tree.child_runs:
                raise RuntimeError('Remote nested workflow spans missing')
            if not run.feedback_stats:
                raise RuntimeError('Remote evaluator feedback missing')
            if run.inputs.get('message') != 'Synthetic evaluation case; customer text retained locally.':
                raise RuntimeError('Remote root input projection differs')
            if set(run.outputs or {}) - {'checks','passed','execution_mode','trace_ids'}:
                raise RuntimeError('Remote root output projection differs')
            pending = list(tree.child_runs)
            span_count = 0
            while pending:
                child = pending.pop()
                if child.inputs or set(child.outputs or {}) - {'execution_error'}:
                    raise RuntimeError('Remote child payload minimization failed')
                step_names.add(child.name)
                span_count += 1
                pending.extend(child.child_runs or [])
            children.append(span_count)
        if not {'classify','retrieve','template.explain'} <= step_names:
            raise RuntimeError('Required remote workflow stages missing')
        report.update(status='VERIFIED', experiment_name=experiment_name,
                      remote_examples=len(remote_examples), remote_runs=len(runs),
                      nested_span_counts=children)
    except Exception as exc:
        report['error_type'] = type(exc).__name__
        if not os.environ.get('LANGSMITH_API_KEY'):
            report['blocked_reason'] = 'LANGSMITH_API_KEY_NOT_CONFIGURED'
        raise RuntimeError('Cloud verification incomplete; inspect the local evidence status') from None
    finally:
        path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report
