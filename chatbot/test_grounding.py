"""Offline regression suite: no database creation, downloads, or provider calls.

Run inside the configured web container:
    python -B -m unittest chatbot.test_grounding -v
Names in fixtures are fictional test data, never institutional knowledge.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from .grounding import eligible_evidence, rank_evidence, render_evidence, selected_evidence
from .logic import PauliBotLogic


def entry(question, answer, **kwargs):
    return dict(question=question, answer=answer, text=answer,
                document_title=question, source_type='office',
                source_office=kwargs.pop('source_office', None),
                distance=kwargs.pop('distance', 0.2), **kwargs)


CALENDAR = entry('What is the school calendar?', 'First semester: August to December. Final examinations follow.')
CEIT = entry('Who are the CEIT faculty?', 'Dr. Alice Example is a CEIT instructor.', source_office='CEIT')
CHS = entry('Who are the CHS faculty?', 'Dr. Bob Example is a CHS professor.', source_office='CHS')


class EvidenceTests(unittest.TestCase):
    def test_reported_calendar_mismatch_is_rejected_even_at_high_similarity(self):
        self.assertEqual(rank_evidence('who are the CEIT faculty lineup', [dict(CALENDAR, distance=0.01)]), [])

    def test_office_authority_cannot_rescue_a_weak_match(self):
        self.assertEqual(rank_evidence('Who are CEIT faculty?', [dict(CEIT, distance=0.9)]), [])

    def test_wrong_college_and_program_catalog_are_rejected(self):
        catalog = entry('CEIT academic programs', 'CEIT faculty deliver BS Civil Engineering and BS Information Technology.')
        self.assertFalse(eligible_evidence('Who are CEIT faculty?', CHS))
        self.assertFalse(eligible_evidence('Who are CEIT faculty?', catalog))

    def test_department_alias_and_filipino_query(self):
        self.assertTrue(eligible_evidence('Sino ang mga guro sa CEIT?', CEIT))
        self.assertTrue(eligible_evidence('Who are the College of Engineering & Information Technology faculty?', CEIT))

    def test_dean_alone_is_not_a_faculty_roster(self):
        dean = entry('Who is the CEIT dean?', 'Dr. Alice Example is the CEIT dean.')
        self.assertFalse(eligible_evidence('Who are the CEIT faculty?', dean))
        dean_in_faculty_room = entry('Who is the CEIT dean?',
            'Dr. Alice Example is the CEIT dean. Office located at CEIT Faculty Room.',
            source_office='CEIT Faculty Room')
        self.assertFalse(eligible_evidence('Who are the CEIT faculty?', dean_in_faculty_room))

    def test_incidental_scholarship_mention_is_not_a_program_answer(self):
        scholarship = entry('Does SPUS offer scholarships?',
            'SPUS offers academic scholarships for undergraduate programs.')
        self.assertFalse(eligible_evidence('What programs are offered at SPUS?', scholarship))

    def test_wrong_enrollment_level_or_documents_are_not_procedure(self):
        junior = entry('How to enroll in Grade 7?', 'Incoming freshmen enroll with a report card.')
        documents = entry('What documents do incoming freshmen need for enrollment?', 'Incoming freshmen submit a report card.')
        self.assertFalse(eligible_evidence('How do incoming freshmen enroll?', junior))
        self.assertFalse(eligible_evidence('How do incoming freshmen enroll?', documents))

    def test_mixed_college_chunk_is_not_misattributed(self):
        mixed = entry('Faculty directory', CEIT['answer'] + '\n' + CHS['answer'])
        self.assertFalse(eligible_evidence('Who are the CEIT faculty?', mixed))

    def test_exact_year_and_role_must_be_supported(self):
        self.assertFalse(eligible_evidence('What is the 2027 school calendar?', CALENDAR))
        self.assertFalse(eligible_evidence('Who is the CEIT president?', CEIT))

    def test_unknown_acronym_and_role_qualifier_are_not_dropped(self):
        scholarship = entry('Does SPUS offer scholarships?', 'SPUS offers academic scholarships.')
        vp = entry('Who is the VP for Finance?', 'Dr. Alice Example is the VP for Finance.')
        self.assertFalse(eligible_evidence('Does SPUS offer DOST scholarships?', scholarship))
        self.assertFalse(eligible_evidence('Who is the VP academic?', vp))

    def test_invalid_scores_fail_closed(self):
        for value in (None, float('nan'), float('inf'), -2, '0.1'):
            with self.subTest(value=value):
                self.assertEqual(rank_evidence('Who are CEIT faculty?', [dict(CEIT, distance=value)]), [])

    def test_relevant_answer_is_kept_and_deduplicated(self):
        self.assertEqual(len(rank_evidence('Who are CEIT faculty?', [CEIT, dict(CEIT)])), 1)

    def test_model_must_return_only_valid_evidence_ids(self):
        for payload in ('invented answer', '{"evidence_ids":[9]}', '{"evidence_ids":[true]}',
                        '{"evidence_ids":[1],"answer":"invented faculty"}', '[]',
                        '{"evidence_ids":"1"}'):
            with self.subTest(payload=payload):
                self.assertIsNone(selected_evidence(payload, 2))
        self.assertEqual(selected_evidence('{"evidence_ids": [2, 1]}', 2), [2, 1])
        self.assertEqual(selected_evidence('{"evidence_ids": []}', 2), [])

    def test_only_displayed_evidence_is_cited_and_body_is_verbatim(self):
        text, sources = render_evidence([CEIT])
        self.assertEqual(text, CEIT['answer'])
        self.assertEqual([source['title'] for source in sources], [CEIT['document_title']])


class ResponseTests(unittest.TestCase):
    def bot(self, results):
        bot = PauliBotLogic.__new__(PauliBotLogic)
        bot.rag = Mock()
        bot.rag.search.return_value = results
        bot.client = bot.openai_client = bot.gemini_model = None
        bot.model_name = 'test-model'
        return bot

    def test_no_evidence_never_calls_provider(self):
        bot = self.bot([CALENDAR])
        bot.client = Mock()
        text, sources, action, _ = bot.process_query('who are the CEIT faculty lineup')
        self.assertIn("don't have enough verified information", text)
        self.assertNotIn('First semester', text)
        self.assertEqual(sources, [])
        self.assertIsNone(action)
        bot.client.chat.completions.create.assert_not_called()
        bot.rag.search.assert_called_once()

    def test_faculty_response_is_extract_not_invented_roster(self):
        bot = self.bot([CEIT])
        text, sources, _, _ = bot.process_query('Who are the CEIT faculty?')
        self.assertIn(CEIT['answer'], text)
        self.assertIn('may not be the complete or current lineup', text)
        self.assertEqual(len(sources), 1)

    def test_provider_outages_reuse_evidence_without_second_retrieval(self):
        one = entry('How to request a transcript?', 'To request a transcript, obtain a request form.')
        two = entry('Transcript request procedure', 'A transcript request requires payment at the cashier.')
        bot = self.bot([one, two])
        bot.client = Mock()
        bot.client.chat.completions.create.side_effect = TimeoutError
        text, sources, _, _ = bot.process_query('How to request a transcript?')
        self.assertIn(one['answer'], text)
        self.assertEqual(len(sources), 1)
        bot.rag.search.assert_called_once()

    def test_generated_claims_cannot_reach_response(self):
        one = entry('How to request a transcript?', 'To request a transcript, obtain a request form.')
        two = entry('Transcript request procedure', 'A transcript request requires payment at the cashier.')
        bot = self.bot([one, two])
        bot.client = Mock()
        bot.client.chat.completions.create.return_value = SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(content='{"evidence_ids":[1],"answer":"Pay 99999 pesos"}'))])
        text, _, _, _ = bot.process_query('How to request a transcript?')
        self.assertNotIn('99999', text)
        self.assertIn(one['answer'], text)

    def test_openai_fallback_selects_and_cites_only_existing_evidence(self):
        one = entry('How to request a transcript?', 'To request a transcript, obtain a request form.')
        two = entry('Transcript request procedure', 'A transcript request requires payment at the cashier.')
        bot = self.bot([one, two])
        bot.client = Mock()
        bot.client.chat.completions.create.side_effect = TimeoutError
        bot.openai_client = Mock()
        bot.openai_client.chat.completions.create.return_value = SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(content='{"evidence_ids":[2]}'))])
        text, sources, _, _ = bot.process_query('How to request a transcript?')
        self.assertIn(two['answer'], text)
        self.assertNotIn(one['answer'], text)
        self.assertEqual([source['title'] for source in sources], [two['document_title']])
        bot.rag.search.assert_called_once()

    def test_gemini_fallback_cannot_add_generated_facts(self):
        bot = self.bot([CEIT])
        bot.gemini_model = Mock()
        bot.gemini_model.generate_content.return_value = SimpleNamespace(text='{"evidence_ids":[1]}')
        self.assertEqual(bot._select('Who teaches?', [CEIT]), [CEIT])

    def test_one_supported_answer_needs_no_provider(self):
        bot = self.bot([CALENDAR])
        bot.client = Mock()
        text, _, _, _ = bot.process_query('What is the school calendar?')
        self.assertIn(CALENDAR['answer'], text)
        bot.client.chat.completions.create.assert_not_called()

    def test_explicit_model_abstention_is_respected(self):
        bot = self.bot([CEIT, dict(CEIT, answer='Dr. Carol Example is a CEIT lecturer.')])
        bot.client = Mock()
        bot.client.chat.completions.create.return_value = SimpleNamespace(choices=[
            SimpleNamespace(message=SimpleNamespace(content='{"evidence_ids":[]}'))])
        self.assertEqual(bot._select('Who teaches?', [CEIT]), [])

    def test_retrieval_outage_is_not_reported_as_missing_knowledge(self):
        bot = self.bot([])
        bot.rag.search.side_effect = RuntimeError('sensitive connection details')
        text, sources, _, _ = bot.process_query('Who are CEIT faculty?')
        self.assertIn('cannot access', text)
        self.assertNotIn('sensitive', text)
        self.assertEqual(sources, [])

    def test_old_calendar_history_cannot_override_current_faculty_question(self):
        bot = self.bot([])
        text, _, _, _ = bot.process_query('Who are CEIT faculty?', history=[
            {'role': 'assistant', 'content': CALENDAR['answer']}])
        self.assertNotIn('First semester', text)

    def test_greeting_does_not_retrieve(self):
        bot = self.bot([])
        self.assertIn('PAULA', bot.process_query('Hello!')[0])
        bot.rag.search.assert_not_called()


if __name__ == '__main__':
    unittest.main()
