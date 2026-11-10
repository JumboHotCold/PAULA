"""Full reference spans, antecedent ambiguity and preserved constraints."""
from django.test import SimpleTestCase
from .conversation_context import resolve_turn
from .query_normalization import faq_question_key


class ReferringNounPhraseTests(SimpleTestCase):
    def test_all_institution_nouns_bind_the_complete_reference(self):
        for noun in ('institution', 'school', 'university', 'campus'):
            with self.subTest(noun=noun):
                result = resolve_turn(f'tell me about SPUS and why should i enroll in this {noun}')
                self.assertEqual(len(result.queries), 2)
                self.assertEqual(faq_question_key(result.queries[1]), faq_question_key('Why should I enroll at SPUS?'))

    def test_reference_binding_supports_other_predicates_and_future_named_subjects(self):
        for name in ('SPUS', 'Orion University'):
            for noun in ('institution', 'school', 'university', 'campus'):
                with self.subTest(name=name, noun=noun):
                    result = resolve_turn(f'What services does this {noun} provide?', f'Tell me about {name}')
                    self.assertEqual(result.queries, (f'What services does {name} provide?',))

    def test_constraints_are_not_discarded(self):
        query = 'What are the requirements at this institution in 2037 without transfer credentials?'
        result = resolve_turn(query, 'Tell me about SPUS')
        self.assertEqual(result.queries, ('What are the requirements at SPUS in 2037 without transfer credentials?',))

    def test_missing_ambiguous_and_incompatible_antecedents_clarify(self):
        for previous in ('', 'Tell me about SPUS and Orion University', 'Tell me about the Registrar office'):
            with self.subTest(previous=previous):
                result = resolve_turn('What services does this institution provide?', previous)
                self.assertTrue(result.clarification)

    def test_explicit_new_institution_does_not_inherit_the_previous_one(self):
        query = 'Why should I enroll at Orion University?'
        self.assertEqual(resolve_turn(query, 'Tell me about SPUS').queries, (query,))
