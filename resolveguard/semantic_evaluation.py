"""Separate public-policy semantic suite alongside existing deterministic checks."""
from .configuration import DEFAULT_CHAT_MODEL, DEFAULT_EMBEDDING_MODEL
import asyncio
import hashlib
import json
import logging
import os
import time
from importlib.metadata import version
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .bow_knowledge import BowKnowledge
from .eval_config import ROOT, evaluation_client, load_eval_environment
from .evaluation import fingerprint
from .telemetry import sanitize


class SemanticCase(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    case_id: Annotated[str, Field(pattern=r'^SEM-[0-9]{3}$')]
    product_id: Annotated[str, Field(pattern=r'^BOW-[A-Z]+-[0-9]{3}$')]
    question: Annotated[str, Field(min_length=1, max_length=2000)]
    reference: Annotated[str, Field(min_length=1, max_length=5000)]
    reference_chunk_ids: Annotated[list[str], Field(min_length=1, max_length=20)]


class SemanticDataset(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: Annotated[str, Field(min_length=1, max_length=100)]
    review_status: Literal['PENDING', 'APPROVED']
    source_sha256: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
    as_of: str
    cases: Annotated[list[SemanticCase], Field(min_length=1, max_length=20)]

    @field_validator('as_of')
    @classmethod
    def valid_date(cls, value):
        date.fromisoformat(value)
        return value

    @field_validator('cases')
    @classmethod
    def unique_cases(cls, value):
        if len({c.case_id for c in value}) != len(value):
            raise ValueError('Duplicate semantic case ID')
        return value


def prepare_samples(dataset: dict) -> list[dict]:
    dataset = SemanticDataset.model_validate(dataset).model_dump()
    knowledge = BowKnowledge()
    if dataset['source_sha256'] != knowledge.manifest['source_sha256']:
        raise ValueError('Semantic references do not match the active policy snapshot')
    samples = []
    for case in dataset['cases']:
        product = case['product_id']
        references = [knowledge.chunk_map[i] for i in case['reference_chunk_ids']]
        if any(not knowledge.applicable(c['product_id'], product) for c in references):
            raise ValueError('Reference chunk has wrong product scope')
        answer = knowledge.answer(case['question'], product, dataset['as_of'])
        if answer.get('selected_product_id') not in (None,product):
            raise ValueError('Semantic product binding conflicts with the explicitly requested product')
        contexts = [knowledge.chunk_map[c['reference']] for c in answer['source_details'] if c['reference'] in knowledge.chunk_map]
        if any(c['bank_id']!='BOW' or not knowledge.applicable(c['product_id'],product) for c in contexts):
            raise ValueError('Retrieved semantic evidence has cross-bank or cross-product scope')
        context_lookup={c['chunk_id']:json.dumps({'product_name':knowledge.product_map[product]['product_name'],
            **{k:c[k] for k in ('chunk_id','bank_id','product_id','effective_date','expires_on','approval_status','chunk_text')}},ensure_ascii=False) for c in contexts}
        context_lookup.update({s['reference']:json.dumps({'evidence_type':'PRODUCT_CATALOG','product_name':knowledge.product_map[product]['product_name'],**s},ensure_ascii=False)
                               for s in answer['source_details'] if s['reference'].startswith('BOW-CATALOG:')})
        samples.append({'case_id':case['case_id'], 'product_id':product,
                        'user_input':case['question'], 'response':answer['response'],
                        'reference':case['reference'],
                        # Preserve metadata actually used to construct dated public answers.
                        # Omitting it would make supported effective-date claims look invented.
                        'retrieved_contexts':[context_lookup[s['reference']] for s in answer['source_details']],
                        'retrieved_chunk_ids':[c['reference'] for c in answer['source_details']],
                        'reference_chunk_ids':case['reference_chunk_ids'],
                        'execution_context':answer['execution_evidence'],
                        'bank_product_isolation':bool(contexts) and all(c['bank_id']=='BOW' and knowledge.applicable(c['product_id'], product) for c in contexts),
                        'authorization':{'data_scope':'PUBLIC', 'restricted_tools_called':False,
                                         'personal_eligibility_checked':answer['execution_evidence']['personal_eligibility_checked']}})
    return samples


async def run_semantic(dataset: dict, ragas: bool, judge: bool, progress_path=None) -> dict:
    if not (ragas or judge):
        raise ValueError('Select RAGAS and/or judge evaluation')
    samples = prepare_samples(dataset)
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    lock_fingerprint=hashlib.sha256((ROOT/'uv.lock').read_bytes()).hexdigest()
    evaluator_fingerprint=fingerprint({name:(ROOT/'resolveguard'/name).read_text(encoding='utf-8') for name in ('ragas_eval.py','judges.py','semantic_evaluation.py','eval_config.py')})
    usage = []
    client = evaluation_client(usage)
    rows = []
    try:
        from langsmith import tracing_context
        # Provider SDK auto-instrumentation must not export evaluation content.
        with tracing_context(enabled=False):
            from .ragas_eval import RAGAS_MAX_TOKENS, build_metrics, score_rag
            from .judges import grade_response
            metrics = build_metrics(client) if ragas else None
            for sample in samples:
                if progress_path:
                    Path(progress_path).write_text(json.dumps({'status':'RUNNING','active_case':sample['case_id'],'completed_cases':len(rows),'total_cases':len(samples),'rows':rows},indent=2),encoding='utf-8')
                logging.getLogger(__name__).info('Starting synthetic case %s', sample['case_id'])
                row = {**sample, 'status':'OK'}
                if ragas:
                    row['ragas'] = await score_rag(sample, metrics)
                    if any(v['status']!='OK' for v in row['ragas'].values()):
                        row['status'] = 'ERROR'
                if judge:
                    attempts=[]
                    for _ in range(2):
                        try:
                            row['judge'] = await asyncio.wait_for(grade_response(sample, client,
                                os.environ.get('RESOLVEGUARD_JUDGE_MODEL', DEFAULT_CHAT_MODEL)), timeout=90)
                            attempts.append({'status':'OK'});break
                        except Exception as exc:
                            attempts.append({'status':'ERROR','error_type':type(exc).__name__})
                            row['judge'] = {'status':'ERROR', 'error_type':type(exc).__name__}
                    row['judge']['attempts']=attempts
                    if row['judge'].get('status')=='ERROR':row['status']='ERROR'
                rows.append(sanitize(row))
                if progress_path:
                    Path(progress_path).write_text(json.dumps({'status':'COMPLETE' if len(rows)==len(samples) else 'RUNNING','active_case':None,'completed_cases':len(rows),'total_cases':len(samples),'rows':rows},indent=2),encoding='utf-8')
                logging.getLogger(__name__).info('Completed case %s: %s', sample['case_id'], row['status'])
    finally:
        await client.close()
    return {'status':'COMPLETE' if all(r['status']=='OK' for r in rows) else 'ERROR',
            'dataset_sha256':fingerprint(dataset), 'review_status':dataset['review_status'],
            'dataset_version':dataset['version'], 'as_of':dataset['as_of'],
            'source_sha256':dataset['source_sha256'], 'started_at':started_at,
            'uv_lock_sha256':lock_fingerprint,
            'evaluator_sha256':evaluator_fingerprint,
            'judge_model':os.environ.get('RESOLVEGUARD_JUDGE_MODEL', DEFAULT_CHAT_MODEL),
            'embedding_model':os.environ.get('RESOLVEGUARD_EMBEDDING_MODEL', DEFAULT_EMBEDDING_MODEL),
            'elapsed_seconds':round(time.perf_counter()-started, 3),
            'usage':usage, 'versions':{package:version(package) for package in (
                ('ragas','openai','instructor') if ragas else ('openai',))},
            'answer_generation':'Existing BOW application templates; live models evaluate the answers',
            'context_format':'policy-and-catalog-metadata-v2',
            'ragas_max_tokens':RAGAS_MAX_TOKENS if ragas else None,
            'scope':'Public BOW semantic pilot; not the 40-case or 100-case banking benchmark',
            'rows':rows}


def evaluate_semantics(output: str, ragas: bool = True, judge: bool = True,
                       dataset_path: str | None = None) -> dict:
    load_eval_environment()
    path = Path(output)
    if path.exists():
        raise FileExistsError('Use a new semantic output path')
    dataset = json.loads(Path(dataset_path or ROOT/'data/semantic_cases.json').read_text(encoding='utf-8'))
    report = {'status':'NOT_RUN', 'dataset_sha256':fingerprint(dataset)}
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = asyncio.run(run_semantic(dataset, ragas, judge,path.with_suffix('.progress.json')))
        return report
    except Exception as exc:
        report.update(status='ERROR', error_type=type(exc).__name__)
        if not os.environ.get('NEBIUS_API_KEY'):
            report['blocked_reason'] = 'NEBIUS_API_KEY_NOT_CONFIGURED'
        raise RuntimeError('Semantic evaluation incomplete; see local result status') from None
    finally:
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
