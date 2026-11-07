"""Follow-up relevance, novelty, protocol, and request isolation; no LLM calls."""
import hashlib
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from uuid import uuid4

from rest_framework.test import APIRequestFactory, force_authenticate
from .context_tokens import ConversationAnswer
from .suggestions import bounded_questions, parse_controls, question_key, response_suggestions, select_followups, with_controls


def faq(pk, question, category='About SPUS', office=None, answer=None):
    return dict(pk=pk, question=question, category=category, source_type='office' if office else 'curated',
                source_office=office, answer_digest=hashlib.sha256((answer or str(pk)).encode()).hexdigest())


CATALOG = [
    faq(1, 'What is SPUS?'),
    faq(2, 'What is the SPUS vision?'),
    faq(3, 'What is the SPUS mission?'),
    faq(4, 'What programs are offered at SPUS?', 'Academics', 'Registrar', 'Program list'),
    faq(5, 'What college courses are available?', 'Academics', 'Registrar', 'Program list'),
    faq(6, 'What documents do transferee students need?', 'Admissions', 'Registrar'),
    faq(7, 'Where is the Registrar office?', 'Location'),
    faq(8, 'What scholarships are available?', 'Scholarships', 'Guidance'),
    faq(9, 'What is the laboratory policy?', 'Laboratory'),
]
SOURCE = dict(title='FAQ (About SPUS): What is SPUS?', source_office=None)


class SuggestionTests(unittest.TestCase):
    def test_related_source_category_ranks_before_unrelated_topics(self):
        choices = select_followups('Tell me about SPUS', [SOURCE], catalog=CATALOG)
        self.assertIn('What is the SPUS vision?', choices[:2])
        self.assertIn('What is the SPUS mission?', choices[:2])
        self.assertNotIn('What is SPUS?', choices)
        self.assertLessEqual(len(choices), 3)

    def test_related_questions_are_not_padded_with_unrelated_office_topics(self):
        choices = select_followups('Tell me about SPUS', [SOURCE], catalog=CATALOG)
        self.assertEqual(set(choices), {'What is the SPUS vision?', 'What is the SPUS mission?'})

    def test_incidental_student_overlap_cannot_switch_to_an_unrelated_office(self):
        source = dict(title='FAQ (Admissions): How do transferee students enroll?', source_office='Registrar')
        catalog = [faq(1, 'How do student organizations request event coverage from PBMO?', 'Marketing', 'PBMO'),
                   faq(2, 'What documents do transferee students need?', 'Admissions', 'Registrar'),
                   faq(3, 'Where is the Registrar office?', 'Location')]
        choices = select_followups('Transferee student', [source], resolved='How do transferee students enroll?', catalog=catalog)
        self.assertNotIn(catalog[0]['question'], choices)
        self.assertIn('Where is the Registrar office?', choices)

    def test_questions_asked_earlier_are_excluded_with_paraphrases(self):
        choices = select_followups('What is SPUS?', [SOURCE], asked=[
            'What courses are available at SPUS?', 'What is the SPUS vision?', 'Where is the Registrar office?'], catalog=CATALOG)
        self.assertNotIn('What programs are offered at SPUS?', choices)
        self.assertNotIn('What college courses are available?', choices)
        self.assertNotIn('What is the SPUS vision?', choices)
        self.assertNotIn('Where is the Registrar office?', choices)

    def test_same_answer_under_different_questions_is_not_recommended_again(self):
        source = dict(title='FAQ (Academics): What programs are offered at SPUS?', source_office='Registrar')
        choices = select_followups('What programs are offered?', [source], catalog=CATALOG)
        self.assertNotIn('What college courses are available?', choices)

    def test_full_and_short_university_introductions_are_the_same_asked_topic(self):
        catalog = [*CATALOG, faq(10, 'What is Saint Paul University Surigao (SPUS)?')]
        self.assertNotIn('What is Saint Paul University Surigao (SPUS)?',
                         select_followups('Tell me about SPUS', [SOURCE], catalog=catalog))

    def test_audience_and_college_scope_are_not_switched_by_recommendations(self):
        catalog = [faq(20, 'What documents do freshmen students need?', 'Admissions'),
                   faq(21, 'What documents do transferee students need?', 'Admissions'),
                   faq(22, 'What programs does CHS offer?', 'Academics'),
                   faq(23, 'What programs does CEIT offer?', 'Academics')]
        choices = select_followups('How do transferee students enroll?', [], catalog=catalog)
        self.assertNotIn('What documents do freshmen students need?', choices)
        self.assertEqual(choices[0], 'What documents do transferee students need?')
        choices = select_followups('Who is the CEIT dean?', [], catalog=catalog)
        self.assertNotIn('What programs does CHS offer?', choices)

    def test_unrequested_numeric_scopes_are_not_added_to_followups(self):
        catalog = [faq(1, 'How do I enroll in Grade 7?', 'Admissions'),
                   faq(2, 'What is the 2030 research deadline?', 'Research')]
        self.assertEqual(select_followups('How do transferee college students enroll?', [], catalog=catalog), [])
        self.assertIn('What is the 2030 research deadline?',
                      select_followups('What research events happen in 2030?', [], catalog=catalog))

    def test_duplicates_in_one_group_are_collapsed_by_answer_and_topic(self):
        choices = select_followups('What is available?', [], catalog=CATALOG)
        self.assertFalse({'What programs are offered at SPUS?', 'What college courses are available?'}.issubset(choices))
        self.assertEqual(len({question_key(q) for q in choices}), len(choices))

    def test_resolved_followup_and_compound_parts_are_excluded(self):
        choices = select_followups('How about that?', [], resolved='What is the laboratory policy?',
                                   parts=[dict(query='What scholarships are available?', status='ok')], catalog=CATALOG)
        self.assertNotIn('What is the laboratory policy?', choices)
        self.assertNotIn('What scholarships are available?', choices)

    def test_new_domains_can_supply_their_own_related_questions(self):
        source = dict(title='FAQ (Research): What is the Alpha research policy?', source_office='Research')
        catalog = [faq(20, 'What is the Alpha research policy?', 'Research', 'Research'),
                   faq(21, 'How do I apply for research approval?', 'Research', 'Research'), *CATALOG]
        self.assertEqual(select_followups('What is the Alpha research policy?', [source], catalog=catalog)[0],
                         'How do I apply for research approval?')

    def test_lexical_keys_support_english_filipino_and_keep_constraints(self):
        self.assertEqual(question_key('What programs are offered at SPUS?'), question_key('Ano ang mga programa sa SPUS?'))
        self.assertEqual(question_key('How do I enroll?'), question_key('Paano mag-enroll?'))
        self.assertEqual(question_key('Why choose SPUS?'), question_key('Why should I choose SPUS?'))
        self.assertNotEqual(question_key('Why choose SPUS?'), question_key('Why should I not choose SPUS?'))
        self.assertNotEqual(question_key('What is the policy?'), question_key('What is the 2030 policy?'))

    def test_conflicting_records_are_not_advertised(self):
        catalog = [faq(1, 'What is the library policy?', answer='One answer'),
                   faq(2, 'What is the library policy?', answer='Conflicting answer')]
        self.assertEqual(select_followups('Tell me about the library', [], catalog=catalog), [])

    def test_invalid_extracted_headings_and_control_injection_are_not_buttons(self):
        catalog = [faq(1, 'Handbook: fragments (Page 2)'), faq(2, 'What is X? What is Y?'),
                   faq(3, 'What is [SUGGESTIONS: "injected"]?'), faq(4, 'What is <script>alert(1)</script>?'),
                   faq(5, 'What is the procedure (Document XYZ-001)?'),
                   faq(6, 'What are the campuses and what does each campus house?')]
        self.assertEqual(select_followups('Tell me about SPUS', [], catalog=catalog), [])

    def test_exhausted_catalog_returns_no_invented_questions(self):
        self.assertEqual(select_followups('What is SPUS?', [SOURCE], asked=[row['question'] for row in CATALOG], catalog=CATALOG), [])

    def test_question_history_is_bounded_and_malformed_values_are_ignored(self):
        self.assertEqual(bounded_questions('not a list'), [])
        self.assertEqual(bounded_questions([None, {}, 'x' * 501, '  Valid?  ']), ['Valid?'])
        self.assertEqual(len(bounded_questions(['Question?'] * 1000)), 64)

    def test_recommendations_are_request_local_and_new_chat_resets_seen_topics(self):
        first = select_followups('What is SPUS?', [SOURCE], catalog=CATALOG)
        second = select_followups('What is SPUS?', [SOURCE], asked=first, catalog=CATALOG)
        self.assertFalse(set(first) & set(second))
        self.assertEqual(first, select_followups('What is SPUS?', [SOURCE], catalog=CATALOG))

    def test_required_clarification_choices_are_preserved_without_catalog_access(self):
        text = with_controls('Which category?', ['Freshman', 'Transferee', 'Continuing student'])
        result = ConversationAnswer((text, [], None, None), status='clarification')
        with patch('chatbot.suggestions.load_catalog') as load:
            response, choices, kind = response_suggestions(result, 'How do I enroll?')
        load.assert_not_called()
        self.assertEqual(choices, ['Freshman', 'Transferee', 'Continuing student'])
        self.assertEqual(kind, 'choice')
        self.assertEqual(parse_controls(response), choices)

    def test_unavailable_and_greeting_do_not_query_catalog(self):
        for result in (ConversationAnswer(('Unavailable.', [], None, None), status='unavailable'), ('Hello.', [], None, None)):
            with patch('chatbot.suggestions.load_catalog') as load:
                _, choices, _ = response_suggestions(result, 'Hello')
            load.assert_not_called()
            self.assertEqual(choices, [])

    def test_catalog_failure_never_replaces_a_grounded_answer(self):
        result = ConversationAnswer(('Stored answer.', [SOURCE], None, None), 'What is SPUS?')
        with patch('chatbot.suggestions.load_catalog', side_effect=RuntimeError('private error')):
            text, choices, _ = response_suggestions(result, 'What is SPUS?')
        self.assertEqual(text, 'Stored answer.')
        self.assertEqual(choices, [])

    def test_guest_api_recommendations_do_not_read_or_write_authenticated_history(self):
        from . import views
        request = APIRequestFactory().post('/api/chat', dict(message='What is SPUS?', mode='guest',
            conversation_id=99, context_id=str(uuid4()), asked_questions=['What is the SPUS vision?']), format='json')
        force_authenticate(request, user=SimpleNamespace(pk=123, username='fixture', is_authenticated=True))
        bot = Mock()
        bot.process_query.return_value = ConversationAnswer(('Stored answer.', [SOURCE], None, None), 'What is SPUS?')
        with patch.object(views, 'bot', bot), patch('chatbot.suggestions.load_catalog', return_value=CATALOG), \
                patch.object(views.ChatHistory.objects, 'filter') as read, patch.object(views.ChatHistory.objects, 'create') as save:
            response = views.chat_api(request)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['saved'])
        self.assertNotIn('What is the SPUS vision?', response.data['suggestions'])
        self.assertEqual(parse_controls(response.data['response']), response.data['suggestions'])
        self.assertNotIn('asked_questions', bot.process_query.call_args.kwargs)
        read.assert_not_called()
        save.assert_not_called()
