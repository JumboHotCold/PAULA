"""Distinct internal reasons, correlation IDs and opt-in text logging without history writes."""
import json
from unittest.mock import Mock, patch
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from . import views
from .context_tokens import ConversationAnswer
from .dialogue import route_turn
from .models import ChatHistory, Conversation, CustomUser
from .performance import capture_trace
from .rag import RAGSearcher


def records(logs):
    return [json.loads(line.split(':', 2)[2]) for line in logs.output]


class PipelineDiagnosticsTests(SimpleTestCase):
    def test_classifier_error_has_its_own_reason_and_no_payload(self):
        with capture_trace() as trace, patch('chatbot.dialogue.social_router.classify', side_effect=RuntimeError('PRIVATE internal error')), \
                self.assertLogs('paula.performance') as logs:
            result = route_turn('What do you know about Nova?')
        self.assertEqual(result.kind, 'knowledge')
        event = records(logs)[0]
        self.assertEqual(event['reason_code'], 'CLASSIFIER_ERROR')
        self.assertEqual(event['request_id'], trace.request_id)
        self.assertNotIn('PRIVATE', str(logs.output))
        self.assertNotIn('Nova', str(logs.output))

    def test_retrieval_errors_and_no_match_are_distinct_and_redacted(self):
        rag = RAGSearcher()
        for error, code in ((RuntimeError('PRIVATE provider detail'), 'RETRIEVAL_ERROR'),
                            (DatabaseError('PRIVATE SQL'), 'DB_ERROR')):
            with capture_trace() as trace, patch.object(rag, 'search', side_effect=error), self.assertLogs('paula.performance') as logs:
                self.assertEqual(rag.retrieve('PRIVATE question').status, 'unavailable')
            event = records(logs)[0]
            self.assertEqual(event['reason_code'], code)
            self.assertEqual(event['request_id'], trace.request_id)
            self.assertNotIn('PRIVATE', str(logs.output))
        with capture_trace() as trace, patch.object(rag, 'search', return_value=[]), self.assertLogs('paula.performance') as logs:
            self.assertEqual(rag.retrieve('PRIVATE question').status, 'no_match')
        self.assertEqual(records(logs)[0]['reason_code'], 'NO_MATCH')
        self.assertEqual(records(logs)[0]['request_id'], trace.request_id)
        self.assertNotIn('PRIVATE', str(logs.output))

    @override_settings(PAULA_LOG_UNANSWERED_QUERIES=False)
    def test_default_no_match_diagnostics_do_not_log_submitted_text(self):
        fake = Mock()
        fake.process_query.return_value = ConversationAnswer(('No verified source.', [], None, None), status='no_match')
        with capture_trace() as trace, patch.object(views, 'bot', fake), self.assertLogs('paula.performance') as logs, self.assertNoLogs('paula.rehearsal'):
            response = views.chat_api(APIRequestFactory().post('/api/chat', {'message': 'PRIVATE unanswered message', 'mode': 'guest'}, format='json'))
        self.assertFalse(response.data['saved'])
        self.assertEqual(records(logs)[0]['reason_code'], 'NO_MATCH')
        self.assertEqual(records(logs)[0]['request_id'], trace.request_id)
        self.assertNotIn('PRIVATE', str(logs.output))

    @override_settings(PAULA_LOG_UNANSWERED_QUERIES=True)
    def test_answered_social_turns_are_not_logged_as_unanswered(self):
        with self.assertNoLogs('paula.rehearsal'):
            result = views.chat_api(APIRequestFactory().post('/api/chat', {'message': 'ty', 'mode': 'guest'}, format='json'))
        self.assertEqual(result.data['response_mode'], 'thanks')


class GuestRehearsalPrivacyTests(TestCase):
    @override_settings(PAULA_LOG_UNANSWERED_QUERIES=True)
    def test_opt_in_logs_only_submitted_text_and_never_creates_guest_history(self):
        user = CustomUser.objects.create_user(username='fixture-rehearsal', student_id='fixture-rehearsal', password='fixture-only')
        fake = Mock()
        fake.process_query.return_value = ConversationAnswer(('No verified source.', [], None, None), status='no_match')
        query = 'Synthetic unanswered\nquestion'
        request = APIRequestFactory().post('/api/chat', {'message': query, 'mode': 'guest', 'context_id': 'fixture-context'}, format='json')
        force_authenticate(request, user=user)
        with capture_trace() as trace, patch.object(views, 'bot', fake), self.assertLogs('paula.rehearsal') as logs:
            response = views.chat_api(request)
        event = records(logs)[0]
        self.assertEqual(event, {'event': 'unanswered_query_rehearsal', 'request_id': trace.request_id, 'reason_code': 'NO_MATCH', 'query_text': query})
        self.assertNotIn('\n', logs.output[0])
        self.assertFalse(response.data['saved'])
        self.assertIsNone(response.data['conversation_id'])
        self.assertEqual(ChatHistory.objects.count(), 0)
        self.assertEqual(Conversation.objects.count(), 0)
