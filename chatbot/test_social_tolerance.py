"""Bounded social spelling repair, no factual interception or identity changes."""
import unittest
from unittest.mock import Mock, patch
from rest_framework.test import APIRequestFactory
from .dialogue import route_turn
from .intents import ENROLL_QUESTION
from .logic import PauliBotLogic
from .social_normalization import match_social

THANKS = ('ty', 'TY!!', 'thx', 'tnx', 'tq', 'tysm', 'TYSM PAULA!!', 'thankyoui', 'thnak you',
          'thnks', 'thankss', 'thankyou', 'thank   you', 'thanks!!!', 'THANK YOU', 'ThAnK YoU',
          'ＴＹ！！', 'salamat', 'salamat kaayo', 'daghang salamat', 'daghang salamat kaayo')


def bot():
    value = PauliBotLogic.__new__(PauliBotLogic)
    value.rag = Mock()
    value.client = Mock()
    value.openai_client = value.gemini_model = None
    value.model_name = 'test'
    return value


class SocialToleranceTests(unittest.TestCase):
    def test_attached_gratitude_variants_are_local_before_semantic_routing(self):
        with patch('chatbot.dialogue.social_router.classify', side_effect=AssertionError('No embedding allowed')):
            for text in THANKS:
                self.assertEqual(route_turn(text).kind, 'thanks', text)

    def test_joined_greetings_and_wellbeing_use_known_phrase_boundaries(self):
        with patch('chatbot.dialogue.social_router.classify', side_effect=AssertionError('No embedding allowed')):
            for text, expected in (('goodmorning', 'greeting'), ('goodafternoon', 'greeting'),
                                   ('howareyou', 'wellbeing'), ('goodbye', 'farewell')):
                self.assertEqual(route_turn(text).kind, expected)

    def test_fuzzy_matching_is_bounded_and_rejects_valid_lookalikes(self):
        for text in ('tanks', 'thinks', 'thunks', 'shanks', 'think', 'salami', 'salary',
                     'typhoon', 'ty123', 'TY-2027', 'https://ty.example', 'thank you i', 'tqq', 'ty office'):
            self.assertIsNone(match_social(text), text)
        self.assertIsNone(match_social('th' * 100))

    def test_semantic_classifier_cannot_override_unknown_single_word_names(self):
        with patch('chatbot.dialogue.social_router.classify', return_value=('thanks', .99)) as semantic:
            for text in ('tanks', 'thinks', 'shanks', 'Nova', 'typhoon'):
                self.assertEqual(route_turn(text).kind, 'knowledge', text)
            semantic.assert_not_called()

    def test_meaningful_institutional_queries_stay_knowledge(self):
        cases = ('Who handles thank you cards without fees in 2037?', 'What is the TY scholarship?',
                 'Thankyoui college faculty lineup', 'No tuition fee is required, right?',
                 'Yes, what documents do transferees need?', 'Dili, how do I enroll?',
                 'Help me locate the Registrar office', 'Explain the library policy',
                 'Who is Thnks Santos?', 'Thx, who is the ICT Director?',
                 'What programs are offered? TY!!')
        with patch('chatbot.dialogue.social_router.classify', return_value=('thanks', .99)):
            for text in cases:
                self.assertEqual(route_turn(text).kind, 'knowledge', text)

    def test_social_edges_preserve_factual_query_constraints(self):
        route = route_turn('TY!! What is the fee for 2037 without a scholarship?')
        self.assertEqual(route.query, 'What is the fee for 2037 without a scholarship?')
        self.assertEqual(route.acknowledgement, 'thanks')
        route = route_turn('What is the fee for 2037 without a scholarship? Thankyoui!')
        self.assertEqual(route.query, 'What is the fee for 2037 without a scholarship')

    def test_fast_social_responses_never_retrieve_or_call_external_provider(self):
        value = bot()
        with patch('chatbot.dialogue.social_router.classify', side_effect=AssertionError('No embedding allowed')):
            for text in THANKS + ('yes', 'no', 'okay', 'sure', 'dili', 'help', 'explain'):
                response = value.process_query(text)
                self.assertFalse(response[1])
                self.assertIsNone(response[2])
                self.assertNotIn('rephrase', response[0].casefold())
        value.rag.search.assert_not_called()
        value.client.chat.completions.create.assert_not_called()

    def test_cebuano_gratitude_uses_reviewed_reply_without_global_language_state(self):
        value = bot()
        self.assertIn('Walay sapayan', value.process_query('salamat kaayo')[0])
        self.assertIn('Walay sapayan', value.process_query('daghang salamat')[0])
        self.assertIn("You're welcome", value.process_query('ty')[0])
        self.assertIn("You're welcome", value.process_query('salamat kaayo', dialogue_state={'language': 'en'})[0])

    def test_reply_variation_is_bounded_to_the_current_conversation(self):
        value = bot()
        first = value.process_query('ty')[0]
        history = [dict(role='user', content='ty'), dict(role='assistant', content=first)]
        self.assertNotEqual(value.process_query('ty', history=history)[0], first)
        self.assertEqual(value.process_query('ty')[0], first)

    def test_short_yes_no_do_not_choose_student_category_or_authorize_action(self):
        value = bot()
        initial = value.process_query('How do I enroll?')
        for text in ('yes', 'no', 'sure', 'okay', 'dili'):
            result = value.process_query(text, context_query=initial.context_query,
                dialogue_state={'pending': initial.pending_clarification})
            self.assertIn(ENROLL_QUESTION, result[0])
            self.assertEqual(result.pending_clarification, initial.pending_clarification)
            self.assertEqual(result.context_query, initial.context_query)
            self.assertIsNone(result[2])
        value.rag.search.assert_not_called()

    def test_clarification_references_previous_answer_without_inventing_facts(self):
        value = bot()
        result = value.process_query('what do you mean?', context_query='Who is the ICT Director?')
        self.assertIn('previous answer', result[0])
        self.assertEqual(result.context_query, 'Who is the ICT Director?')
        value.rag.search.assert_not_called()

    def test_variants_do_not_replace_prior_factual_context(self):
        from .conversation_context import conversation_anchor
        history = [dict(role='user', content='Who are CEIT faculty?'), dict(role='assistant', content='Stored response.')]
        for text in ('ty', 'thankyoui', 'yes', 'no', 'salamat kaayo'):
            self.assertEqual(conversation_anchor(history + [dict(role='user', content=text), dict(role='assistant', content='Social reply.')]), 'Who are CEIT faculty?')

    def test_guest_api_social_turns_remain_unsaved(self):
        from . import views
        with patch.object(views, 'bot', bot()), patch.object(views.ChatHistory.objects, 'create') as save:
            response = views.chat_api(APIRequestFactory().post('/api/chat', {'message': 'ty', 'mode': 'guest'}, format='json'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['response_mode'], 'thanks')
        self.assertFalse(response.data['saved'])
        save.assert_not_called()
