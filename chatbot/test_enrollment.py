"""Enrollment-control regressions using actual Registrar knowledge fixtures.

No test accounts, database writes, model downloads or provider calls are used.
"""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from .enrollment import enrollment_lookup_topic, exact_enrollment_lookup
from .intents import ENROLL_CHOICES, ENROLL_QUESTION, enrollment_resolution
from .logic import PauliBotLogic
from .rag import RAGSearcher


def registrar_rows():
    source = Path(__file__).resolve().parent.parent / 'knowledge_base/office_documents/Registrar/Registrar_knowledge.json'
    return [SimpleNamespace(**item, source_type='office', source_office='Registrar', category="Registrar's Office")
            for item in json.loads(source.read_text(encoding='utf-8'))['items']]


def history(question='How do I enroll at SPUS?'):
    return [{'role': 'user', 'content': question}, {'role': 'assistant', 'content': ENROLL_QUESTION}]


def bot():
    value = PauliBotLogic.__new__(PauliBotLogic)
    value.rag = RAGSearcher()
    value.rag.ensure_embeddings = Mock(side_effect=AssertionError('Exact enrollment must not generate embeddings'))
    value.client = value.openai_client = value.gemini_model = None
    value.model_name = 'test'
    return value


class RegistrarLookupTests(unittest.TestCase):
    def test_all_exact_ui_choices_resolve_with_and_without_history(self):
        for question in ('How do I enroll?', 'How do I enroll at SPUS?'):
            for context in (history(question), []):
                for reply, document in zip(ENROLL_CHOICES, ('URO-PR-005', 'URO-PR-017', 'URO-PR-016')):
                    with self.subTest(question=question, reply=reply, has_history=bool(context)):
                        clarify, query = enrollment_resolution(reply, context)
                        self.assertFalse(clarify)
                        result = exact_enrollment_lookup(query, registrar_rows())
                        self.assertEqual(len(result), 1)
                        self.assertIn(document, result[0]['answer'])
                        self.assertEqual(result[0]['retrieval_method'], 'exact_registrar_enrollment')

    def test_standalone_personal_statement_does_not_assume_enrollment(self):
        statement = 'I am an old student'
        self.assertEqual(enrollment_resolution(statement), (False, statement))

    def test_explicit_category_question_uses_direct_lookup(self):
        for category in ('an old student', 'a transferee', 'an incoming freshman'):
            _, query = enrollment_resolution(f'How do I enroll at SPUS as {category}?')
            self.assertEqual(enrollment_lookup_topic(query), 'procedure')
            self.assertEqual(len(exact_enrollment_lookup(query, registrar_rows())), 1)

    def test_continuing_answer_is_exact_office_excerpt_with_four_steps(self):
        _, query = enrollment_resolution('Old/continuing college student', history())
        rows = registrar_rows()
        result = exact_enrollment_lookup(query, rows)
        answer = result[0]['answer']
        self.assertEqual(answer, next(obj.answer for obj in rows if 'URO-PR-016' in obj.question))
        for step in ('1. Academic Advising', '2. Assessment of Fees', '3. Payment', '4. Encoding and Validation'):
            self.assertIn(step, answer)

    def test_document_request_keeps_document_intent(self):
        _, query = enrollment_resolution('Transferee student', history('What documents do I need to enroll at SPUS?'))
        result = exact_enrollment_lookup(query, registrar_rows())
        self.assertEqual(len(result), 1)
        self.assertIn('Requirements for Transferee', result[0]['answer'])
        self.assertNotIn('5. ICT Office', result[0]['answer'])

    def test_missing_continuing_document_list_does_not_return_a_procedure(self):
        _, query = enrollment_resolution('Old/continuing college student', history('What documents do I need to enroll at SPUS?'))
        self.assertEqual(exact_enrollment_lookup(query, registrar_rows()), [])

    def test_additional_constraints_and_other_levels_do_not_enter_shortcut(self):
        for query in ('How do I enroll as an old student in 2099?',
                      'How do I enroll as an old student at another institution?',
                      'How do I enroll as a graduate continuing student?',
                      'What fees do old students pay for enrollment?',
                      'How do I enroll as a transferee with missing documents?',
                      'How do I enroll as a freshman or transferee?'):
            with self.subTest(query=query):
                self.assertIsNone(enrollment_lookup_topic(query))

    def test_missing_or_wrong_source_fails_closed(self):
        _, query = enrollment_resolution(ENROLL_CHOICES[2], history())
        self.assertEqual(exact_enrollment_lookup(query, []), [])
        rows = registrar_rows()
        for row in rows:
            row.source_type = 'website'
        self.assertEqual(exact_enrollment_lookup(query, rows), [])

    def test_conflicting_office_procedures_do_not_choose_arbitrarily(self):
        _, query = enrollment_resolution(ENROLL_CHOICES[2], history())
        rows = registrar_rows()
        original = next(obj for obj in rows if 'URO-PR-016' in obj.question)
        alternate = SimpleNamespace(**{**vars(original), 'answer': 'Alternative continuing college enrollment procedure.'})
        self.assertEqual(exact_enrollment_lookup(query, rows + [alternate]), [])

    def test_exact_controls_work_without_model_or_provider(self):
        actual_lookup = exact_enrollment_lookup
        value = bot()
        with patch('chatbot.enrollment.exact_enrollment_lookup', side_effect=lambda query: actual_lookup(query, registrar_rows())):
            for reply in ENROLL_CHOICES:
                text, sources, action, _ = value.process_query(reply, history())
                self.assertIn('Enrollment procedure', text)
                self.assertEqual(sources[0]['source_office'], 'Registrar')
                self.assertIsNone(action)
        self.assertIsNone(value.rag.model)
        value.rag.ensure_embeddings.assert_not_called()


class AuthenticatedClarificationTests(unittest.TestCase):
    def test_authenticated_request_without_conversation_id_uses_bounded_context(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from . import views
        user = SimpleNamespace(pk=123, id=123, username='fixture', is_authenticated=True, is_active=True)
        conversation = SimpleNamespace(id=42, title='Fixture', save=Mock())
        request = APIRequestFactory().post('/api/chat', {
            'message': 'Transferee student',
            'mode': 'authenticated',
            'history': history('What documents do I need to enroll at SPUS?'),
        }, format='json')
        force_authenticate(request, user=user)
        value, actual_lookup = bot(), exact_enrollment_lookup
        with patch.object(views, 'bot', value), \
                patch('chatbot.enrollment.exact_enrollment_lookup', side_effect=lambda query: actual_lookup(query, registrar_rows())), \
                patch.object(views.Conversation.objects, 'create', return_value=conversation), \
                patch.object(views.ChatHistory.objects, 'create', return_value=SimpleNamespace(id=1)):
            response = views.chat_api(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Requirements for Transferee', response.data['response'])
        self.assertEqual(response.data['conversation_id'], 42)
        self.assertTrue(response.data['saved'])

    def test_owned_persisted_context_wins_over_client_context(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from . import views
        user = SimpleNamespace(pk=123, id=123, username='fixture', is_authenticated=True, is_active=True)
        conversation = SimpleNamespace(id=42, title='Fixture', save=Mock())
        stored = SimpleNamespace(message='What documents do I need to enroll at SPUS?', response=ENROLL_QUESTION)
        request = APIRequestFactory().post('/api/chat', {
            'message': 'Transferee student', 'conversation_id': 42, 'history': history(),
            'mode': 'authenticated',
        }, format='json')
        force_authenticate(request, user=user)
        value, actual_lookup = bot(), exact_enrollment_lookup
        with patch.object(views, 'bot', value), \
                patch('chatbot.enrollment.exact_enrollment_lookup', side_effect=lambda query: actual_lookup(query, registrar_rows())), \
                patch.object(views.Conversation.objects, 'get', return_value=conversation), \
                patch.object(views.ChatHistory.objects, 'filter') as fetch, \
                patch.object(views.ChatHistory.objects, 'create', return_value=SimpleNamespace(id=1)):
            fetch.return_value.order_by.return_value = [stored]
            response = views.chat_api(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Requirements for Transferee', response.data['response'])
        fetch.assert_called_once_with(conversation_id=42, user=user, conversation__is_active=True)


if __name__ == '__main__':
    unittest.main()
