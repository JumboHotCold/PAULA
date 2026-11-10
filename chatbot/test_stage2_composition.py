"""Composition regressions: wrappers must not turn local self-help into RAG."""
from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from .dialogue import route_turn
from .logic import PauliBotLogic


class SocialCompositionTests(SimpleTestCase):
    def test_identity_and_capability_wrappers_use_existing_local_intents(self):
        for wrapper in ('hi, ', 'Hello! ', 'Kumusta; ', 'hi and '):
            for request, intent in (('tell me about yourself', 'identity'),
                                    ('tell me about yourself?', 'identity'),
                                    ('what can you do?', 'capabilities'), ('help', 'capabilities')):
                with self.subTest(wrapper=wrapper, request=request), patch('chatbot.dialogue.social_router.classify', side_effect=AssertionError('Local route needs no encoder')):
                    self.assertEqual(route_turn(wrapper + request).kind, intent)

    def test_composed_replies_do_not_retrieve_or_call_a_provider(self):
        bot = PauliBotLogic.__new__(PauliBotLogic)
        bot.rag = Mock()
        bot.client = Mock()
        bot.openai_client = bot.gemini_model = None
        for query, intent in (('hi, tell me about yourself', 'identity'), ('hi, what can you do?', 'capabilities')):
            with self.subTest(query=query):
                result = bot.process_query(query)
                self.assertEqual(result.response_mode, intent)
                self.assertFalse(result[1])
                self.assertTrue(result[0].startswith('Hi!'))
        bot.rag.search.assert_not_called()
        bot.client.chat.completions.create.assert_not_called()

    def test_extra_institutional_clauses_are_not_discarded_as_self_help(self):
        for query in ('hi, tell me about SPUS', 'hi, tell me about yourself and the ICT director',
                      'hi, what can you do about enrollment without credentials in 2037?',
                      'hi, help with the scholarship application', 'hi, what is your office policy?'):
            with self.subTest(query=query):
                route = route_turn(query, semantic=False)
                self.assertEqual(route.kind, 'knowledge')
                self.assertEqual(route.query, query.split(', ', 1)[1])
