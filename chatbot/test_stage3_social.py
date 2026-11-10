from unittest.mock import patch
from django.test import SimpleTestCase
from .dialogue import route_turn
from .chat_language import social_core,expand_shorthand
from .spelling import matching_plan,build_lexicon


class ConfiguredChatLanguageTests(SimpleTestCase):
    def test_manual_development_social_cases(self):
        lexicon=build_lexicon(names=['Del Santos'])
        with patch('chatbot.spelling._public_lexicon',lexicon):
            self.assertEqual(route_turn('tel me abt urself',semantic=False).kind,'identity')
            for text in ('thank u po','salamat gyud','salamat kaayo','maraming salamat po','daghang salamat','thanks a lot'):
                self.assertEqual(route_turn(text,semantic=False).kind,'thanks',text)
            self.assertEqual(route_turn('salamat gyud',semantic=False).reply_language,'ceb')

    def test_modifiers_do_not_discard_institutional_clauses(self):
        for text in ('salamat gyud what is the tuition fee','thank u po who is the dean','po registrar office',
                     'Who is Ur Santos?','where r the offices','please list scholarship requirements naman'):
            self.assertEqual(route_turn(text,semantic=False).kind,'knowledge',text)
        self.assertEqual(expand_shorthand('Who is ur Santos?',person_lookup=True),'Who is ur Santos?')
        for text in ('po','gyud','naman lang'):
            self.assertEqual(social_core(text)[0],'')
