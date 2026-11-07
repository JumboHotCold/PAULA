"""Self-introduction, related suggestion support, and announcement precedence."""
import unittest
from unittest.mock import Mock, patch

from django.test import TestCase

from .context_tokens import ConversationAnswer
from .dialogue import route_turn
from .logic import PauliBotLogic
from .models import FAQ, Announcement
from .rag import RAGSearcher
from .retrieval_types import EvidenceList
from .suggestions import load_catalog, response_suggestions, select_followups, starter_questions
from .test_suggestions import faq

PBMO = 'How are announcements and promotional materials broadcast across the SPUS campus?'


def bot():
    value = PauliBotLogic.__new__(PauliBotLogic)
    value.rag = RAGSearcher()
    value.rag.ensure_embeddings = Mock(side_effect=AssertionError('No vector search expected'))
    value.client = value.openai_client = value.gemini_model = None
    value.model_name = 'test'
    return value


class IdentityTests(unittest.TestCase):
    def test_self_introduction_paraphrases_use_whole_message_grammar(self):
        for text in ('who you?', 'Who are u?', 'who r u', 'tell me about yourself?', 'Please introduce yourself',
                     'Could you introduce yourself?', 'Describe yourself please', "What's your name?", 'Who is PAULA?',
                     'Sino ka ba?', 'Pakilala ka naman', 'Magpakilala ka po', 'Hi! Who you?',
                     'What are you?', 'What do you do?', 'What is your purpose?', 'Tell me about you'):
            with self.subTest(text=text):
                self.assertEqual(route_turn(text).kind, 'identity')

    def test_self_reference_does_not_capture_people_or_mixed_fact_requests(self):
        for text in ('Who is the university president?', 'Who is your ICT director?', 'Who are you and who is the CEIT dean?',
                     'Tell me about yourself and the tuition fees', 'Tell me about the Registrar office',
                     'What does PAULA know about scholarship requirements?'):
            self.assertEqual(route_turn(text).kind, 'knowledge', text)

    def test_intro_needs_no_retrieval_or_provider(self):
        value = bot()
        value.client = Mock()
        value.rag.search = Mock(side_effect=AssertionError('No retrieval needed'))
        result = value.process_query('who you?')
        self.assertEqual(result.response_mode, 'identity')
        self.assertIn('Paulinian Artificial User Support and Learning Assistant', result[0])
        self.assertIn('St. Paul University Surigao', result[0])
        self.assertIn("I'm an AI assistant", result[0])
        self.assertIn('campus navigation', result[0])
        self.assertEqual(result[1], [])
        value.client.chat.completions.create.assert_not_called()

    def test_intro_does_not_replace_pending_task(self):
        value = bot()
        first = value.process_query('How do I enroll?')
        result = value.process_query('tell me about yourself?', context_query=first.context_query,
                                    dialogue_state={'pending': first.pending_clarification})
        self.assertEqual(result.pending_clarification, first.pending_clarification)
        self.assertEqual(result.context_query, first.context_query)

    def test_filipino_introduction_uses_filipino_framing(self):
        result = bot().process_query('Pakilala ka naman')
        self.assertTrue(result[0].startswith('Kumusta! Ako si PAULA'))


class SuggestionContracts(unittest.TestCase):
    def test_zero_relevance_never_falls_back_to_random_offices(self):
        catalog = [faq(1, 'What are the PBMO posting rules?', 'Marketing', 'PBMO'),
                   faq(2, 'What programs are offered at SPUS?', 'Academics')]
        self.assertEqual(select_followups('Tell me about quantum entanglement', [], catalog=catalog), [])

    def test_generic_student_or_campus_overlap_is_not_a_topic_match(self):
        catalog = [faq(1, 'How do students submit campus posters to PBMO?', 'Marketing', 'PBMO')]
        self.assertEqual(select_followups('What student help is there on campus?', [], catalog=catalog), [])

    def test_conflict_hidden_in_excluded_source_is_not_recommended(self):
        one = faq(1, 'What is the library policy?', 'Library', answer='One claim')
        other = {**faq(2, 'What is the library policy?', 'Library', answer='Other claim'), 'source_type': 'handbook'}
        self.assertEqual(select_followups('Tell me about the library', [], catalog=[one, other]), [])

    def test_long_document_questions_are_not_faq_buttons(self):
        long = 'What is the detailed procedure for ' + 'submitting official materials ' * 3 + 'to PBMO?'
        short = 'Do posters require PBMO review?'
        choices = select_followups('How do I post a PBMO poster?', [], catalog=[faq(1, long), faq(2, short)])
        self.assertNotIn(long, choices)
        self.assertIn(short, choices)

    def test_responsible_office_location_ranks_before_unrelated_internal_form(self):
        source = dict(title='FAQ (Academics): What programs are offered at SPUS?', source_office='Registrar')
        choices = select_followups('What programs are offered at SPUS?', [source], catalog=[
            faq(1, 'Who must approve the subject withdrawal form?', 'Procedures', 'Registrar'),
            faq(2, 'Where is the Registrar office?', 'Location')])
        self.assertEqual(choices[0], 'Where is the Registrar office?')

    def test_legacy_information_headings_do_not_become_buttons(self):
        catalog = [faq(1, 'What is the courses information?', 'Courses'),
                   faq(2, 'What programs are offered at SPUS?', 'Academics')]
        choices = select_followups('What courses are available?', [], catalog=catalog)
        self.assertNotIn(catalog[0]['question'], choices)

    def test_unsupported_empty_or_unready_records_are_not_advertised(self):
        for extra in ({'answer': ''}, {'embedding_ready': False}, {'source_type': 'handbook'}):
            record = {**faq(1, 'What programs are offered at SPUS?'), **extra}
            self.assertEqual(select_followups('Tell me about programs', [], catalog=[record]), [])

    def test_personnel_identity_needs_more_than_a_single_faq_claim(self):
        record = faq(1, 'Who is the PBMO director?', 'Marketing', 'PBMO')
        self.assertEqual(select_followups('Tell me about PBMO', [], catalog=[record]), [])

    def test_introduction_choices_are_not_required_clarification_controls(self):
        result = ConversationAnswer(('Introduction.', [], None, None), status='social', mode='identity')
        with patch('chatbot.suggestions.starter_questions', return_value=['Where is the Registrar office?']):
            _, choices, kind = response_suggestions(result, 'who you?', catalog=[])
        self.assertEqual(choices, ['Where is the Registrar office?'])
        self.assertEqual(kind, 'related')


class PostgreSQLSuggestionTests(TestCase):
    def setUp(self):
        FAQ.objects.create(category='Academics', question='What programs are offered at SPUS?',
                           answer='Fixture program catalog.', embedding=[.01]*384)
        self.pbmo = FAQ.objects.create(category='PBMO', source_type='office', source_office='PBMO',
            question='[PBMO] ' + PBMO, answer='Fixture: announcements use campus screens and the public portal.', embedding=[.01]*384)

    def test_pbmo_announcement_question_uses_exact_faq_before_empty_news_table(self):
        value = bot()
        with patch.object(value.rag, '_announcements', side_effect=AssertionError('FAQ must take precedence')):
            result = value.process_query(PBMO)
        self.assertIn(self.pbmo.answer, result[0])
        self.assertEqual(result[1][0]['source_office'], 'PBMO')
        value.rag.ensure_embeddings.assert_not_called()

    def test_exact_faq_conflict_is_not_hidden_by_announcement_routing(self):
        FAQ.objects.create(category='PBMO', question=PBMO, answer='Contradictory fixture.')
        value = bot()
        result = value.process_query(PBMO)
        self.assertEqual(result.answer_status, 'conflict')
        self.assertEqual(result[1], [])

    def test_empty_news_lookup_allows_existing_hybrid_fallback(self):
        value = bot()
        with patch.object(value.rag, '_hybrid_search', return_value=[]) as hybrid:
            value.rag.search('How are missing announcements distributed?')
        hybrid.assert_called_once()

    def test_actual_news_requests_can_still_use_active_announcements(self):
        Announcement.objects.create(title='Fixture announcement', content='Public fixture announcement.')
        value = bot()
        result = value.rag.search('What are the latest announcements?')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['source_type'], 'announcement')

    def test_catalog_does_not_read_embedding_arrays_or_users(self):
        with self.assertNumQueries(1):
            catalog = load_catalog()
        self.assertTrue(catalog)
        self.assertNotIn('embedding', catalog[0])
        self.assertIn('embedding_ready', catalog[0])
        self.assertIn('answer', catalog[0])

    def test_missing_enrollment_sources_do_not_advertise_unsupported_enrollment(self):
        choices = starter_questions(load_catalog())
        self.assertIn('What programs are offered at SPUS?', choices)
        self.assertIn('Where is the Registrar office?', choices)
        self.assertNotIn('How do I enroll at SPUS?', choices)

    def test_clicked_program_starter_uses_exact_source(self):
        choices = starter_questions(load_catalog())
        result = bot().process_query(choices[0])
        self.assertIn('Fixture program catalog.', result[0])
        self.assertEqual(len(result[1]), 1)

    def test_onboarding_choices_respect_seen_question_history(self):
        choices = starter_questions(load_catalog(), ['What courses are offered at SPUS?', 'Where is the Registrar office?'])
        self.assertEqual(choices, [])

    def test_real_catalog_recommendations_pass_same_exact_grounding(self):
        FAQ.objects.create(category='PBMO', question='Do posters need PBMO review?', source_type='office', source_office='PBMO',
                           answer='Fixture: posters need PBMO review.', embedding=[.01]*384)
        result = bot().process_query(PBMO)
        _, questions, _ = response_suggestions(result, PBMO)
        self.assertTrue(questions)
        for question in questions:
            rows = RAGSearcher._exact_faq_lookup(question)
            self.assertEqual(len(rows), 1)
