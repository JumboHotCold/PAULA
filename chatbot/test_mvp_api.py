"""Error contracts, health fault isolation, and source-selection diagnostics."""
from unittest.mock import Mock, patch
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory
from . import views
from .context_tokens import ConversationAnswer
from .health import knowledge_health, service_readiness
from .logic import PauliBotLogic
from .models import FAQ
from .rag import RAGSearcher


class APIContracts(SimpleTestCase):
    def test_malformed_json_and_non_object_payloads_are_client_errors(self):
        factory = APIRequestFactory()
        for request in (factory.generic('POST', '/api/chat', '{', content_type='application/json'),
                        factory.post('/api/chat', [], format='json'),
                        factory.post('/api/chat', 'ty', format='json')):
            result = views.chat_api(request)
            self.assertEqual(result.status_code, 400)
            self.assertIn('error_code', result.data)

    def test_invalid_ids_and_message_types_never_reach_logic(self):
        value = Mock()
        with patch.object(views, 'bot', value):
            for payload in ({'message': {}}, {'message': ' '}, {'message': 'x' * 2001},
                            {'message': 'ty', 'conversation_id': []}, {'message': 'ty', 'conversation_id': True},
                            {'message': 'ty', 'conversation_id': -1}, {'message': 'ty', 'conversation_id': '\u00b2'}):
                result = views.chat_api(APIRequestFactory().post('/api/chat', payload, format='json'))
                self.assertEqual(result.status_code, 400, payload)
        value.process_query.assert_not_called()

    def test_infrastructure_and_unexpected_errors_are_safe_and_distinct(self):
        for exception, status, code in ((DatabaseError('PRIVATE connection SQL password'), 503, 'storage_unavailable'),
                                        (RuntimeError('PRIVATE API secret'), 500, 'request_failed')):
            value = Mock()
            value.process_query.side_effect = exception
            with patch.object(views, 'bot', value), self.assertLogs('paula.performance', level='INFO') as logs:
                result = views.chat_api(APIRequestFactory().post('/api/chat', {'message': 'ty'}, format='json'))
            self.assertEqual(result.status_code, status)
            self.assertEqual(result.data['error_code'], code)
            self.assertNotIn('PRIVATE', str(result.data))
            self.assertNotIn('PRIVATE', str(logs.output))

    def test_answer_status_is_exposed_without_changing_existing_response_fields(self):
        value = Mock()
        value.process_query.return_value = ConversationAnswer(('Safe temporary message.', [], None, None), status='unavailable')
        with patch.object(views, 'bot', value):
            result = views.chat_api(APIRequestFactory().post('/api/chat', {'message': 'Fixture query', 'mode': 'guest'}, format='json'))
        self.assertEqual(result.data['answer_status'], 'unavailable')
        self.assertFalse(result.data['saved'])
        self.assertIn('sources', result.data)
        self.assertIn('response', result.data)

    def test_navigation_rejects_invalid_coordinates_before_loading_pathfinder(self):
        for value in (None, True, 'NaN', 'Infinity', -1, 101, {}, []):
            payload = {'start_x': value, 'start_y': 10, 'end_x': 20, 'end_y': 20}
            with patch.object(views, 'get_pathfinder') as pathfinder:
                result = views.calculate_campus_route(APIRequestFactory().post('/api/navigation/route/', payload, format='json'))
            self.assertEqual(result.status_code, 400)
            pathfinder.assert_not_called()

    def test_navigation_component_failure_is_safe(self):
        payload = {'start_x': 10, 'start_y': 10, 'end_x': 20, 'end_y': 20}
        with patch.object(views, 'get_pathfinder', side_effect=RuntimeError('PRIVATE disk path')):
            result = views.calculate_campus_route(APIRequestFactory().post('/api/navigation/route/', payload, format='json'))
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.data['error_code'], 'navigation_unavailable')
        self.assertNotIn('PRIVATE', str(result.data))

    def test_model_rejection_is_not_misreported_as_missing_knowledge(self):
        value = PauliBotLogic.__new__(PauliBotLogic)
        value.rag = Mock()
        value.rag.search.return_value = [dict(question='Transcript request procedure', answer=f'Transcript request fixture {i}.', source_type='office') for i in range(2)]
        value._select = Mock(return_value=[])
        value.client = value.openai_client = value.gemini_model = None
        result = value.process_query('How to request a transcript?')
        self.assertEqual(result.answer_status, 'selection_rejected')
        self.assertIn('related information', result[0])
        self.assertFalse(result[1])


class KnowledgeHealthTests(TestCase):
    def test_empty_knowledge_does_not_advertise_usable_readiness(self):
        with patch('chatbot.health.readiness_state', return_value={'ready': True, 'workers': [], 'expected_workers': 1, 'ready_workers': 1}):
            state = service_readiness()
        self.assertTrue(state['database_ready'])
        self.assertFalse(state['ready'])

    def test_missing_vectors_are_visible_but_do_not_disable_exact_faqs(self):
        FAQ.objects.create(question='What is Nova?', answer='Fixture institution.', category='Fixture')
        with patch('chatbot.health.readiness_state', return_value={'ready': True}):
            state = service_readiness()
        self.assertTrue(state['ready'])
        self.assertFalse(state['index_complete'])
        self.assertTrue(RAGSearcher._exact_faq_lookup('What is Nova?'))

    def test_database_outage_makes_readiness_false_without_leaking_details(self):
        with patch('chatbot.health.FAQ.objects.aggregate', side_effect=DatabaseError('PRIVATE hostname')), self.assertLogs('paula.performance') as logs:
            state = knowledge_health()
        self.assertFalse(state['database_ready'])
        self.assertNotIn('PRIVATE', str(state) + str(logs.output))
