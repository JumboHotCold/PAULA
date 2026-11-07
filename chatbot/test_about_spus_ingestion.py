"""PostgreSQL import safety and exact FAQ grounding regressions; no API calls."""
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, SimpleTestCase, override_settings

from .grounding import eligible_evidence
from .management.commands.ingest_about_spus import SOURCE, document_entries
from .models import FAQ
from .rag import RAGSearcher


TEXT = (Path(settings.BASE_DIR) / SOURCE).read_text(encoding='utf-8-sig')


def snapshot(rows):
    return json.dumps(list(rows), sort_keys=True, default=lambda value: value.tolist())


class ImportSafetyTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(BASE_DIR=Path(self.directory.name))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.source = Path(self.directory.name) / SOURCE
        self.source.parent.mkdir(parents=True)
        self.source.write_text(TEXT, encoding='utf-8')

    def run_import(self, **options):
        call_command('ingest_about_spus', stdout=StringIO(), **options)

    def model(self):
        return Mock(encode=Mock(return_value=SimpleNamespace(
            tolist=lambda: [[0.001] * 384 for _ in document_entries(TEXT)])))

    def test_document_chunks_preserve_source_and_separate_topics(self):
        entries = dict(document_entries(TEXT))
        self.assertEqual(len(entries), 7)
        self.assertIn('Sisters of St. Paul of Chartres', entries['What is SPUS?'])
        self.assertNotIn('VISION', entries['What is SPUS?'])
        self.assertIn('San Nicolas School', entries['What is the early history of SPUS?'])
        self.assertNotIn('Why Choose SPUS?', entries['What are the complete definitions of the Paulinian core values at SPUS?'])

    def test_dry_run_creates_no_rows_and_loads_no_model(self):
        with patch('chatbot.embedding_runtime.runtime.get_model') as load:
            self.run_import(dry_run=True)
        load.assert_not_called()
        self.assertEqual(FAQ.objects.count(), 0)

    def test_repeat_import_is_idempotent_and_source_is_unchanged(self):
        original = self.source.read_bytes()
        with patch('chatbot.embedding_runtime.runtime.get_model', return_value=self.model()):
            self.run_import()
        before = snapshot(FAQ.objects.order_by('pk').values())
        with patch('chatbot.embedding_runtime.runtime.get_model') as load:
            self.run_import()
        load.assert_not_called()
        self.assertEqual(FAQ.objects.count(), 7)
        self.assertEqual(before, snapshot(FAQ.objects.order_by('pk').values()))
        self.assertTrue(all(len(obj.embedding) == 384 for obj in FAQ.objects.all()))
        self.assertEqual(self.source.read_bytes(), original)

    def test_existing_knowledge_is_reused_without_replacing_metadata(self):
        question, answer = document_entries(TEXT)[0]
        old = FAQ.objects.create(category='Existing', question=question, answer=answer,
                                 source_type='website', embedding=[0.002] * 384)
        before = snapshot(FAQ.objects.filter(pk=old.pk).values())
        self.run_import(dry_run=True)
        self.assertEqual(before, snapshot(FAQ.objects.filter(pk=old.pk).values()))

    def test_conflict_aborts_without_mutating_existing_data(self):
        FAQ.objects.create(category='Existing', question='What is SPUS?', answer='Different reviewed content')
        with self.assertRaises(CommandError), patch('chatbot.embedding_runtime.runtime.get_model') as load:
            self.run_import()
        load.assert_not_called()
        self.assertEqual(FAQ.objects.count(), 1)

    def test_invalid_embedding_or_malformed_source_creates_no_rows(self):
        model = Mock(encode=Mock(return_value=SimpleNamespace(tolist=lambda: [[float('nan')] * 384] * 7)))
        with patch('chatbot.embedding_runtime.runtime.get_model', return_value=model), self.assertRaises(CommandError):
            self.run_import()
        self.assertEqual(FAQ.objects.count(), 0)
        self.source.write_text('Incomplete document', encoding='utf-8')
        with self.assertRaises(CommandError):
            self.run_import()


class ExactFAQTests(SimpleTestCase):
    def faq(self, question='[About SPUS.txt] What is SPUS?', answer='A Catholic educational institution.', pk=1):
        return SimpleNamespace(pk=pk, question=question, answer=answer, category='About SPUS',
                               source_type='curated', source_office=None)

    def test_empty_subject_terms_require_an_exact_stored_question(self):
        result = RAGSearcher._exact_faq_lookup('What is SPUS?', [self.faq()])
        self.assertEqual(len(result), 1)
        self.assertTrue(eligible_evidence('What is SPUS?', result[0]))
        self.assertTrue(eligible_evidence('Tell me about SPUS', result[0]))
        self.assertFalse(eligible_evidence('What is SPUS in 2030?', result[0]))
        self.assertFalse(eligible_evidence('SPUS', result[0]))

    def test_exact_faq_is_generic_and_does_not_drop_constraints(self):
        faq = self.faq('What is the library policy?', 'The library policy requires a valid ID.')
        self.assertEqual(len(RAGSearcher._exact_faq_lookup('What is the library policy', [faq])), 1)
        self.assertEqual(RAGSearcher._exact_faq_lookup('What is the library policy for visitors?', [faq]), [])

    def test_explicit_overview_paraphrases_preserve_subject_in_both_languages(self):
        for query in ('Tell me about SPUS', 'Please give me information about SPUS', 'Ano ang SPUS?'):
            with self.subTest(query=query):
                self.assertEqual(len(RAGSearcher._exact_faq_lookup(query, [self.faq()])), 1)
        for query in ('What is not SPUS?', 'Tell me about SPUS scholarships', 'Ano ang SPUS scholarship?'):
            self.assertEqual(RAGSearcher._exact_faq_lookup(query, [self.faq()]), [])

    def test_conflicting_exact_answers_fail_closed(self):
        result = RAGSearcher._exact_faq_lookup('What is SPUS?', [self.faq(), self.faq(answer='A different answer.', pk=2)])
        self.assertEqual(result.status, 'conflict')
        self.assertEqual(result, [])

    def test_duplicate_exact_answers_return_one_answer_with_provenance(self):
        result = RAGSearcher._exact_faq_lookup('What is SPUS?', [self.faq(), self.faq('What is SPUS?', pk=2)])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['supporting_sources'][0]['record_id'], 2)

    def test_reported_recommendation_question_matches_stored_faq(self):
        faq = self.faq('Why choose SPUS?', 'Faith-Based Education and Academic Excellence.')
        for query in ('why should i choose spus?', 'Why should we choose SPUS?', 'Why should you choose SPUS?'):
            with self.subTest(query=query):
                result = RAGSearcher._exact_faq_lookup(query, [faq])
                self.assertEqual(len(result), 1)
                self.assertTrue(eligible_evidence(query, result[0]))

    def test_recommendation_framing_is_independent_of_knowledge_domain(self):
        for question, query, answer in (
                ('Why use the library?', 'Why should I use the library?', 'The library provides study spaces.'),
                ('Why follow the laboratory policy?', 'Why should we follow the laboratory policy?', 'The laboratory policy protects equipment.'),
                ('Why apply for a scholarship?', 'Why should I apply for a scholarship?', 'A scholarship provides financial assistance.')):
            with self.subTest(query=query):
                self.assertEqual(len(RAGSearcher._exact_faq_lookup(query, [self.faq(question, answer)])), 1)

    def test_recommendation_matching_keeps_negation_audiences_and_constraints(self):
        faq = self.faq('Why choose SPUS?', 'Faith-Based Education and Academic Excellence.')
        for query in (
                'Why should I not choose SPUS?', "Why shouldn't I choose SPUS?",
                'Why should I choose SPUS over other universities?',
                'Why should I choose SPUS in 2030?', 'Why should parents choose SPUS?',
                'Why can I choose SPUS?', 'Why must I choose SPUS?'):
            with self.subTest(query=query):
                self.assertEqual(RAGSearcher._exact_faq_lookup(query, [faq]), [])

    def test_equivalent_recommendation_questions_do_not_hide_source_conflicts(self):
        result = RAGSearcher._exact_faq_lookup('why should i choose spus?', [
            self.faq('Why choose SPUS?', 'Reviewed answer one.'),
            self.faq('Why should I choose SPUS?', 'Different reviewed answer.', pk=2),
        ])
        self.assertEqual(result, [])
        self.assertEqual(result.status, 'conflict')
