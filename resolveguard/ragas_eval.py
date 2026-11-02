"""RAGAS collections metrics, explicitly invoked; no mock semantic scores."""
from .configuration import DEFAULT_CHAT_MODEL, DEFAULT_EMBEDDING_MODEL
import asyncio
import logging
import json
import math
import os
from .telemetry import sanitize

RAGAS_MAX_TOKENS = 8192


def build_metrics(client):
    # Disable RAGAS usage analytics; evaluation data goes only to configured Nebius.
    os.environ['RAGAS_DO_NOT_TRACK'] = 'true'
    try:
        from ragas.llms import llm_factory
        from ragas.embeddings.base import embedding_factory
        from ragas.metrics.collections import (
            ContextRecall, ContextPrecision, Faithfulness, AnswerRelevancy,
        )
    except ImportError as exc:
        raise RuntimeError('RAGAS dependencies are missing or incompatible; run uv sync --extra evals') from exc
    llm = llm_factory(os.environ.get('RESOLVEGUARD_JUDGE_MODEL', DEFAULT_CHAT_MODEL),
                      client=client, temperature=0, max_tokens=RAGAS_MAX_TOKENS)
    # Retain only structured evaluator verdicts, not hidden model reasoning.
    evidence = []
    original_generate = llm.agenerate

    async def record_verdict(prompt, response_model):
        result = await original_generate(prompt, response_model)
        evidence.append({'schema':response_model.__name__, 'verdict':sanitize(result.model_dump())})
        return result

    llm.agenerate = record_verdict
    llm._resolveguard_evidence = evidence
    embeddings = embedding_factory('openai',
        model=os.environ.get('RESOLVEGUARD_EMBEDDING_MODEL', DEFAULT_EMBEDDING_MODEL), client=client)
    return {'context_recall': ContextRecall(llm=llm),
            'context_precision': ContextPrecision(llm=llm),
            'faithfulness': Faithfulness(llm=llm),
            'answer_relevance': AnswerRelevancy(llm=llm, embeddings=embeddings)}


async def score_rag(sample: dict, metrics: dict) -> dict:
    results = {}
    for name, scorer in metrics.items():
        evidence = getattr(getattr(scorer, 'llm', None), '_resolveguard_evidence', None)
        keys = ('user_input', 'response') if name == 'answer_relevance' else (
            ('user_input', 'response', 'retrieved_contexts') if name == 'faithfulness'
            else ('user_input', 'retrieved_contexts', 'reference'))
        inputs = {k:sample[k] for k in keys}
        if name=='faithfulness' and sample.get('execution_context'):
            # Retrieval metrics remain policy-only. Faithfulness also checks
            # operational claims against the actual public handler's outcome.
            inputs['retrieved_contexts'] = [*sample['retrieved_contexts'],
                json.dumps({'evidence_type':'execution_state', **sample['execution_context']})]
        attempts = []
        for _ in range(2):
            evidence_start = len(evidence) if evidence is not None else 0
            try:
                result = await asyncio.wait_for(scorer.ascore(**inputs), timeout=180)
                value = float(result.value)
                if not math.isfinite(value) or not -1 <= value <= 1:
                    raise ValueError('Invalid metric result')
                attempt = {'status': 'OK', 'score': value}
            except Exception as exc:
                # Never log provider exception strings, which may contain prompts or keys.
                attempt = {'status': 'ERROR', 'score': None, 'error_type': type(exc).__name__}
            if evidence is not None:
                attempt['evidence'] = evidence[evidence_start:]
            attempts.append(attempt)
            retryable = {'IncompleteOutputException','APITimeoutError','APIConnectionError',
                         'RateLimitError','InternalServerError','TimeoutError'}
            # Retry technical failures only, never a valid low quality score.
            if attempt['status']=='OK' or attempt.get('error_type') not in retryable:
                break
        results[name] = {**attempts[-1], 'attempts':attempts}
        if name=='faithfulness':
            results[name]['evidence_scope'] = 'retrieved_policies_and_execution_state' if sample.get('execution_context') else 'retrieved_policies'
        logging.getLogger(__name__).info('RAGAS %s: %s', name, results[name]['status'])
    return results
