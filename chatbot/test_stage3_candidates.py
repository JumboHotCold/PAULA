from unittest.mock import patch,Mock
from django.test import TestCase,SimpleTestCase
from .logic import PauliBotLogic
from .models import FAQ
from .rag import RAGSearcher
from .spelling import prepare_vocabulary,matching_plan,build_lexicon
from .retrieval_types import RetrievalOutcome
from .spelling_evidence import resolve_candidates,candidate_questions
from types import SimpleNamespace


def bot(rag):
    value=PauliBotLogic.__new__(PauliBotLogic)
    value.rag=rag
    value.client=value.openai_client=value.gemini_model=None
    return value


class GroundedCandidateTests(TestCase):
    def setUp(self):
        self.catalog=FAQ.objects.create(question='What programs are offered at SPUS?',answer='Reviewed fixture program list.',category='Fixture')
        FAQ.objects.create(question='How do I register for an account?',answer='Reviewed fixture registration.',category='Fixture')
        snapshot=patch('chatbot.spelling._public_lexicon',None)
        snapshot.start();self.addCleanup(snapshot.stop)
        prepare_vocabulary()

    def test_inflected_spelling_candidates_resolve_to_same_grounded_question(self):
        rag=RAGSearcher()
        with patch.object(rag,'_hybrid_search',return_value=[]):
            result=bot(rag).process_query('wat r the programs offerd')
        self.assertEqual(result.answer_status,'ok')
        self.assertIn(self.catalog.answer,result[0])

    def test_location_evidence_disambiguates_nearby_ordinary_word(self):
        rag=RAGSearcher()
        with patch.object(rag,'_hybrid_search',return_value=[]):
            result=bot(rag).process_query('where is the registrr')
        self.assertEqual(result[2],'navigate_map')
        self.assertEqual(result[3]['destination'],'registrar_office')

    def test_disagreeing_grounded_candidates_still_require_confirmation(self):
        lexicon=build_lexicon(['dean mean'])
        with patch('chatbot.spelling._public_lexicon',lexicon):
            plan=matching_plan('What is fean?')
            self.assertTrue(plan.ambiguous)
            rag=SimpleNamespace(retrieve=lambda query,limit:RetrievalOutcome([
                dict(question=query,answer='Reviewed '+query,record_type='faq',record_id=query)],'ok'))
            self.assertEqual(resolve_candidates(plan,rag).status,'clarification')


class CandidateSafetyTests(SimpleTestCase):
    def test_same_evidence_consensus_and_failure_boundaries(self):
        with patch('chatbot.spelling._public_lexicon',build_lexicon(['dean mean'])):
            plan=matching_plan('Explain fean')
            row=dict(question='Explain dean and mean',answer='Reviewed explanation of dean and mean',record_type='faq',record_id=1)
            for status,expected in (('ok','resolved'),('unavailable','unavailable'),('conflict','conflict'),('no_match','clarification')):
                rag=SimpleNamespace(retrieve=lambda query,limit:RetrievalOutcome([row] if status=='ok' else [],status))
                self.assertEqual(resolve_candidates(plan,rag).status,expected)

    def test_candidate_budget_and_protected_names(self):
        with patch('chatbot.spelling._public_lexicon',build_lexicon(['dean mean'],names=['Alice Santos'])):
            plan=matching_plan('Who is Alice Santoz?')
            rag=Mock()
            self.assertNotEqual(resolve_candidates(plan,rag).status,'resolved')
            rag.retrieve.assert_not_called()
            from dataclasses import replace
            plan=replace(plan,ambiguous=('unknown',),protected_name=False)
            with patch('chatbot.spelling_evidence.nearest',return_value=(1,tuple('choice'+str(i) for i in range(7)))):
                self.assertEqual(candidate_questions(plan),())

