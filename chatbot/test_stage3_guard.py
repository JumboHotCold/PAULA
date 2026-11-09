from unittest.mock import patch
from django.test import SimpleTestCase
from .spelling import build_lexicon,matching_plan


class PersonGuardScopeTests(SimpleTestCase):
    def test_guard_requires_person_lookup(self):
        lexicon=build_lexicon(names=['Ted Sample','Del Santos'])
        for text in ('tel me abt urself','Where is the tedd office?','What is the tedd policy?','I feel tedd today'):
            self.assertFalse(matching_plan(text,lexicon).protected_name,text)
        for text in ('Who is Tedd Sample?','Contact of Tedd Sample','Email of Tedd Sample','Sino si Tedd Sample?',
                     'Head of Tedd Sample','Tell me about Tedd Sample'):
            self.assertTrue(matching_plan(text,lexicon).protected_name,text)

