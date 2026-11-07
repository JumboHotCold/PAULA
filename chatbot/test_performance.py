"""Phase 1 contracts: no provider access, model downloads, or DB writes."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from .embedding_runtime import EmbeddingRuntime, ModelNotReady
from .performance import RequestTimingMiddleware, capture_trace, stage
from .providers import GenerationBudget, ProviderPolicy, completion_options, generation_scope, _budget
from .readiness import readiness_state


class TimingTests(unittest.TestCase):
    def test_nested_spans_distinguish_inclusive_and_exclusive_time(self):
        with capture_trace() as trace:
            with stage('outer'):
                with stage('inner'):
                    time.sleep(.001)
        self.assertGreaterEqual(trace.stages['outer']['inclusive_ms'], trace.stages['inner']['inclusive_ms'])
        self.assertLessEqual(trace.stages['outer']['self_ms'], trace.stages['outer']['inclusive_ms'])
        self.assertEqual(trace.stages['inner']['calls'], 1)

    def test_request_ids_are_generated_and_payloads_never_logged(self):
        request = RequestFactory().post('/api/chat', {'message': 'PRIVATE MESSAGE'}, HTTP_X_REQUEST_ID='PRIVATE HEADER')
        middleware = RequestTimingMiddleware(lambda request: HttpResponse('PRIVATE RESPONSE'))
        with self.assertLogs('paula.performance', level='INFO') as logs:
            response = middleware(request)
        UUID(response['X-Request-ID'])
        self.assertEqual(response['X-PAULA-Worker'], str(os.getpid()))
        self.assertNotIn('PRIVATE', ''.join(logs.output))
        self.assertIn('Server-Timing', response)

    def test_concurrent_traces_are_isolated_and_reset(self):
        def request():
            with capture_trace() as trace:
                with stage('work'):
                    return trace.request_id
        with ThreadPoolExecutor(max_workers=2) as executor:
            ids = list(executor.map(lambda _: request(), range(4)))
        self.assertEqual(len(set(ids)), 4)
        with capture_trace() as fresh:
            self.assertEqual(fresh.stages, {})


class EmbeddingReadinessTests(unittest.TestCase):
    def model(self, dimension=384):
        model = Mock()
        model.get_sentence_embedding_dimension.return_value = dimension
        model.encode.return_value.tolist.return_value = [0.1] * dimension
        return model

    def test_cached_model_is_constructed_once_with_offline_options(self):
        runtime = EmbeddingRuntime()
        factory = Mock(return_value=self.model())
        with patch.object(runtime, 'cached_path', return_value=Path('/cached/snapshot')), \
                patch.dict('sys.modules', {'sentence_transformers': SimpleNamespace(SentenceTransformer=factory)}):
            first = runtime.initialize()
            self.assertIs(runtime.initialize(), first)
        factory.assert_called_once_with('/cached/snapshot', local_files_only=True, device='cpu')
        self.assertEqual(runtime.status, 'ready')

    def test_web_request_cannot_cold_initialize_a_model(self):
        runtime = EmbeddingRuntime()
        runtime.web_worker = True
        with patch.object(runtime, 'initialize') as initialize:
            with self.assertRaises(ModelNotReady):
                runtime.get_model()
        initialize.assert_not_called()

    def test_wrong_dimensions_never_become_ready(self):
        runtime = EmbeddingRuntime()
        with patch.object(runtime, 'cached_path', return_value=Path('/cached/snapshot')), \
                patch.dict('sys.modules', {'sentence_transformers': SimpleNamespace(SentenceTransformer=Mock(return_value=self.model(768)))}):
            with self.assertRaises(ModelNotReady):
                runtime.initialize()
        self.assertEqual(runtime.status, 'failed')
        self.assertIsNone(runtime.model)

    def test_multiple_searchers_share_one_prepared_process_model(self):
        from .rag import RAGSearcher
        runtime = EmbeddingRuntime()
        runtime.status = 'ready'
        runtime.model = self.model()
        with patch('chatbot.embedding_runtime.runtime', runtime):
            first, second = RAGSearcher(), RAGSearcher()
            self.assertEqual(len(first._generate_embedding('Public query')), 384)
            self.assertEqual(len(second._generate_embedding('Other public query')), 384)
        self.assertIs(first.model, second.model)

    def test_missing_cached_files_fail_without_downloading(self):
        with override_settings(PAULA_EMBEDDING_MODEL_PATH='/does-not-exist'):
            with self.assertRaises(ModelNotReady):
                EmbeddingRuntime.cached_path()


class ProviderPolicyTests(unittest.TestCase):
    def error(self, status=403, code='model_permission_blocked_project'):
        error = RuntimeError('PRIVATE provider diagnostic')
        error.status_code = status
        error.body = {'error': {'code': code}}
        return error

    def test_permanent_errors_are_not_repeated(self):
        for status, code in ((403, 'model_permission_blocked_project'), (404, 'model_not_found'), (429, 'credit_balance_exhausted')):
            policy = ProviderPolicy()
            callback = Mock(side_effect=self.error(status, code))
            self.assertIsNone(policy.call('groq', 'test-model', callback))
            self.assertIsNone(policy.call('groq', 'test-model', callback))
            callback.assert_called_once()

    def test_outage_state_is_shared_by_workers_in_the_same_boot(self):
        with TemporaryDirectory() as directory, override_settings(PAULA_RUNTIME_DIR=directory), \
                patch.dict(os.environ, {'PAULA_BOOT_ID': str(uuid4())}):
            ProviderPolicy().fail('groq', 'test-model', self.error())
            callback = Mock()
            ProviderPolicy().call('groq', 'test-model', callback)
            callback.assert_not_called()

    def test_other_models_are_not_disabled_by_one_model_outage(self):
        policy = ProviderPolicy()
        policy.fail('groq', 'blocked-model', self.error(404, 'model_not_found'))
        callback = Mock(return_value='verified IDs')
        self.assertEqual(policy.call('groq', 'healthy-model', callback), 'verified IDs')

    def test_overall_deadline_stops_waiting_for_a_slow_provider(self):
        release = Event()
        policy = ProviderPolicy()
        token = _budget.set(GenerationBudget(.03))
        start = time.perf_counter()
        try:
            self.assertIsNone(policy.call('groq', 'slow-model', lambda timeout: release.wait(1)))
            self.assertLess(time.perf_counter()-start, .3)
            fallback = Mock()
            policy.call('openai', 'fallback', fallback)
            fallback.assert_not_called()
        finally:
            release.set()
            _budget.reset(token)

    def test_request_budget_is_shared_by_nested_calls_and_reset_afterward(self):
        values = []
        @generation_scope
        def inner():
            values.append(_budget.get())
        @generation_scope
        def outer():
            values.append(_budget.get())
            inner()
        outer()
        self.assertIs(values[0], values[1])
        self.assertIsNone(_budget.get())

    def test_known_blocked_provider_does_not_spend_compound_call_allowance(self):
        policy = ProviderPolicy()
        policy.fail('groq', 'blocked-model', self.error())
        attempts = [1]
        policy.call('groq', 'blocked-model', Mock(), attempts)
        callback = Mock(return_value='IDs')
        self.assertEqual(policy.call('openai', 'healthy-model', callback, attempts), 'IDs')
        self.assertEqual(attempts, [0])
        policy.call('gemini', 'other', Mock(side_effect=AssertionError()), attempts)

    def test_gpt_oss_uses_low_reasoning_and_strict_bounded_id_schema(self):
        options = completion_options('groq', 'openai/gpt-oss-20b', count=2)
        self.assertEqual(options['reasoning_effort'], 'low')
        self.assertFalse(options['include_reasoning'])
        schema = options['response_format']['json_schema']['schema']
        self.assertEqual(schema['properties']['evidence_ids']['items']['enum'], [1, 2])
        self.assertFalse(schema['additionalProperties'])

    def test_failure_logs_never_include_raw_provider_error_details(self):
        with capture_trace() as trace:
            ProviderPolicy().call('groq', 'test', Mock(side_effect=self.error()))
        self.assertNotIn('PRIVATE', json.dumps(trace.summary()))
        self.assertEqual(trace.providers[0]['outcome'], 'model_permission_blocked')

    def test_real_sdk_timeout_class_uses_timeout_cooldown_and_safe_metadata(self):
        import httpx
        from groq import APITimeoutError
        policy = ProviderPolicy()
        callback = Mock(side_effect=APITimeoutError(request=httpx.Request('POST', 'https://api.groq.com/test')))
        with capture_trace() as trace:
            self.assertIsNone(policy.call('groq', 'test', callback))
            self.assertIsNone(policy.call('groq', 'test', callback))
        callback.assert_called_once()
        self.assertEqual(trace.providers[0]['outcome'], 'timeout')
        self.assertEqual(trace.providers[0]['error_type'], 'APITimeoutError')
        self.assertNotIn('https://', json.dumps(trace.summary()))


class WorkerReadinessTests(unittest.TestCase):
    def test_master_cleanup_needs_no_django_or_model_initialization(self):
        from paulibot.gunicorn_conf import child_exit
        with TemporaryDirectory() as root, patch.dict(os.environ, {'PAULA_RUNTIME_DIR': root, 'PAULA_BOOT_ID': str(uuid4())}):
            directory = Path(root)/os.environ['PAULA_BOOT_ID']
            directory.mkdir()
            marker = directory/'123.json'
            other = directory/'124.json'
            marker.write_text('{}')
            other.write_text('{}')
            with patch.dict('sys.modules', {'chatbot.readiness': None}):
                child_exit(None, SimpleNamespace(pid=123))
            self.assertFalse(marker.exists())
            self.assertTrue(other.exists())

    def test_all_workers_must_be_ready_and_old_boots_are_ignored(self):
        from .embedding_runtime import runtime
        with TemporaryDirectory() as root, override_settings(PAULA_RUNTIME_DIR=root), \
                patch.dict(os.environ, {'PAULA_BOOT_ID': str(uuid4()), 'PAULA_WORKER_COUNT': '2'}), \
                patch.object(runtime, 'status', 'ready'), patch('chatbot.readiness.os.kill'):
            path = Path(root)/os.environ['PAULA_BOOT_ID']
            path.mkdir()
            (path/'1.json').write_text(json.dumps({'worker': 1, 'ready': True, 'dimensions': 384}))
            self.assertFalse(readiness_state()['ready'])
            (path/'2.json').write_text(json.dumps({'worker': 2, 'ready': True, 'dimensions': 384}))
            self.assertTrue(readiness_state()['ready'])
            with patch.dict(os.environ, {'PAULA_BOOT_ID': str(uuid4())}):
                self.assertFalse(readiness_state()['ready'])

    def test_dead_or_failed_workers_do_not_count(self):
        from .embedding_runtime import runtime
        with TemporaryDirectory() as root, override_settings(PAULA_RUNTIME_DIR=root), \
                patch.dict(os.environ, {'PAULA_BOOT_ID': str(uuid4()), 'PAULA_WORKER_COUNT': '1'}), \
                patch.object(runtime, 'status', 'ready'), patch('chatbot.readiness.os.kill', side_effect=ProcessLookupError):
            path = Path(root)/os.environ['PAULA_BOOT_ID']
            path.mkdir()
            (path/'1.json').write_text(json.dumps({'worker': 1, 'ready': True, 'dimensions': 384}))
            self.assertFalse(readiness_state()['ready'])
