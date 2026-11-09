from unittest.mock import patch
from django.test import TestCase
from .models import StaffMember,WebResource
from .rag import RAGSearcher
from .spelling import build_lexicon


class ExactLocalIdentityTests(TestCase):
    def setUp(self):
        self.local=StaffMember.objects.create(name='Dr. Alice Santos',position='Dean',office='Fixture Office')
        WebResource.objects.create(category='Website personnel',url='https://spus.edu.ph/administrator/',
            title='SPUS Personnel | ACADEMIC SERVICES | Dean | Dr. Alice R. Santos',
            content='Section: ACADEMIC SERVICES\nName: Dr. Alice R. Santos\nRole: Dean')

    def test_format_ambiguous_website_does_not_hide_exact_local_record(self):
        rag=RAGSearcher()
        with patch.object(rag,'_hybrid_search',side_effect=AssertionError('No name inference')):
            outcome=rag.retrieve('Who is Dr. Alice Santos?')
        self.assertEqual(outcome.status,'ok')
        self.assertEqual(outcome.evidence[0]['personnel_name'],self.local.name)
        self.assertTrue(outcome.evidence[0]['review_notes'])
        self.assertIn('local staff record',outcome.evidence[0]['answer'])

    def test_unknown_near_name_still_cannot_choose_another_person(self):
        outcome=RAGSearcher().retrieve('Who is Dr. Alice Sants?')
        self.assertFalse(outcome.evidence)
