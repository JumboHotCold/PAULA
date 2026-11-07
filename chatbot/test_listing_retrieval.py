"""Constraint-preserving FAQ lookup before vector retrieval; fictional fixtures."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from django.test import TestCase
from .grounding import eligible_evidence
from .logic import PauliBotLogic
from .models import FAQ
from .intents import normalize_query
from .query_understanding import listing_signature
from .rag import RAGSearcher


def faq(question='What programs are offered at SPUS?', answer='Fixture: BS Information Technology and BS Nursing.', pk=1):
    return SimpleNamespace(pk=pk, question=question, answer=answer, category='Fixture', source_type='office', source_office='Registrar')


class ListingSignatureTests(unittest.TestCase):
    def test_equivalent_question_frames_and_languages(self):
        signature = listing_signature('What programs are offered at SPUS?')
        for query in ('What programs are offered?', 'Which courses are available?', 'What courses does SPUS offer?',
                      'What are the available programs?', 'What are the programs offered?', 'List programs',
                      'Please show available courses', 'Anong mga kursong inaalok sa SPUS?',
                      'Ano ang mga programa na offered?', 'Anong available na mga kurso sa SPUS?'):
            with self.subTest(query=query):
                self.assertEqual(listing_signature(query), signature)

    def test_generic_listing_grammar_extends_to_other_and_future_subjects(self):
        for subject in ('scholarships', 'library services', 'laboratory facilities', 'Nova research grants'):
            self.assertEqual(listing_signature(f'List {subject}'), listing_signature(f'What {subject} are available?'))

    def test_subject_scope_and_request_type_are_not_dropped(self):
        broad = listing_signature('What programs are offered?')
        for query in ('What graduate programs are offered?', 'What programs are offered at CEIT?',
                      'What online programs are offered?', 'What programs are offered by another university?',
                      'What scholarships are offered?', 'How many programs are offered?', 'Why are programs offered?'):
            self.assertNotEqual(listing_signature(query), broad, query)

    def test_constraint_and_multi_question_frames_do_not_enter_equivalent_lookup(self):
        for query in ('What programs are not offered?', 'What programs are offered in 2030?',
                      'List only online programs', 'List all programs', 'What programs are currently offered?',
                      'What programs are offered? What are the fees?', 'What programs or scholarships are offered?'):
            self.assertIsNone(listing_signature(query), query)

    def test_different_scoped_faq_cannot_answer_broad_query(self):
        for question in ('What CEIT programs are offered?', 'What graduate programs are available?'):
            self.assertFalse(RAGSearcher._exact_faq_lookup('What programs are offered?', [faq(question)]))

    def test_duplicates_preserve_provenance_and_conflicts_abstain(self):
        row = faq()
        duplicate = faq('Which programs are available?', pk=2)
        result = RAGSearcher._exact_faq_lookup('List programs', [row, duplicate])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['supporting_sources'][0]['record_id'], 2)
        conflicting = faq('Which programs are available?', answer='Different stored list.', pk=3)
        self.assertEqual(RAGSearcher._exact_faq_lookup('List programs', [row, conflicting]).status, 'conflict')

    def test_literal_question_is_representative_for_matching_equivalent_sources(self):
        exact = faq('What programs are offered?', 'Exact fixture text.')
        result = RAGSearcher._exact_faq_lookup(exact.question, [faq(answer=exact.answer, pk=2), exact])
        self.assertEqual(result[0]['answer'], exact.answer)
        self.assertEqual(result[0]['record_id'], exact.pk)
        self.assertEqual(result[0]['retrieval_method'], 'exact_faq_question')

    def test_literal_match_does_not_hide_conflicting_equivalent_answer(self):
        exact = faq('What programs are offered?', 'Conflicting fixture text.')
        self.assertEqual(RAGSearcher._exact_faq_lookup(exact.question, [exact, faq(pk=2)]).status, 'conflict')

    def test_scoped_alias_is_bound_without_inheriting_unrelated_question_words(self):
        row = faq('What programs does the College of Engineering and Information Technology offer? Does SPUS offer Engineering?')
        result = RAGSearcher._exact_faq_lookup('What programs are offered at CEIT?', [row])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['retrieval_method'], 'equivalent_faq_alias')
        self.assertIn('College of Engineering', result[0]['matched_question'])
        self.assertEqual(result[0]['question'], row.question)
        self.assertTrue(eligible_evidence('What programs are offered at CEIT?', result[0]))

    def test_multiclause_source_does_not_match_unmentioned_scope(self):
        row = faq('What CEIT programs are offered? What CHS programs are offered?')
        self.assertFalse(RAGSearcher._exact_faq_lookup('What programs are offered at CBMA?', [row]))

    def test_single_question_source_precedes_combined_alias_record(self):
        single = faq()
        combined = faq('What programs are offered at SPUS? What courses are available?', answer='Broader combined source.', pk=2)
        result = RAGSearcher._exact_faq_lookup('What programs are offered?', [combined, single])
        self.assertEqual(result[0]['record_id'], single.pk)

    def test_conflicts_between_fallback_aliases_still_abstain(self):
        first = faq('What programs are offered? What courses are available?')
        second = faq('Which programs are available? What degrees are available?', answer='Different list.', pk=2)
        self.assertEqual(RAGSearcher._exact_faq_lookup('List programs', [first, second]).status, 'conflict')

    def test_equivalent_lookup_still_uses_grounding(self):
        row = faq(answer='')
        self.assertFalse(RAGSearcher._exact_faq_lookup('What programs are offered?', [row]))


class PostgreSQLListingTests(TestCase):
    def setUp(self):
        self.catalog = FAQ.objects.create(question='What programs are offered at SPUS?',
            answer='Fixture: BS Information Technology and BS Nursing.', category='Fixture', source_type='office', source_office='Registrar')
        self.bot = PauliBotLogic.__new__(PauliBotLogic)
        self.bot.rag = RAGSearcher()
        self.bot.rag._hybrid_search = Mock(side_effect=AssertionError('Equivalent FAQ should not embed'))
        self.bot.client = self.bot.openai_client = self.bot.gemini_model = None
        self.bot.model_name = 'test'

    def test_short_queries_use_stored_evidence_without_embedding_or_provider(self):
        for query in ('What programs are offered?', 'What progrms are offered?', 'Which courses are available?',
                      'Anong mga kursong inaalok sa SPUS?'):
            with self.subTest(query=query):
                result = self.bot.process_query(query)
                self.assertIn(self.catalog.answer, result[0])
                self.assertEqual(len(result[1]), 1)
                self.assertTrue(eligible_evidence(normalize_query(query), dict(question=self.catalog.question, answer=self.catalog.answer, record_type='faq')))
        self.bot.rag._hybrid_search.assert_not_called()

    def test_conflicting_equivalent_records_do_not_reach_generation(self):
        FAQ.objects.create(question='Which programs are available?', answer='Different fixture list.', category='Fixture')
        result = self.bot.process_query('What programs are offered?')
        self.assertEqual(result.answer_status, 'conflict')
        self.assertFalse(result[1])

    def test_scoped_program_followup_retrieves_the_new_college_only(self):
        previous = 'What programs are offered at CEIT?'
        FAQ.objects.create(question='What programs does the College of Engineering and Information Technology offer? Does SPUS offer Engineering?',
            answer='CEIT fixture: Engineering Alpha and Technology Beta.', category='Fixture')
        FAQ.objects.create(question='What programs does the College of Health Sciences offer? Does SPUS offer Nursing?',
            answer='CHS fixture: Health Gamma.', category='Fixture')
        result = self.bot.process_query(previous)
        self.assertIn('Engineering Alpha', result[0])
        followup = self.bot.process_query('How about CHS?', history=[
            dict(role='user', content=previous), dict(role='assistant', content=result[0])])
        self.assertIn('Health Gamma', followup[0])
        self.assertNotIn('Engineering Alpha', followup[0])
        self.assertEqual(len(followup[1]), 1)
        self.bot.rag._hybrid_search.assert_not_called()

    def test_explicit_topic_switch_does_not_reuse_catalog_as_enrollment_evidence(self):
        result = self.bot.process_query('How do I enroll?', history=[
            dict(role='user', content='What programs are offered?'), dict(role='assistant', content=self.catalog.answer)])
        self.assertIn('Are you enrolling', result[0])
        self.assertFalse(result[1])
