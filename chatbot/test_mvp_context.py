"""Shared attribute grammar applies to future domains as well as enrollment."""
from django.test import SimpleTestCase
from .conversation_context import resolve_turn


class AttributeGrammarTests(SimpleTestCase):
    def test_filipino_and_english_use_the_same_subject_binding(self):
        for subject in ('Orion scholarship', 'Nova program', 'Vega policy', 'transferee college students'):
            prior = f'What is the procedure for {subject}?'
            for phrase in ('What about requirements?', 'Ano ang requirements?', 'Ano naman ang requirements?', 'Paano naman ang requirements?'):
                with self.subTest(subject=subject, phrase=phrase):
                    result = resolve_turn(phrase, prior)
                    self.assertEqual(result.relation, 'attribute')
                    self.assertEqual(result.queries, (f'What are requirements for {subject}?',))

    def test_attribute_does_not_remove_user_constraints_or_invent_a_topic(self):
        self.assertTrue(resolve_turn('Ano naman ang requirements?').clarification)
        result = resolve_turn('Ano naman ang requirements without credentials in 2037?', 'What is the procedure for Orion scholarship?')
        self.assertIn('without credentials in 2037', result.queries[0])
        self.assertIn('Orion scholarship', result.queries[0])
        switched = resolve_turn('Ano ang requirements for Nova program?', 'What is the procedure for Orion scholarship?')
        self.assertEqual(switched.relation, 'standalone')
        self.assertNotIn('Orion', switched.queries[0])
