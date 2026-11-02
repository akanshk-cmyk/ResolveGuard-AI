"""Read-only localhost operations view, isolated from customer authentication."""
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from .eval_config import ROOT
from .cloud_privacy import cloud_trace
from .monitoring import read_observations


def read_json(path: Path, root: Path):
    if not path.resolve().is_relative_to(root.resolve()) or path.stat().st_size > 8_000_000:
        raise ValueError('Artifact outside allowed root or too large')
    return json.loads(path.read_text(encoding='utf-8'))


def collect_runs(root: Path) -> tuple[list[dict], dict]:
    runs, locations = [], {}
    for directory, folders, files in os.walk(root, followlinks=False):
        folders[:] = [f for f in folders if not f.startswith(('ui-browser-profile', '.'))]
        if len(runs) >= 250:
            break
        if 'summary.json' not in files:
            continue
        path = Path(directory)/'summary.json'
        try:
            data = read_json(path, root)
            if not isinstance(data, dict) or not isinstance(data.get('metrics'), dict):
                continue
            run_id = hashlib.sha256(str(path.relative_to(root)).encode()).hexdigest()[:16]
            allowed = ('intent_accuracy', 'deterministic_journey_pass_rate', 'fraud_recall',
                       'p95_local_mock_latency_ms', 'model_cost_usd', 'token_usage')
            runs.append({'id':run_id, 'label':path.parent.name,
                         'modified_at':path.stat().st_mtime,
                         'run_type':data.get('run_type'),
                         'metrics':{k:data['metrics'].get(k) for k in allowed},
                         'dataset_sha256':data.get('dataset_sha256'),
                         'code_sha256':data.get('code_sha256'),
                         'fixture_sha256':data.get('fixture_sha256'),
                         'cases_executed':data.get('cases_executed'),
                         'qualification':data.get('demo_release_decision',data.get('release_decision')),
                         'human_review_pending':data.get('human_review_pending'),
                         'source_contract_conflicts':data.get('source_contract_conflicts',0),
                         'failure_counts':data.get('failure_counts', {})})
            semantic_path = path.parent/'semantic_results.json'
            if semantic_path.exists():
                semantic = read_json(semantic_path, root)
                runs[-1]['semantic'] = {'status':semantic.get('status'),
                    'dataset_sha256':semantic.get('dataset_sha256'),
                    'scope':semantic.get('scope'),
                    'cases':[{'case_id':row.get('case_id'), 'ragas':row.get('ragas'),
                              'judge_passed':row.get('judge', {}).get('grade', {}).get('passed')}
                             for row in semantic.get('rows', [])]}
            locations[run_id] = path.parent
        except (OSError, ValueError, TypeError):
            continue
    return sorted(runs, key=lambda r:r['modified_at']), locations


def create_dashboard(artifacts=None, token=None, monitor_db=None, review_database=None):
    root = Path(artifacts or ROOT/'artifacts').resolve()
    token = token or os.environ.get('RESOLVEGUARD_DASHBOARD_TOKEN')
    if not token or len(token) < 24:
        raise ValueError('Set RESOLVEGUARD_DASHBOARD_TOKEN to at least 24 characters')
    app = FastAPI(title='ResolveGuard Operations', docs_url=None, redoc_url=None, openapi_url=None)
    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):return JSONResponse(status_code=422,content={'detail':'Please check the review form fields and try again.'})
    from .reviewer import install_reviewer
    install_reviewer(app,review_database or root/'web.sqlite3',token)

    def authorize(request):
        supplied = request.headers.get('authorization', '').removeprefix('Bearer ')
        if not hmac.compare_digest(supplied.encode(), token.encode()):
            raise HTTPException(401, 'Dashboard access token required')

    @app.middleware('http')
    async def secure_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.get('/')
    def index():
        return FileResponse(ROOT/'resolveguard/static/operations.html')

    @app.get('/operations.js')
    def script():
        return FileResponse(ROOT/'resolveguard/static/operations.js')

    @app.get('/operations.css')
    def style():
        return FileResponse(ROOT/'resolveguard/static/operations.css')

    @app.get('/api/operations')
    def operations(request: Request):
        authorize(request)
        runs, _ = collect_runs(root)
        try:
            events = read_observations(monitor_db or os.environ.get('RESOLVEGUARD_MONITOR_DB') or str(root/'operations.sqlite3'))
        except (OSError, ValueError, TypeError):
            events = []
        workflow_events=[e for e in events if e.get('journey_scope','WORKFLOW')=='WORKFLOW']
        chat_events=[e for e in events if e.get('journey_scope') in {'/api/chat','/api/auth/resume'}]
        journey_events=chat_events or workflow_events
        durations = sorted(e['latency_ms'] for e in journey_events)
        p95 = durations[max(0, math.ceil(.95*len(durations))-1)] if durations else None
        errors = sum(e['error_count']>0 for e in journey_events)
        generations=[e['generation'] for e in events if e.get('journey_scope')=='GENERATION' and e.get('generation')]
        generation_times=sorted(g['generation_latency_ms'] for g in generations if isinstance(g.get('generation_latency_ms'),(int,float)))
        generation_p95=generation_times[max(0,math.ceil(.95*len(generation_times))-1)] if generation_times else None
        alerts = []
        if sum(e['error_count']>0 for e in events[:20]) >= 3:
            alerts.append({'code':'RECENT_ERROR_BURST', 'severity':'warning', 'message':'At least three of the last twenty observed executions reported errors.'})
        if p95 is not None and p95 > 5000:
            alerts.append({'code':'HIGH_P95_LATENCY', 'severity':'warning', 'message':'Observed p95 execution time exceeds five seconds.'})
        return {'scope':'Local evaluations and API/workflow telemetry; p95 covers chat, resumed requests and configured workflows, not health polling',
                'runs':runs, 'events':events, 'alerts':alerts,
                'generation':{'sample_count':len(generations),'p95_ms':generation_p95,
                              'fallback_count':sum(g.get('outcome')=='FALLBACK' for g in generations),
                              'over_budget_count':sum(g.get('budget_exceeded') is True for g in generations),
                              'scope':'Bounded local observation window; generation latency is separate from end-to-end chat latency'},
                'runtime':{'sample_count':len(journey_events),'journey_sample_count':len(journey_events),'all_observation_count':len(events),
                           'workflow_sample_count':len(workflow_events),'workflow_error_executions':sum(e['error_count']>0 for e in workflow_events),
                           'error_executions':errors,'error_rate':errors/len(journey_events) if journey_events else None, 'p95_ms':p95}}

    @app.get('/api/traces/{run_id}')
    def traces(run_id: str, request: Request):
        authorize(request)
        _, locations = collect_runs(root)
        if run_id not in locations:
            raise HTTPException(404, 'Evaluation run not found')
        path = locations[run_id]/'traces.jsonl'
        if not path.exists():
            return {'traces':[]}
        if not path.resolve().is_relative_to(root) or path.stat().st_size > 32_000_000:
            raise HTTPException(413, 'Trace archive too large or outside artifact root')
        items = []
        with path.open(encoding='utf-8') as handle:
            for line in handle:
                if len(items) >= 50:
                    break
                try:
                    items.append(cloud_trace(json.loads(line)))
                except (ValueError, KeyError, TypeError):
                    continue
        return {'traces':items}
    return app
