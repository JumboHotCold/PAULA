"""Release checks operate on controlled PostgreSQL fixtures, without providers."""
from io import StringIO
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, SimpleTestCase
from .models import FAQ
from .embedding_runtime import ModelNotReady


class OperationalChecks(TestCase):
    def test_strict_audit_rejects_empty_missing_zero_and_conflicting_knowledge(self):
        for condition in ('empty', 'missing', 'zero', 'conflict'):
            with self.subTest(condition=condition):
                # Fixtures exist only in Django's isolated PostgreSQL test database.
                FAQ.objects.all().delete()
                if condition != 'empty':
                    row = FAQ.objects.create(question='What is Nova?', answer='Approved fixture.', category='Fixture',
                                             embedding=None if condition == 'missing' else [0.0 if condition == 'zero' else .1] * 384)
                    if condition == 'conflict':
                        FAQ.objects.create(question=row.question, answer='Conflicting fixture.', category='Fixture', embedding=[.1]*384)
                with self.assertRaisesMessage(CommandError, 'Knowledge release check failed'):
                    call_command('audit_knowledge', strict=True, stdout=StringIO())

    def test_strict_audit_accepts_valid_knowledge_without_loading_an_encoder(self):
        FAQ.objects.create(question='What is Nova?', answer='Approved fixture.', category='Fixture', embedding=[.1]*384)
        with patch('chatbot.embedding_runtime.runtime.initialize', side_effect=AssertionError('Audit must stay offline')):
            call_command('audit_knowledge', strict=True, stdout=StringIO())

    def test_legacy_seed_never_overwrites_existing_sources(self):
        row = FAQ.objects.create(question='Reviewed correction', answer='Keep this fact.', category='Fixture')
        with self.assertRaisesMessage(CommandError, 'Existing facts were preserved'):
            call_command('seed_knowledge', stdout=StringIO())
        row.refresh_from_db()
        self.assertEqual(row.answer, 'Keep this fact.')
        self.assertEqual(FAQ.objects.count(), 1)


class ModelCacheChecks(SimpleTestCase):
    def test_cache_check_never_downloads_or_loads_by_default(self):
        with patch('chatbot.management.commands.prepare_embedding_model.EmbeddingRuntime') as runtime:
            call_command('prepare_embedding_model', stdout=StringIO())
        runtime.cached_path.assert_called_once()
        runtime.assert_not_called()

    def test_missing_cache_has_an_explicit_operational_failure(self):
        with patch('chatbot.management.commands.prepare_embedding_model.EmbeddingRuntime.cached_path', side_effect=ModelNotReady('Private path')):
            with self.assertRaisesMessage(CommandError, 'Embedding cache check failed (ModelNotReady)'):
                call_command('prepare_embedding_model', stdout=StringIO())
