"""Build metadata is stable per loaded worker and does not need a Git executable."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.test import SimpleTestCase, RequestFactory, override_settings
from .build_info import _build_snapshot, build_info
from .readiness import initialize_worker
from .readiness import readiness_state
from .views import health_live

SHA = 'a' * 40


class BuildStampTests(SimpleTestCase):
    def setUp(self):
        _build_snapshot.cache_clear()

    def tearDown(self):
        _build_snapshot.cache_clear()

    def test_environment_stamp_is_validated_and_public_health_exposes_it(self):
        with override_settings(PAULA_BUILD_COMMIT=SHA), patch('chatbot.build_info._git_commit', return_value=None):
            result = json.loads(health_live(RequestFactory().get('/api/health/live')).content)
        self.assertEqual(result['build_commit'], SHA)
        self.assertEqual(result['build_source'], 'environment')
        self.assertEqual(len(result['build_source_digest']), 64)

    def test_invalid_environment_stamp_is_not_presented_as_verified(self):
        with override_settings(PAULA_BUILD_COMMIT='not-a-commit'), self.assertRaises(ValueError):
            build_info()

    def test_git_stamp_and_digest_do_not_follow_later_worktree_edits(self):
        with TemporaryDirectory() as directory, override_settings(BASE_DIR=Path(directory), PAULA_BUILD_COMMIT=''):
            root = Path(directory)
            (root / '.git' / 'refs' / 'heads').mkdir(parents=True)
            (root / '.git' / 'HEAD').write_text('ref: refs/heads/demo\n')
            ref = root / '.git' / 'refs' / 'heads' / 'demo'
            ref.write_text(SHA)
            (root / 'chatbot').mkdir()
            source = root / 'chatbot' / 'demo.py'
            source.write_text('value = 1\n')
            first = build_info()
            ref.write_text('b' * 40)
            source.write_text('value = 2\n')
            self.assertEqual(build_info(), first)
            _build_snapshot.cache_clear()
            second = build_info()
            self.assertNotEqual(second['build_commit'], first['build_commit'])
            self.assertNotEqual(second['build_source_digest'], first['build_source_digest'])

    def test_packed_refs_and_detached_head_are_supported(self):
        with TemporaryDirectory() as directory, override_settings(BASE_DIR=Path(directory), PAULA_BUILD_COMMIT=''):
            root = Path(directory) / '.git'
            root.mkdir()
            (root / 'HEAD').write_text('ref: refs/heads/demo\n')
            (root / 'packed-refs').write_text('# pack-refs\n' + SHA + ' refs/heads/demo\n')
            self.assertEqual(build_info()['build_commit'], SHA)
            _build_snapshot.cache_clear()
            (root / 'HEAD').write_text('b' * 40)
            self.assertEqual(build_info()['build_commit'], 'b' * 40)

    def test_missing_metadata_is_explicitly_unknown(self):
        with TemporaryDirectory() as directory, override_settings(BASE_DIR=Path(directory), PAULA_BUILD_COMMIT=''):
            stamp = build_info()
        self.assertIsNone(stamp['build_commit'])
        self.assertEqual(stamp['build_source'], 'unknown')

    def test_development_source_overrides_an_older_baked_image_revision(self):
        with override_settings(PAULA_BUILD_COMMIT=SHA), patch('chatbot.build_info._git_commit', return_value='b' * 40):
            stamp = build_info()
        self.assertEqual(stamp['build_commit'], 'b' * 40)
        self.assertEqual(stamp['build_source'], 'git')

    def test_startup_logs_and_worker_record_share_the_build_stamp(self):
        stamp = {'build_commit': SHA, 'build_source': 'environment', 'build_source_digest': 'c' * 64}
        model_runtime = Mock(status='ready')
        with patch('chatbot.readiness.build_info', return_value=stamp), patch('chatbot.readiness.runtime', model_runtime), \
                patch('chatbot.views.bot', SimpleNamespace(rag=Mock())), patch('chatbot.dialogue.social_router.prepare'), \
                patch('chatbot.readiness.boot_directory', return_value=None), self.assertLogs('paula.performance') as logs:
            initialize_worker(Mock())
        records = [json.loads(value.split(':', 2)[2]) for value in logs.output]
        self.assertEqual([row['event'] for row in records], ['worker_initializing', 'worker_startup'])
        self.assertTrue(all(row['build_commit'] == SHA for row in records))

    def test_mixed_worker_revisions_are_visible_in_readiness(self):
        stamp = {'build_commit': SHA, 'build_source': 'git', 'build_source_digest': 'c' * 64}
        with TemporaryDirectory() as directory:
            Path(directory, 'fixture.json').write_text(json.dumps({'worker': 123, 'ready': True, 'dimensions': 384,
                'build_commit': 'b' * 40, 'build_source_digest': 'c' * 64}))
            with patch('chatbot.readiness.boot_directory', return_value=Path(directory)), \
                    patch('chatbot.readiness.runtime', SimpleNamespace(status='ready')), \
                    patch('chatbot.readiness.build_info', return_value=stamp), patch('chatbot.readiness.os.kill'), \
                    patch.dict('os.environ', {'PAULA_WORKER_COUNT': '1'}):
                state = readiness_state()
        self.assertFalse(state['build_consistent'])
        self.assertEqual(state['build_commit'], SHA)
