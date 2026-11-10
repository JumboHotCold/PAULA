"""Explicit red-first Log #9 audit; promoted after its separate fixes land."""
from unittest.mock import patch
from django.test import SimpleTestCase
from .dialogue import route_turn
from .spelling import build_lexicon, matching_plan


class RetestDevelopmentCases(SimpleTestCase):
    def setUp(self):
        snapshot=patch('chatbot.spelling._public_lexicon',build_lexicon(
            ['What programs are offered at SPUS?','register offer offers offered'],names=['Ted Sample','Abt Example']))
        snapshot.start()
        self.addCleanup(snapshot.stop)

    def test_shorthand_intro_is_not_a_person_lookup(self):
        self.assertEqual(route_turn('tel me abt urself',semantic=False).kind,'identity')

    def test_gratitude_modifiers_and_shorthand(self):
        for text in ('thank u po','salamat gyud','salamat kaayo','maraming salamat po','daghang salamat','thanks a lot'):
            with self.subTest(text=text):self.assertEqual(route_turn(text,semantic=False).kind,'thanks')

    def test_person_guard_does_not_intercept_nonlookup_questions(self):
        for text in ('Please tell me about Ted policy','Where is the tedd office?','What are the abt programs?'):
            with self.subTest(text=text):self.assertFalse(matching_plan(text).protected_name)
