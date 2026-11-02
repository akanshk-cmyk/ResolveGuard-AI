"""Explicit opt-in publishing of already-sanitized evidence; inert on import."""
import os
from datetime import datetime
from .telemetry import sanitize
from .evaluation import fingerprint
from .cloud_privacy import cloud_trace

REMOTE_MESSAGE = 'Synthetic evaluation case; customer text retained locally.'


def client_from_environment():
    if not os.environ.get('LANGSMITH_API_KEY'):
        raise RuntimeError('LANGSMITH_API_KEY is required only for explicit publishing')
    try:
        from langsmith import Client
    except ImportError as exc:
        raise RuntimeError('Install requirements.txt to enable LangSmith publishing') from exc
    endpoint = os.environ.get('LANGSMITH_ENDPOINT', 'https://api.smith.langchain.com')
    if endpoint not in {'https://api.smith.langchain.com', 'https://eu.api.smith.langchain.com'}:
        raise ValueError('Use an approved LangSmith HTTPS endpoint')
    return Client(api_url=endpoint, hide_inputs=sanitize, hide_outputs=sanitize,
                  auto_batch_tracing=False, omit_traced_runtime_info=True)


def upload_dataset(dataset, client=None):
    client = client or client_from_environment()
    name = 'resolveguard-draft-'+fingerprint(dataset)[:12]
    # New versioned dataset only; never silently update a frozen dataset.
    created = client.create_dataset(dataset_name=name, description=(
        'Synthetic draft ResolveGuard cases. Human review and provenance attestation pending.'))
    client.create_examples(dataset_id=created.id,
        inputs=[{'case_id':f'CASE-{i:03d}','message':REMOTE_MESSAGE} for i,c in enumerate(dataset['cases'])],
        outputs=[{'reference_retained_locally':True} for c in dataset['cases']],
        metadata=[{'synthetic':True, 'human_review':'PENDING'} for c in dataset['cases']])
    return created


def publish_trace(trace, client=None, parent=None):
    client = client or client_from_environment()
    try:
        from langsmith.run_trees import RunTree
    except ImportError as exc:
        raise RuntimeError('LangSmith SDK is not installed') from exc
    trace = cloud_trace(trace)
    parents = {}
    root = None
    for span in trace['spans']:
        args = dict(name=span['name'],run_type=span['run_type'],
                    inputs=span['inputs'],start_time=datetime.fromisoformat(span['start_time']),
                    extra={'metadata':trace['metadata']})
        if span['parent_id']:
            run = parents[span['parent_id']].create_child(**args)
        elif parent is not None:
            run = parent.create_child(**args)
            root = run
        else:
            run = RunTree(id=span['id'],project_name=os.environ.get('LANGSMITH_PROJECT','resolveguard-demo-eval'),
                          client=client,**args)
            root = run
        parents[span['id']] = run
        run.post()
        run.end(outputs=span['outputs'],error=span['error'],
                end_time=datetime.fromisoformat(span['end_time']))
        run.patch()
    return root


def evaluate_in_langsmith(dataset_name, dataset, engine='langgraph', client=None):
    """Future credentialed SDK evaluation. Same inputs/oracles, no live GLM claims.

    This target still uses MockModel. A live Nebius adapter is intentionally not
    included in the authorized credential-free implementation.
    """
    client = client or client_from_environment()
    from tempfile import TemporaryDirectory
    from .evaluation import execute_case
    cases = {f'CASE-{i:03d}':c for i,c in enumerate(dataset['cases'])}

    def target(inputs, langsmith_extra=None):
        case = cases[inputs['case_id']]
        if inputs['message'] != REMOTE_MESSAGE:
            raise ValueError('Remote case differs from the frozen local dataset')
        with TemporaryDirectory() as temp:
            result = execute_case(case,temp,engine=engine)
            from langsmith.run_helpers import get_current_run_tree
            parent = get_current_run_tree()
            for attempt in result['attempts']:
                publish_trace(attempt['trace'],client,parent=parent)
            return {'checks':result['checks'], 'passed':result['passed'],
                    'execution_mode':'MOCK', 'trace_ids':[a['trace']['trace_id'] for a in result['attempts']]}

    def route_score(run, example):
        return {'key':'routing_exact','score':run.outputs['checks']['routing_exact']}

    def deterministic_score(run, example):
        return {'key':'deterministic_journey','score':run.outputs['passed']}

    return client.evaluate(target,data=dataset_name,evaluators=[route_score,deterministic_score],
                           experiment_prefix='resolveguard-MOCK-workflow',max_concurrency=1,
                           metadata={'execution_mode':'MOCK','dataset_sha256':fingerprint(dataset),
                                     'scope':'Deterministic mock assertions; not measured GLM quality'})
