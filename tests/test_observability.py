import asyncio
import copy
import json
import os
import tempfile
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from resolveguard.cloud_privacy import cloud_trace
from resolveguard.cloud_verify import verify_cloud
from resolveguard.dashboard import create_dashboard
from resolveguard.eval_config import ROOT, cloud_tracing_enabled, load_eval_environment
from resolveguard.judges import JudgeGrade, grade_response
from resolveguard.monitoring import observe, read_observations, record_observation
from resolveguard.ragas_eval import score_rag
from resolveguard.semantic_evaluation import prepare_samples, evaluate_semantics
from resolveguard.telemetry import Trace
from contextlib import nullcontext


def traced_result():
    trace = Trace({'customer_name':'Private Customer'})
    with trace.span('resolveguard.journey', inputs={'message':'Private Customer, acct 123456789'}) as span:
        span['outputs'] = {'balance':999, 'address':'Private Street'}
    return {'trace':trace.export(), 'execution_mode':'MOCK', 'errors':[]}


class PrivacyAndConfigTests(unittest.TestCase):
    def test_projection_omits_all_arbitrary_payload_and_metadata(self):
        original = traced_result()['trace']
        original['spans'][0]['unexpected_field'] = 'Secret Name'
        result = cloud_trace(original)
        serialized = json.dumps(result)
        for private in ('Private Customer','123456789','Private Street','Secret Name','balance'):
            self.assertNotIn(private, serialized)
        self.assertTrue(original['spans'][0]['inputs'])
        self.assertEqual(result['spans'][0]['inputs'], {})

    def test_env_loader_preserves_existing_values_and_does_not_execute(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'NEBIUS_API_KEY':'existing'}, clear=True):
            path = Path(temp)/'.env'
            path.write_text('NEBIUS_API_KEY=replacement\nLANGSMITH_PROJECT="sample"\nPATH=changed\nUNRELATED=$(whoami)')
            load_eval_environment(path)
            self.assertEqual(os.environ['NEBIUS_API_KEY'], 'existing')
            self.assertEqual(os.environ['LANGSMITH_PROJECT'], 'sample')
            self.assertNotIn('PATH', os.environ)

    def test_runtime_cloud_requires_both_switches(self):
        with patch.dict(os.environ, {'LANGSMITH_TRACING':'true'}, clear=True):
            self.assertFalse(cloud_tracing_enabled())
            os.environ['RESOLVEGUARD_CLOUD_TRACING'] = 'true'
            self.assertTrue(cloud_tracing_enabled())

    def test_monitor_failure_does_not_break_customer_result(self):
        with patch.dict(os.environ, {'RESOLVEGUARD_MONITOR_DB':'unused'}, clear=True), \
             patch('resolveguard.monitoring.record_observation', side_effect=RuntimeError('secret')):
            observe(traced_result())


class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.dataset = json.loads((ROOT/'data/semantic_cases.json').read_text())

    def test_real_policy_retrieval_has_independent_reference_ids(self):
        samples = prepare_samples(self.dataset)
        self.assertEqual(len(samples), 3)
        for sample in samples:
            self.assertTrue(sample['bank_product_isolation'])
            self.assertTrue(set(sample['reference_chunk_ids']) <= set(sample['retrieved_chunk_ids']))
            self.assertTrue(sample['retrieved_contexts'])
            context = json.loads(sample['retrieved_contexts'][0])
            self.assertEqual(context['effective_date'], self.dataset['as_of'][:7]+'-01')
            self.assertEqual(context['bank_id'], 'BOW')
            self.assertTrue(context['product_name'].startswith('Whatever '))

    def test_wrong_source_snapshot_rejected(self):
        self.dataset['source_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'snapshot'):
            prepare_samples(self.dataset)

    def test_wrong_product_reference_rejected(self):
        self.dataset['cases'][0]['reference_chunk_ids'] = ['POL-BOW-SAV-001-C02']
        with self.assertRaisesRegex(ValueError, 'scope'):
            prepare_samples(self.dataset)

    def test_explicit_product_and_reference_binding_cannot_disagree(self):
        self.dataset['cases'][0]['question']='What is the monthly maintenance fee for Whatever Plus Checking?'
        with self.assertRaisesRegex(ValueError,'binding'):
            prepare_samples(self.dataset)

    def test_metric_errors_and_nan_are_not_scores(self):
        sample = prepare_samples(self.dataset)[0]
        good = SimpleNamespace(ascore=AsyncMock(return_value=SimpleNamespace(value=.75)))
        bad = SimpleNamespace(ascore=AsyncMock(side_effect=RuntimeError('secret payload')))
        nan = SimpleNamespace(ascore=AsyncMock(return_value=SimpleNamespace(value=float('nan'))))
        result = asyncio.run(score_rag(sample, {'faithfulness':good, 'context_recall':bad, 'context_precision':nan}))
        self.assertEqual(result['faithfulness']['score'], .75)
        self.assertIsNone(result['context_recall']['score'])
        self.assertIsNone(result['context_precision']['score'])
        self.assertNotIn('secret payload', json.dumps(result))
        self.assertNotIn('reference', good.ascore.call_args.kwargs)

    def test_only_technical_metric_errors_are_retried_once(self):
        sample = prepare_samples(self.dataset)[0]
        incomplete = type('IncompleteOutputException', (Exception,), {})
        scorer = SimpleNamespace(ascore=AsyncMock(side_effect=[incomplete(), SimpleNamespace(value=.25)]))
        result = asyncio.run(score_rag(sample, {'faithfulness':scorer}))['faithfulness']
        self.assertEqual(result['score'], .25)
        self.assertEqual(len(result['attempts']), 2)
        self.assertEqual(result['attempts'][0]['status'], 'ERROR')
        self.assertEqual(scorer.ascore.await_count, 2)
        low = SimpleNamespace(ascore=AsyncMock(return_value=SimpleNamespace(value=.1)))
        asyncio.run(score_rag(sample, {'faithfulness':low}))
        self.assertEqual(low.ascore.await_count, 1)

    def test_missing_credentials_create_explicit_failure_evidence(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True), \
             patch('resolveguard.semantic_evaluation.load_eval_environment'):
            path = Path(temp)/'semantic.json'
            with self.assertRaises(RuntimeError):
                evaluate_semantics(str(path))
            self.assertEqual(json.loads(path.read_text())['status'], 'ERROR')

    def test_structured_judge_and_inconsistent_grades(self):
        dimension = {'score':4, 'passed':True, 'reasoning':'Supported by the supplied policy.'}
        grade = {k:copy.deepcopy(dimension) for k in ('tone_empathy','policy_compliance','guardrail_integrity')}
        grade['passed'] = True
        reply = SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=json.dumps(grade)))], usage=None)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=reply))))
        result = asyncio.run(grade_response(prepare_samples(self.dataset)[0], client, 'test-judge'))
        self.assertTrue(result['grade']['passed'])
        self.assertEqual(client.chat.completions.create.call_args.kwargs['max_tokens'], 8192)
        payload=json.loads(client.chat.completions.create.call_args.kwargs['messages'][1]['content'])
        self.assertNotIn('authorization', payload)
        self.assertEqual(payload['access_evidence']['data_scope'], 'PUBLIC')
        self.assertIs(payload['access_evidence']['restricted_tools_called'],False)
        grade['policy_compliance']['score'] = 1
        with self.assertRaises(ValueError):
            JudgeGrade.model_validate(grade)

    def test_safe_access_projection_never_forwards_identifiers_or_credentials(self):
        sample=prepare_samples(self.dataset)[0]
        sample['authorization']={'data_scope':'RESTRICTED','authenticated':True,'authorized':False,
            'personal_eligibility_checked':'yes',
            'restricted_tools_called':False,'account_id':'PRIVATE-ACCOUNT','token':'PRIVATE-TOKEN',
            'header':'Bearer PRIVATE-KEY'}
        dimension={'score':4,'passed':True,'reasoning':'Supported by test evidence.'}
        grade={k:dimension for k in ('tone_empathy','policy_compliance','guardrail_integrity')}
        reply=SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=json.dumps({**grade,'passed':True})))],usage=None)
        client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=reply))))
        asyncio.run(grade_response(sample,client,'test-judge'))
        payload=client.chat.completions.create.call_args.kwargs['messages'][1]['content']
        self.assertNotIn('PRIVATE-',payload)
        access=json.loads(payload)['access_evidence']
        self.assertIs(access['authenticated'],True);self.assertIs(access['authorized'],False)
        self.assertIsNone(access['personal_eligibility_checked'])

    def test_execution_facts_only_extend_faithfulness_not_retrieval_metrics(self):
        sample=prepare_samples(self.dataset)[1]
        recall=SimpleNamespace(ascore=AsyncMock(return_value=SimpleNamespace(value=1.0)))
        faithful=SimpleNamespace(ascore=AsyncMock(return_value=SimpleNamespace(value=1.0)))
        asyncio.run(score_rag(sample,{'context_recall':recall,'faithfulness':faithful}))
        self.assertEqual(recall.ascore.call_args.kwargs['retrieved_contexts'],sample['retrieved_contexts'])
        context=faithful.ascore.call_args.kwargs['retrieved_contexts']
        self.assertEqual(len(context),len(sample['retrieved_contexts'])+1)
        self.assertEqual(json.loads(context[-1])['evidence_type'],'execution_state')


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        run = self.root/'sample'; run.mkdir()
        summary = {'metrics':{'intent_accuracy':.9, 'deterministic_journey_pass_rate':.8,
                             'fraud_recall':1.0}, 'failure_counts':{'policy_evidence':1},
                   'dataset_sha256':'abc', 'code_sha256':'def', 'run_type':'MOCK'}
        (run/'summary.json').write_text(json.dumps(summary))
        (run/'traces.jsonl').write_text(json.dumps(traced_result()['trace'])+'\n')
        self.db = str(self.root/'monitor.sqlite3')
        self.token = 'test-token-at-least-24-characters'
        self.headers = {'Authorization':'Bearer '+self.token}
        self.client = TestClient(create_dashboard(self.root, self.token, self.db))

    def tearDown(self):
        self.client.close(); self.temp.cleanup()

    def test_unauthenticated_api_blocked(self):
        self.assertEqual(self.client.get('/api/operations').status_code, 401)
        self.assertEqual(self.client.get('/api/traces/unknown').status_code, 401)

    def test_static_interface_and_security_headers(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Evaluation trends', response.text)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(self.client.get('/operations.js').status_code, 200)

    def test_history_metrics_and_private_trace_projection(self):
        data = self.client.get('/api/operations', headers=self.headers).json()
        self.assertEqual(data['runs'][0]['metrics']['intent_accuracy'], .9)
        run_id = data['runs'][0]['id']
        trace = self.client.get('/api/traces/'+run_id, headers=self.headers).text
        self.assertNotIn('Private Customer', trace)
        self.assertNotIn('123456789', trace)
        self.assertEqual(self.client.get('/api/traces/missing', headers=self.headers).status_code, 404)

    def test_runtime_events_p95_and_error_alert(self):
        result = traced_result(); result['errors'] = ['INTERNAL_ERROR']
        result['trace']['spans'][0]['latency_ms'] = 6000
        for _ in range(3): record_observation(result, self.db)
        self.assertEqual(len(read_observations(self.db)), 3)
        data = self.client.get('/api/operations', headers=self.headers).json()
        self.assertEqual(data['runtime']['p95_ms'], 6000)
        self.assertEqual(data['runtime']['error_rate'], 1)
        self.assertEqual({a['code'] for a in data['alerts']}, {'RECENT_ERROR_BURST','HIGH_P95_LATENCY'})
        self.assertNotIn('Private Customer', json.dumps(data))

    def test_malformed_summary_is_skipped(self):
        broken = self.root/'broken'; broken.mkdir(); (broken/'summary.json').write_text('{')
        self.assertEqual(len(self.client.get('/api/operations', headers=self.headers).json()['runs']), 1)


class CloudReadbackTests(unittest.TestCase):
    def test_smoke_verification_requires_remote_nested_stages(self):
        from unittest.mock import Mock
        client = Mock()
        client.list_examples.return_value = [object()]
        root = SimpleNamespace(id='remote-run', feedback_stats={'routing_exact':{}},
            inputs={'message':'Synthetic evaluation case; customer text retained locally.'},
            outputs={'checks':{}, 'passed':True})
        client.list_runs.return_value = [root]
        children = [SimpleNamespace(name=name, inputs={}, outputs={'execution_error':False}, child_runs=[])
                    for name in ('classify','retrieve','template.explain')]
        client.read_run.return_value = SimpleNamespace(child_runs=children)
        created = SimpleNamespace(id='remote-dataset', name='remote-name')
        experiment = Mock(experiment_name='remote-experiment')
        with tempfile.TemporaryDirectory() as temp, \
             patch('resolveguard.cloud_verify.load_eval_environment'), \
             patch('resolveguard.langsmith_integration.client_from_environment', return_value=client), \
             patch('resolveguard.langsmith_integration.upload_dataset', return_value=created), \
             patch('resolveguard.langsmith_integration.evaluate_in_langsmith', return_value=experiment), \
             patch('langsmith.tracing_context', side_effect=lambda **kwargs:nullcontext()):
            report = verify_cloud(str(Path(temp)/'success.json'), limit=1)
            self.assertEqual(report['status'], 'VERIFIED')
            self.assertEqual(report['nested_span_counts'], [3])
            client.read_run.return_value = SimpleNamespace(child_runs=[])
            failed = Path(temp)/'failed.json'
            with self.assertRaises(RuntimeError):
                verify_cloud(str(failed), limit=1)
            self.assertEqual(json.loads(failed.read_text())['status'], 'NOT_VERIFIED')
            self.assertEqual(json.loads(failed.read_text())['experiment_name'], 'remote-experiment')

    def test_missing_key_records_unverified_not_success(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=True), \
             patch('resolveguard.cloud_verify.load_eval_environment'):
            output = Path(temp)/'cloud.json'
            with self.assertRaises(RuntimeError):
                verify_cloud(str(output), limit=1)
            evidence = json.loads(output.read_text())
            self.assertEqual(evidence['status'], 'NOT_VERIFIED')
            self.assertEqual(evidence['blocked_reason'], 'LANGSMITH_API_KEY_NOT_CONFIGURED')


@unittest.skipUnless(importlib.util.find_spec('openai'), 'Optional evaluation SDK not installed')
class ProviderUsageTests(unittest.IsolatedAsyncioTestCase):
    async def test_usage_capture_records_counts_not_prompts_or_keys(self):
        import httpx
        from resolveguard.eval_config import evaluation_client
        usage = []
        with patch.dict(os.environ, {'NEBIUS_API_KEY':'test-key'}):
            client = evaluation_client(usage)
        try:
            hook = client._client.event_hooks['response'][0]
            request = httpx.Request('POST', 'https://api.tokenfactory.nebius.com/v1/chat/completions',
                json={'model':'test-model', 'messages':[{'content':'PRIVATE SENTENCE'}]},
                headers={'Authorization':'Bearer test-key'})
            response = httpx.Response(200, request=request,
                json={'usage':{'prompt_tokens':10, 'completion_tokens':20}, 'secret':'PRIVATE RESPONSE'})
            await hook(response)
            self.assertEqual(usage, [{'http_status':200, 'model':'test-model', 'input_tokens':10, 'output_tokens':20}])
            self.assertNotIn('PRIVATE', json.dumps(usage))
            self.assertNotIn('test-key', json.dumps(usage))
        finally:
            await client.close()


if __name__ == '__main__':
    unittest.main()
