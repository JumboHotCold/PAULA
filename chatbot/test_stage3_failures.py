from types import SimpleNamespace
from unittest.mock import Mock,patch
from django.test import SimpleTestCase
from django.db import DatabaseError
from .logic import PauliBotLogic
from .rag import RAGSearcher
from .retrieval_types import RetrievalOutcome


class Fake429(Exception):
    status_code=429
    response=SimpleNamespace(headers={'retry-after':'2'})
    body={}


class PipelineFailureTests(SimpleTestCase):
    def bot(self):
        value=PauliBotLogic.__new__(PauliBotLogic)
        value.rag=RAGSearcher();value.client=Mock();value.openai_client=value.gemini_model=None;value.model_name='fixture'
        return value

    def test_provider_429_timeout_and_invalid_output_preserve_only_stored_answer(self):
        rows=[dict(question='What is the library policy?',answer='Reviewed library fixture.',record_type='faq',record_id=1),
              dict(question='What are the library policies?',answer='Reviewed alternate library fixture.',record_type='faq',record_id=2)]
        for failure in (Fake429(),TimeoutError()):
            value=self.bot();value.client.chat.completions.create.side_effect=failure
            with patch.object(value,'_retrieve',return_value=RetrievalOutcome(rows,'ok')):
                result=value.process_query('What is the library policy?')
            self.assertIn('Reviewed library fixture.',result[0]);self.assertTrue(result[1])
        value=self.bot()
        value.client.chat.completions.create.return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"fabricated":"unverified institution fact"}'))])
        with patch.object(value,'_retrieve',return_value=RetrievalOutcome(rows,'ok')):
            result=value.process_query('What is the library policy?')
        self.assertNotIn('unverified institution fact',result[0]);self.assertTrue(result[1])

    def test_empty_retrieval_and_db_error_have_distinct_safe_outcomes(self):
        for outcome,error,expected in (([],None,'no_match'),(None,DatabaseError('PRIVATE SQL'),'unavailable')):
            value=self.bot()
            with patch.object(value.rag,'search',return_value=outcome,side_effect=error):result=value.process_query('What is the library policy?')
            self.assertEqual(result.answer_status,expected);self.assertFalse(result[1]);self.assertNotIn('PRIVATE',result[0])
