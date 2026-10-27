"""Multi-part contracts use fictional evidence and no external providers."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from .compound_queries import MAX_PARTS, decompose_query
from .context_tokens import decode_context, encode_context
from .conversation_context import Entity, Vocabulary, builtin_vocabulary, resolve_conversation, resolve_turn
from .logic import PauliBotLogic
from .intents import normalize_query
from .retrieval_types import RetrievalOutcome


def pair(query, answer='Source evidence was displayed.'):
    return [{'role': 'user', 'content': query}, {'role': 'assistant', 'content': answer}]


def evidence(query, answer, **extra):
    return dict(question=query, document_title=query, answer=answer,
                source_type='office', source_office='Responsible office', **extra)


def bot_for(lookup):
    bot = PauliBotLogic.__new__(PauliBotLogic)
    bot.client = bot.openai_client = bot.gemini_model = None
    bot.model_name = 'fixture-model'
    bot.rag = SimpleNamespace(search=Mock(side_effect=lambda query, limit: lookup(query)))
    return bot


class CompoundParserTests(unittest.TestCase):
    def test_independent_role_phrases(self):
        self.assertEqual(resolve_turn('Who is the ICT Director and CEIT Dean?').queries,
                         ('Who is the ICT Director?', 'Who is the CEIT Dean?'))

    def test_shared_role_and_audience_slots(self):
        self.assertEqual(resolve_turn('Who are the deans of CEIT and CHS?').queries,
                         ('Who are the deans of CEIT?', 'Who are the deans of CHS?'))
        self.assertEqual(resolve_turn('What are the requirements for freshmen and transferees?').queries,
                         ('What are the requirements for freshmen?', 'What are the requirements for transferees?'))

    def test_office_suffix_belongs_to_each_destination(self):
        self.assertEqual(resolve_turn('Where are the Registrar and Finance offices?').queries,
                         ('Where are the Registrar offices?', 'Where are the Finance offices?'))

    def test_dependent_action_binds_only_to_explicit_resource(self):
        result = resolve_turn('What scholarships are available, and how do I apply?')
        self.assertEqual(result.queries, ('What scholarships are available?', 'how do I apply for scholarships?'))
        result = resolve_turn('Who is the university president, and how do I enroll?')
        self.assertEqual(result.queries[-1], 'how do I enroll?')

    def test_explicit_topic_switch_does_not_inherit_previous_clause(self):
        result = resolve_turn('Who is the University President, and what office handles enrollment?', 'Who are CEIT faculty?')
        self.assertEqual(result.queries[-1], 'what office handles enrollment?')
        self.assertNotIn('faculty', str(result.queries))

    def test_english_filipino_and_taglish(self):
        for query in ('Sino ang ICT director at CEIT dean?', 'Sino ang ICT director pati CEIT dean?',
                      'Who is the ICT director and CEIT dean po?'):
            with self.subTest(query=query):
                result = resolve_turn(query)
                self.assertEqual(len(result.queries), 2)
                self.assertIn('ICT', result.queries[0])
                self.assertIn('CEIT', result.queries[1])

    def test_contextual_entity_list_resolves_each_query(self):
        result = resolve_conversation('How about CHS and CBMA?', pair('Who are the CEIT faculty?'))
        self.assertEqual(result.queries, ('Who are the CHS faculty?', 'Who are the CBMA faculty?'))

    def test_pronoun_within_message_reuses_its_own_prior_clause(self):
        result = resolve_turn('Who is the CEIT dean, and where is their office?')
        self.assertEqual(len(result.queries), 2)
        self.assertIn('CEIT', result.queries[-1])
        self.assertNotIn('their', result.queries[-1])

    def test_singular_pronoun_after_multi_part_turn_is_ambiguous(self):
        previous = 'Who is the ICT Director and CEIT Dean?'
        self.assertTrue(resolve_turn('Where is it?', previous).clarification)
        self.assertTrue(resolve_conversation('Where is it?', pair(previous)).clarification)

    def test_explicit_entity_followup_can_select_one_prior_slot(self):
        result = resolve_turn('How about CHS?', 'Who is the ICT Director and CEIT Dean?')
        self.assertEqual(len(result.queries), 1)
        self.assertIn('CHS', result.queries[0])
        self.assertIn('Dean', result.queries[0])
        self.assertNotIn('ICT', result.queries[0])

    def test_plural_attribute_followup_refetches_each_subject(self):
        result = resolve_turn('What are their office hours?', 'Where are the Registrar and Finance offices?')
        self.assertEqual(len(result.queries), 2)
        self.assertIn('Registrar', result.queries[0])
        self.assertIn('Finance', result.queries[1])

    def test_new_domains_and_named_resources_need_no_domain_branch(self):
        for noun in ('policy', 'scholarship', 'academic program', 'procedure', 'announcement'):
            query = f'What are the requirements for Alpha {noun} and Beta {noun}?'
            result = resolve_turn(query)
            self.assertEqual(len(result.queries), 2)
            self.assertIn(f'Alpha {noun}', result.queries[0])
            self.assertIn(f'Beta {noun}', result.queries[1])

    def test_known_labels_and_quoted_titles_keep_internal_conjunctions(self):
        for query in ('Who is the dean of College of Engineering and Information Technology?',
                      'Explain the "Research and Development" policy?',
                      'What are the requirements for "Merit and Service"?'):
            self.assertEqual(resolve_turn(query).queries, (query,))
        vocabulary = Vocabulary([Entity('scholarship', 'merit', 'Merit and Service', ('Merit and Service',))])
        self.assertEqual(decompose_query('What is Merit and Service?', vocabulary).queries,
                         ('What is Merit and Service?',))

    def test_ambiguous_conjunctions_and_relational_questions_stay_atomic(self):
        for query in ('What is research and development?', 'What is the relationship between CEIT and CHS?',
                      'Is CEIT or CHS available?', 'Directions from Registrar to Finance'):
            self.assertEqual(resolve_turn(query).queries, (query,))

    def test_shared_dates_and_negation_are_never_dropped(self):
        for query in ('Who are the deans of CEIT and CHS in 2099?',
                      'Who is the ICT director and CEIT dean without credentials?'):
            result = resolve_turn(query)
            self.assertEqual(len(result.queries), 2)
            suffix = '2099' if '2099' in query else 'without credentials'
            self.assertTrue(all(suffix in part for part in result.queries))

    def test_clause_specific_dates_and_institutions_do_not_mix(self):
        result = resolve_turn('Who is the dean in 2020, and who is the president in 2025?')
        self.assertIn('2020', result.queries[0])
        self.assertNotIn('2025', result.queries[0])
        result = resolve_turn('Who is the ICT director and CEIT dean at Mars University?')
        self.assertTrue(all('Mars University' in query for query in result.queries))

    def test_complexity_bound_and_incomplete_request(self):
        query = ' and '.join('Who is person ' + str(index) for index in range(MAX_PARTS+1))
        self.assertTrue(resolve_turn(query).clarification)
        self.assertTrue(resolve_turn('Who is the ICT Director and ').clarification)
        self.assertTrue(resolve_turn('x' * 2001).clarification)

    def test_duplicates_are_retrieved_once(self):
        result = resolve_turn('Who is the ICT director and ICT director?')
        self.assertEqual(result.queries, ('Who is the ICT director?',))

    def test_mixed_shared_slots_and_independent_clauses(self):
        result = resolve_turn('Who is the ICT director and CEIT dean, and where is the Registrar office?')
        self.assertEqual(result.queries, ('Who is the ICT director?', 'Who is the CEIT dean?', 'where is the Registrar office?'))

    def test_resolved_multi_turn_intent_survives_more_than_one_followup(self):
        history = pair('Who are the CEIT faculty?') + pair('How about CHS and CBMA?')
        result = resolve_conversation('What are their office hours?', history)
        self.assertEqual(len(result.queries), 2)
        self.assertIn('CHS', result.queries[0])
        self.assertIn('CBMA', result.queries[1])

    def test_dependent_resource_attributes_are_grammatical(self):
        result = resolve_turn('What scholarships are available, and what are their requirements?')
        self.assertEqual(result.queries[-1], 'what are the requirements for scholarships?')

    def test_role_comparison_can_include_more_than_two_entity_spans(self):
        result = resolve_turn('Compare the deans of CEIT and CHS')
        self.assertEqual(result.relation, 'comparison')
        self.assertEqual(result.queries, ('Who are the deans of CEIT?', 'Who are the deans of CHS?'))

    def test_pronoun_after_two_parallel_subjects_does_not_pick_the_last(self):
        result = resolve_turn('Who is the ICT director and CEIT dean, and where is their office?')
        self.assertEqual(len(result.queries), 3)
        self.assertEqual(result.queries[-1], 'where is their office?')
        answer = bot_for(lambda query: []).process_query('Who is the ICT director and CEIT dean, and where is their office?')
        self.assertEqual(answer.answer_parts[-1]['status'], 'clarification')

    def test_bare_action_clarifies_without_a_unique_resource(self):
        self.assertTrue(resolve_turn('How do I apply?').clarification)
        self.assertTrue(resolve_turn('How do I apply?', 'What are the requirements for Alpha?; What are the requirements for Beta?').clarification)

    def test_repeated_roles_and_steps_need_a_unique_prior_part(self):
        previous = 'Who is the ICT director and CEIT dean?'
        for query in ('Who is currently holding that role?', 'Explain step 3', 'Compare it with CHS'):
            self.assertTrue(resolve_turn(query, previous).clarification)

    def test_valid_plural_words_are_not_rewritten_as_typos(self):
        query = 'What scholarships are available and who are the deans?'
        self.assertEqual(normalize_query(query), query)


class CompoundAnswerTests(unittest.TestCase):
    def test_independent_personnel_results_are_combined_and_cited_separately(self):
        rows = {
            'Who is the ICT Director?': evidence('Who is the ICT Director?', 'Dr. Alice Example is the ICT Director.'),
            'Who is the CEIT Dean?': evidence('Who is the CEIT Dean?', 'Dr. Bob Example is the CEIT Dean.'),
        }
        bot = bot_for(lambda query: [rows[query]])
        result = bot.process_query('Who is the ICT Director and CEIT Dean?')
        self.assertIn('Alice Example', result[0]); self.assertIn('Bob Example', result[0])
        self.assertEqual(len(result[1]), 2)
        self.assertEqual([part['source_indices'] for part in result.answer_parts], [[1], [2]])
        self.assertEqual([source['part'] for source in result[1]], [1, 2])
        self.assertEqual(bot.rag.search.call_count, 2)

    def test_missing_part_retains_successful_answer(self):
        bot = bot_for(lambda query: [evidence(query, 'Dr. Alice Example is the ICT Director.')] if 'ICT' in query else [])
        result = bot.process_query('Who is the ICT director, and who is the director of Mars?')
        self.assertIn('Alice Example', result[0]); self.assertIn('verified information', result[0])
        self.assertEqual([part['status'] for part in result.answer_parts], ['ok', 'no_match'])
        self.assertEqual(result.answer_status, 'partial')
        self.assertEqual(len(result[1]), 1)

    def test_conflict_and_retrieval_failure_only_affect_their_part(self):
        for status in ('conflict', 'unavailable', 'ambiguous'):
            class Retriever:
                def retrieve(self, query, **kwargs):
                    return (RetrievalOutcome([evidence(query, 'Dr. Alice Example is the ICT Director.')], 'ok')
                            if 'ICT' in query else RetrievalOutcome(status=status))
            bot = bot_for(lambda query: [])
            bot.rag = Retriever()
            result = bot.process_query('Who is the ICT director, and who is the CEIT dean?')
            self.assertIn('Alice Example', result[0])
            self.assertEqual([part['status'] for part in result.answer_parts], ['ok', status])
            self.assertEqual(len(result[1]), 1)

    def test_exception_in_one_part_does_not_erase_other_parts(self):
        def lookup(query):
            if 'CEIT' in query:
                raise RuntimeError('private connection details')
            return [evidence(query, 'Dr. Alice Example is the ICT Director.')]
        result = bot_for(lookup).process_query('Who is the ICT director and CEIT dean?')
        self.assertIn('Alice Example', result[0])
        self.assertNotIn('private connection details', result[0])
        self.assertEqual(result.answer_parts[-1]['status'], 'unavailable')

    def test_other_part_evidence_cannot_pass_wrong_entity_gate(self):
        wrong = evidence('Who is the ICT Director?', 'Dr. Alice Example is the ICT Director.')
        result = bot_for(lambda query: [wrong]).process_query('Who is the ICT director and CEIT dean?')
        self.assertEqual(len(result[1]), 1)
        self.assertEqual(result.answer_parts[-1]['status'], 'no_match')

    def test_category_clarification_does_not_block_another_topic(self):
        result = bot_for(lambda query: [evidence(query, 'Dr. Alice Example is the University President.')]).process_query(
            'Who is the University President, and how do I enroll?')
        self.assertIn('Alice Example', result[0])
        self.assertIn('incoming college freshman', result[0])
        self.assertEqual(result.answer_parts[-1]['status'], 'clarification')

    def test_map_destinations_are_choices_and_do_not_invent_locations(self):
        bot = bot_for(lambda query: self.fail('Navigation should not call retrieval'))
        result = bot.process_query('Where are the Registrar and Finance offices?')
        self.assertIsNone(result[2])
        self.assertIn('Directions to Registrar Office', result[0])
        self.assertIn('Directions to Finance Office', result[0])
        self.assertNotIn('Opening the campus map', result[0])
        self.assertEqual([row['source_type'] for row in result[1]], ['campus_map', 'campus_map'])

    def test_entire_message_has_at_most_one_selector_provider_call(self):
        def lookup(query):
            return [evidence(query, f'Policy requirements for {query}: stored item {i}.') for i in (1, 2)]
        bot = bot_for(lookup)
        client = Mock()
        client.chat.completions.create.side_effect = TimeoutError()
        bot.client = client
        bot.openai_client = Mock()
        result = bot.process_query('What are policy requirements for Alpha and Beta?')
        self.assertEqual(client.chat.completions.create.call_count, 1)
        bot.openai_client.chat.completions.create.assert_not_called()
        self.assertEqual(len(result.answer_parts), 2)

    def test_no_history_fact_can_supply_a_missing_compound_answer(self):
        bot = bot_for(lambda query: [])
        result = bot.process_query('Who is the ICT director and CEIT dean?', pair('Who is the ICT director?', 'Invented Person is the dean.'))
        self.assertEqual(result[1], [])
        self.assertNotIn('Invented Person', result[0])

    def test_owner_thread_token_isolation_preserves_compound_intent(self):
        query = 'Who is the ICT director and CEIT dean?'
        result = bot_for(lambda query: []).process_query(query)
        self.assertEqual(len(resolve_turn(result.context_query).queries), 2)
        token = encode_context(result.context_query, 'guest', 'tab-a')
        self.assertEqual(decode_context(token, 'guest', 'tab-a'), result.context_query)
        self.assertEqual(decode_context(token, 'user:1', 'tab-a'), '')
        self.assertEqual(decode_context(token, 'guest', 'tab-b'), '')

    def test_guest_api_exposes_parts_without_persistence(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from . import views
        bot = bot_for(lambda query: [])
        request = APIRequestFactory().post('/api/chat', {'message': 'Who is the ICT director and CEIT dean?',
                                                        'mode': 'guest'}, format='json')
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True, pk=42, username='fixture'))
        with patch.object(views, 'bot', bot), patch.object(views.ChatHistory.objects, 'create') as save:
            response = views.chat_api(request)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['saved'])
        self.assertEqual(len(response.data['answer_parts']), 2)
        save.assert_not_called()

    def test_limit_rejection_uses_no_retrieval_or_provider(self):
        bot = bot_for(lambda query: self.fail('An over-limit message must not retrieve'))
        bot.client = Mock()
        query = 'How about ' + ' and '.join(('CEIT', 'CHS', 'CBMA', 'CEAS', 'CCJE'))
        result = bot.process_query(query, context_query='Who are the CEIT faculty?')
        self.assertIn('at most', result[0])
        bot.client.chat.completions.create.assert_not_called()

    def test_non_personnel_domains_use_independent_grounded_evidence(self):
        for subject in ('scholarship', 'academic program', 'university policy', 'office procedure'):
            def lookup(query):
                label = 'Alpha' if 'Alpha' in query else 'Beta'
                return [evidence(query, f'{subject} requirements for {label}: verified {label} documents.')]
            result = bot_for(lookup).process_query(f'What are {subject} requirements for Alpha and Beta?')
            self.assertEqual(result.answer_status, 'ok')
            self.assertEqual(len(result[1]), 2)
            self.assertIn('verified Alpha documents', result[0])
            self.assertIn('verified Beta documents', result[0])

    def test_scholarship_application_is_retrieved_with_the_resource_context(self):
        def lookup(query):
            if 'apply' in query:
                self.assertIn('scholarship', query)
                return [evidence('How do I apply for scholarships?', 'Apply for scholarships: submit the verified application form.')]
            return [evidence('What scholarships are available?', 'Scholarships available: Fictional Scholarship A.')]
        result = bot_for(lookup).process_query('What scholarships are available, and how do I apply?')
        self.assertEqual(result.answer_status, 'ok')
        self.assertEqual(len(result[1]), 2)
        self.assertIn('verified application form', result[0])

    def test_a_conflict_before_success_does_not_abort_remaining_retrieval(self):
        class Retriever:
            def retrieve(self, query, **kwargs):
                return (RetrievalOutcome(status='conflict') if 'CEIT' in query else
                        RetrievalOutcome([evidence(query, 'Dr. Alice Example is the ICT Director.')], 'ok'))
        bot = bot_for(lambda query: [])
        bot.rag = Retriever()
        result = bot.process_query('Who is the CEIT dean and ICT director?')
        self.assertEqual([part['status'] for part in result.answer_parts], ['conflict', 'ok'])
        self.assertIn('Alice Example', result[0])

    def test_signed_resolved_context_supports_a_later_multi_subject_attribute(self):
        bot = bot_for(lambda query: [])
        result = bot.process_query('How about CHS and CBMA?', context_query='Who are the CEIT faculty?')
        context = decode_context(encode_context(result.context_query, 'guest', 'test-tab'), 'guest', 'test-tab')
        follow = resolve_turn('What are their office hours?', context)
        self.assertEqual(len(follow.queries), 2)
        self.assertIn('CHS', follow.queries[0])
        self.assertIn('CBMA', follow.queries[1])

    def test_authenticated_compound_turn_is_saved_once_in_the_owned_thread(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from . import views
        query = 'Who is the ICT director and CEIT dean?'
        bot = bot_for(lambda query: [])
        user = SimpleNamespace(pk=7, id=7, username='fixture', is_authenticated=True)
        conversation = SimpleNamespace(id=42, title='Fixture', save=Mock())
        request = APIRequestFactory().post('/api/chat', {'message': query, 'mode': 'authenticated',
                                                        'conversation_id': 42}, format='json')
        force_authenticate(request, user=user)
        with patch.object(views, 'bot', bot), patch.object(views.Conversation.objects, 'get', return_value=conversation) as owned, \
                patch.object(views.ChatHistory.objects, 'filter') as history, \
                patch.object(views.ChatHistory.objects, 'create', return_value=SimpleNamespace(id=55)) as save:
            history.return_value.order_by.return_value = []
            response = views.chat_api(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['saved'])
        self.assertEqual(response.data['conversation_id'], 42)
        self.assertEqual(len(response.data['answer_parts']), 2)
        owned.assert_called_once_with(id=42, user=user, is_active=True)
        save.assert_called_once()
        self.assertEqual(save.call_args.kwargs['message'], query)
        self.assertIs(save.call_args.kwargs['conversation'], conversation)


if __name__ == '__main__':
    unittest.main()
