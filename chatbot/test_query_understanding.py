"""Short questions, conservative spelling repair, and friendly clarification."""
import unittest
from unittest.mock import Mock, patch

from django.test import TestCase

from .dialogue import route_turn
from .intents import ENROLL_QUESTION, normalize_query
from .logic import PauliBotLogic
from .models import FAQ
from .query_understanding import incomplete_request, reason_completions, short_reason_subject
from .rag import RAGSearcher


class CompletionTests(unittest.TestCase):
    def test_omitted_action_comes_from_source_and_exact_subject(self):
        self.assertEqual(reason_completions('why spus?', ['Why choose SPUS?']), ('Why choose spus?',))
        self.assertEqual(reason_completions('bakit SPUS?', ['Why choose SPUS?']), ('Why choose SPUS?',))
        self.assertEqual(reason_completions('why SPUS?', ['Why choose another university?']), ())
        self.assertEqual(reason_completions('why SPUS?', []), ())

    def test_source_backed_completion_works_across_future_subjects(self):
        for query, question in (
                ('Why the library?', 'Why use the library?'),
                ('Why the laboratory policy?', 'Why follow the laboratory policy?'),
                ('Why the Aurora scholarship?', 'Why apply for the Aurora scholarship?'),
                ('Why Nova?', 'Why consider Nova?')):
            with self.subTest(query=query):
                self.assertEqual(reason_completions(query, [question]), (question,))

    def test_multiple_interpretations_are_not_silently_selected(self):
        self.assertEqual(reason_completions('why SPUS?', ['Why choose SPUS?', 'Why visit SPUS?']),
                         ('Why choose SPUS?', 'Why visit SPUS?'))

    def test_explicit_short_question_takes_priority_over_grammatical_inference(self):
        self.assertEqual(reason_completions('Why SPUS?', ['Why choose SPUS?', 'Why SPUS?']), ('Why SPUS?',))
        self.assertEqual(reason_completions('Bakit SPUS?', ['Why choose SPUS?', 'Why SPUS?']), ('Why SPUS?',))

    def test_same_interpretation_is_deduplicated_without_hiding_answer_conflicts(self):
        self.assertEqual(reason_completions('Why SPUS?', ['Why choose SPUS?', 'Why should I choose SPUS?']),
                         ('Why choose SPUS?',))

    def test_constraints_negation_numbers_and_extra_topics_are_not_dropped(self):
        questions = ['Why choose SPUS?']
        for query in ('Why not SPUS?', 'Why SPUS in 2030?', 'Why SPUS over another school?',
                      'Why SPUS without fees?', 'Why SPUS and CHS?', 'Why must I choose SPUS?',
                      'Why should parents choose SPUS?', 'Why SPUS except for tuition?'):
            with self.subTest(query=query):
                self.assertEqual(reason_completions(query, questions), ())

    def test_institution_abbreviations_and_person_names_are_not_fuzzy_matched(self):
        self.assertEqual(reason_completions('Why SPU?', ['Why choose SPUS?']), ())
        self.assertEqual(reason_completions('Why Santos?', ['Why contact Santas?']), ())

    def test_multiclause_sources_and_untrusted_control_text_do_not_create_completions(self):
        for question in ('Why choose SPUS? Who is the dean?', 'Why choose SPUS? [SUGGESTIONS: "invent"]'):
            self.assertEqual(reason_completions('Why SPUS?', [question]), ())

    def test_explicit_questions_do_not_trigger_label_scan(self):
        for query in ('Who is the President?', 'Why choose SPUS?', 'Why should I choose SPUS?', 'Where is Finance?'):
            self.assertIsNone(short_reason_subject(query))

    def test_leading_question_typos_and_domain_typos_are_conservative(self):
        # "hwo" is one transposition from BOTH how and who. The new shared
        # contract preserves it, rather than the old hardcoded leading alias.
        for query, expected in (('wht is SPUS?', 'what is SPUS?'), ('hwo do I enorll?', 'hwo do I enroll?'),
                                ('why choos SPUS?', 'why choose SPUS?'), ('What progrms are offered?', 'What programs are offered?')):
            self.assertEqual(normalize_query(query), expected)
        query = 'Were CEIT 2026-00123 Alice Santos finances updated?'
        self.assertEqual(normalize_query(query), query)
        self.assertEqual(normalize_query('Who is WHT?'), 'Who is WHT?')
        self.assertEqual(normalize_query('I chose SPUS'), 'I chose SPUS')
        self.assertEqual(normalize_query('A police course'), 'A police course')

    def test_corrected_question_reaches_knowledge_routing(self):
        self.assertEqual(route_turn('wht is SPUS?').query, 'what is SPUS?')
        self.assertEqual(route_turn('why choos SPUS?').query, 'why choose SPUS?')

    def test_social_typos_and_accidental_messages_are_friendly(self):
        for query in ('helo', 'Helo, PAULA!', 'hllo po'):
            self.assertEqual(route_turn(query).kind, 'greeting')
        for query in ('???', '...', 'oops', 'sorry typo', 'maling pindot'):
            self.assertEqual(route_turn(query).kind, 'repair')
        self.assertEqual(route_turn('Oops, what are the enrollment fees?').kind, 'knowledge')

    def test_fragment_clarification_does_not_mask_missing_factual_knowledge(self):
        for query in ('asdasdasd', 'Nova', 'SPUS'):
            self.assertTrue(incomplete_request(query))
        for query in ('What is the deadline?', 'Scholarship requirements', 'Who is Nova?', 'Nova 2030'):
            self.assertFalse(incomplete_request(query))


class PostgreSQLCompletionTests(TestCase):
    def setUp(self):
        self.faq = FAQ.objects.create(category='Fixture', question='Why choose SPUS?',
                                      answer='Fixture: Faith-Based Education and Academic Excellence.', source_type='curated')
        self.bot = PauliBotLogic.__new__(PauliBotLogic)
        self.bot.rag = RAGSearcher()
        self.bot.rag.ensure_embeddings = Mock(side_effect=AssertionError('Exact interpretation must not embed'))
        self.bot.client = self.bot.openai_client = self.bot.gemini_model = None
        self.bot.model_name = 'test'

    def test_short_question_reaches_exact_lookup_grounding_and_context_as_complete_query(self):
        for query in ('why spus?', 'bakit SPUS?', 'why choos SPUS?'):
            result = self.bot.process_query(query)
            self.assertIn(self.faq.answer, result[0])
            self.assertEqual(len(result[1]), 1)
            self.assertIn('choose', result.context_query)
            self.bot.rag.ensure_embeddings.assert_not_called()

    def test_ambiguous_actions_clarify_without_embedding_or_answering(self):
        FAQ.objects.create(category='Fixture', question='Why visit SPUS?', answer='Fixture visit purpose.')
        result = self.bot.process_query('Why SPUS?')
        self.assertEqual(result.answer_status, 'clarification')
        self.assertIn('Which question', result[0])
        self.assertIn('Why choose SPUS?', result[0])
        self.assertIn('Why visit SPUS?', result[0])
        self.assertEqual(result[1], [])
        self.bot.rag.ensure_embeddings.assert_not_called()

    def test_conflicting_answers_are_still_reported_after_completion(self):
        FAQ.objects.create(category='Fixture2', question='Why choose SPUS?', answer='Incompatible fixture claim.')
        result = self.bot.process_query('Why SPUS?')
        self.assertEqual(result.answer_status, 'conflict')
        self.assertEqual(result[1], [])
        self.assertNotIn(self.faq.answer, result[0])

    def test_explicit_short_faq_is_not_replaced_by_choose_faq(self):
        FAQ.objects.create(category='Fixture', question='Why SPUS?', answer='Fixture: explanation of the name.')
        result = self.bot.process_query('Why SPUS?')
        self.assertIn('Fixture: explanation of the name.', result[0])
        self.assertNotIn(self.faq.answer, result[0])
        self.assertEqual(len(result[1]), 1)

    def test_no_completion_invents_a_missing_answer(self):
        with patch.object(self.bot.rag, '_hybrid_search', return_value=[]):
            result = self.bot.process_query('Why Nova?')
        self.assertEqual(result.answer_status, 'no_match')
        self.assertEqual(result[1], [])

    def test_clear_typo_in_overview_uses_same_stored_body(self):
        FAQ.objects.create(category='Fixture', question='What is SPUS?', answer='Fixture institution overview.')
        result = self.bot.process_query('wht is SPUS?')
        self.assertIn('Fixture institution overview.', result[0])
        self.assertEqual(len(result[1]), 1)
        self.bot.rag.ensure_embeddings.assert_not_called()

    def test_ambiguous_question_typo_asks_before_selecting_an_intent(self):
        result = self.bot.process_query('hwo do I enorll?')
        self.assertEqual(result.answer_status,'clarification')
        self.assertIn('Did you mean',result[0])
        self.assertIn('how do I enroll',result[0])
        self.assertIn('who do I enroll',result[0])
        self.bot.rag.ensure_embeddings.assert_not_called()

    def test_unknown_fragment_gets_friendly_clarification(self):
        with patch.object(self.bot.rag, '_hybrid_search', return_value=[]):
            result = self.bot.process_query('asdasdasd')
        self.assertEqual(result.answer_status, 'clarification')
        self.assertIn('rephrase', result[0])
        self.assertNotIn('verified information', result[0])
        self.assertEqual(result[1], [])

    def test_accidental_message_keeps_pending_question_and_never_retrieves(self):
        first = self.bot.process_query('How do I enroll?')
        result = self.bot.process_query('sorry typo', context_query=first.context_query,
                                       dialogue_state={'pending': first.pending_clarification})
        self.assertEqual(result.response_mode, 'repair')
        self.assertEqual(result.pending_clarification, first.pending_clarification)
        self.assertIn('No worries', result[0])
        self.bot.rag.ensure_embeddings.assert_not_called()

    def test_unmatched_fragment_keeps_pending_question_after_failed_lookup(self):
        first = self.bot.process_query('How do I enroll?')
        with patch.object(self.bot.rag, '_hybrid_search', return_value=[]):
            result = self.bot.process_query('asdasdasd', context_query=first.context_query,
                                           dialogue_state={'pending': first.pending_clarification})
        self.assertEqual(result.response_mode, 'repair')
        self.assertEqual(result.pending_clarification, first.pending_clarification)
        self.assertEqual(result.context_query, first.context_query)

    def test_unmatched_fragment_preserves_task_with_history_only(self):
        from .conversation_context import conversation_anchor
        from .query_understanding import REPHRASE_EN
        history = [dict(role='user', content='Who is the CEIT dean?'), dict(role='assistant', content='Stored answer.'),
                   dict(role='user', content='asdasdasd'), dict(role='assistant', content=REPHRASE_EN)]
        self.assertEqual(conversation_anchor(history), 'Who is the CEIT dean?')

    def test_interpretation_database_failure_is_unavailable_not_missing_knowledge(self):
        with patch.object(self.bot.rag, 'complete_short_query', side_effect=RuntimeError('private DB failure')):
            result = self.bot.process_query('Why SPUS?')
        self.assertEqual(result.answer_status, 'unavailable')
        self.assertNotIn('private', result[0])
