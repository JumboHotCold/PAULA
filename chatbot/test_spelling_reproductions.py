"""Log #7 red-first reproductions; submitted strings belong in tests only."""
from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from .dialogue import route_turn
from .grounding import eligible_evidence
from .logic import PauliBotLogic


class LogSevenReproductions(SimpleTestCase):
    def setUp(self):
        from .spelling import build_lexicon
        lexicon = build_lexicon(['What programs are offered at SPUS?'])
        self.snapshot = patch('chatbot.spelling._public_lexicon', lexicon)
        self.snapshot.start()
        self.addCleanup(self.snapshot.stop)

    def test_identity_transposition_without_wrapper(self):
        self.assertEqual(route_turn('tell me abuot yourself', semantic=False).kind, 'identity')

    def test_four_short_phrases_individually(self):
        for text, kind in (('who r u', 'identity'), ('wat can u do', 'capabilities'),
                           ('thnx', 'thanks'), ('thankyouuu', 'thanks')):
            with self.subTest(text=text):
                self.assertEqual(route_turn(text, semantic=False).kind, kind)

    def test_all_four_phrases_in_one_message(self):
        bot = PauliBotLogic.__new__(PauliBotLogic)
        bot.rag = Mock()
        bot.client = Mock()
        bot.openai_client = bot.gemini_model = None
        result = bot.process_query('who r u, wat can u do, thnx, thankyouuu')
        self.assertEqual(result.answer_status, 'social')
        self.assertIn("I'm PAULA", result[0])
        self.assertIn('help', result[0].lower())
        self.assertIn('welcome', result[0].lower())
        self.assertLess(len(result[0].split()),80)
        bot.rag.search.assert_not_called()
        bot.client.chat.completions.create.assert_not_called()

    def test_greeting_tail_corrected_before_retrieval_and_grounding(self):
        route = route_turn('hi, what are the programs ofered', semantic=False)
        self.assertEqual(route.kind, 'knowledge')
        self.assertIn('offered', route.query)
        evidence = dict(question='What programs are offered at SPUS?',
                        answer='SPUS offers its reviewed undergraduate programs.', record_type='faq')
        self.assertTrue(eligible_evidence(route.query, evidence))
