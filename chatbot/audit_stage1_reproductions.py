"""Explicit Stage 1 red tests; no application behavior changes.

Run: docker exec paulibot_web python -B manage.py test
     chatbot.audit_stage1_reproductions --keepdb
This audit module is intentionally separate from default test discovery while
Stage 2 awaits authorization. Its failing assertions are reported, not skipped.
"""
from django.test import SimpleTestCase
from .dialogue import route_turn
from .conversation_context import resolve_turn
from .query_normalization import faq_question_key


class HistoricalSocialCases(SimpleTestCase):
    def test_gratitude_variants_are_currently_recognized_without_semantics(self):
        for query in ('ty', 'thankyoui', 'thank you', 'THANK YOU', 'ThAnK YoU', 'thx',
                      'tnx', 'tq', 'tysm', 'thnak you', 'thankss', 'thankyou',
                      'thank   you', 'thanks!!!', 'salamat kaayo', 'daghang salamat'):
            with self.subTest(query=query):
                self.assertEqual(route_turn(query, semantic=False).kind, 'thanks')

    def test_standalone_identity_is_currently_recognized(self):
        self.assertEqual(route_turn('hi', semantic=False).kind, 'greeting')
        self.assertEqual(route_turn('tell me about yourself', semantic=False).kind, 'identity')

    def test_social_keywords_do_not_intercept_institutional_questions(self):
        for query in ('ty, who is the ICT Director?', 'What programs are offered? TY!!',
                      'What is the TY scholarship?', 'Who is the university preseidnt?'):
            with self.subTest(query=query):
                self.assertEqual(route_turn(query, semantic=False).kind, 'knowledge')


class CurrentFailureReproductions(SimpleTestCase):
    def test_greeting_plus_identity_without_final_punctuation(self):
        self.assertEqual(route_turn('hi, tell me about yourself', semantic=False).kind, 'identity')

    def test_greeting_plus_identity_with_final_punctuation(self):
        self.assertEqual(route_turn('hi, tell me about yourself?', semantic=False).kind, 'identity')

    def test_institution_reference_does_not_leave_a_residual_noun(self):
        result = resolve_turn('tell me about SPUS and why should i enroll in this institution')
        self.assertEqual(len(result.queries), 2)
        # The complete referring noun phrase denotes SPUS, not "SPUS institution".
        self.assertNotIn('spus institution', result.queries[1].casefold())

    def test_implicit_and_explicit_institution_have_equivalent_retrieval_intent(self):
        implicit = resolve_turn('tell me about SPUS and why should i enroll in this institution')
        explicit = resolve_turn('tell me about SPUS and why should i enroll at SPUS')
        self.assertEqual(faq_question_key(implicit.queries[1]), faq_question_key(explicit.queries[1]))
