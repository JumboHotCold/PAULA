"""Matching safety, privacy and real PostgreSQL retrieval integration."""
from types import SimpleNamespace
from unittest.mock import Mock, patch
import json
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from .dialogue import route_turn
from .logic import PauliBotLogic
from .models import FAQ, StaffMember, Location, WebResource, Conversation, ChatHistory, CustomUser
from .rag import RAGSearcher
from .spelling import build_lexicon, matching_plan, prepare_vocabulary, confirmation_questions, edit_distance


def fixture_lexicon():
    return build_lexicon(['What programs are offered at SPUS?', 'What are the library policies?',
                          'What scholarships are available?', 'dean mean formation'],
                         names=['Mara Cortez','Tara Cortez','Alice Santos'],acronyms=['CEIT','ICT'])


def local_bot(rag=None):
    bot=PauliBotLogic.__new__(PauliBotLogic)
    bot.rag=rag if rag is not None else Mock()
    bot.client=bot.openai_client=bot.gemini_model=None
    bot.model_name='unused-test-provider'
    return bot


class SpellingSafetyTests(SimpleTestCase):
    def setUp(self):
        self.lexicon=fixture_lexicon()
        snapshot=patch('chatbot.spelling._public_lexicon',self.lexicon)
        snapshot.start()
        self.addCleanup(snapshot.stop)

    def test_known_tokens_are_never_corrected(self):
        for word in self.lexicon.words:
            self.assertEqual(matching_plan(word).matching,word)

    def test_unique_edits_use_length_aware_distance(self):
        for word,target,distance in (('abuot','about',1),('ofered','offered',1),
                                     ('progrmas','programs',1),('enorll','enroll',1)):
            with self.subTest(word=word):
                plan=matching_plan(word)
                self.assertEqual(plan.matching,target)
                self.assertEqual(plan.corrections[0].distance,distance)
        self.assertEqual(edit_distance('ab','ba'),1)

    def test_ambiguous_token_stays_unchanged_and_offers_choices(self):
        plan=matching_plan('Who is the fean?')
        self.assertIn('fean',plan.matching)
        self.assertIn('fean',plan.ambiguous)
        self.assertTrue(plan.needs_confirmation)
        self.assertGreaterEqual(len(confirmation_questions(plan)),2)

    def test_numbers_acronyms_urls_and_identifiers_are_opaque(self):
        for text in ('CEIT ICF WHT 2026-00123', 'URO-PR-016', 'https://example.org/abuot',
                     'abuot@example.org','student_abuot_17','abc123def','ICT-2026','item-abuot-2026'):
            self.assertEqual(matching_plan(text).matching,text)

    def test_person_names_and_nearby_names_are_not_rewritten(self):
        for text in ('Who is Alice Santoz?', 'Who is alice santoz?', 'Who is Mra Cortez?'):
            plan=matching_plan(text)
            self.assertEqual(plan.matching,text)
            self.assertTrue(plan.protected_name)
            result=local_bot().process_query(text)
            self.assertEqual(result.answer_status,'clarification')
            self.assertFalse(result[1])

    def test_valid_name_one_edit_from_another_name_requires_disambiguation(self):
        # A corruption can itself spell another real person's name. No system
        # can recover the intended name from those bytes alone: ask for a role.
        for name in ('Mara Cortez','Tara Cortez'):
            plan=matching_plan('Who is '+name+'?')
            self.assertTrue(plan.protected_name)
            self.assertIn(name,plan.matching)

    def test_repeat_collapsing_never_reaches_factual_matching(self):
        self.assertEqual(route_turn('thankyouuu',semantic=False).kind,'thanks')
        plan=matching_plan('What are the prograaammmss?')
        self.assertIn('prograaammmss',plan.matching)
        self.assertEqual(route_turn('thankyouuu scholarship rules',semantic=False).kind,'knowledge')

    def test_borderline_factual_correction_asks_without_retrieving(self):
        bot=local_bot()
        result=bot.process_query('What is the preseidnt?')
        self.assertEqual(result.answer_status,'clarification')
        self.assertIn('Did you mean',result[0])
        bot.rag.search.assert_not_called()

    def test_spelling_clarification_preserves_pending_task_and_anchor(self):
        pending={'kind':'enrollment','query':'How do I enroll?'}
        result=local_bot().process_query('What is the preseidnt?',context_query='How do I enroll?',
                                        dialogue_state={'pending':pending,'language':'fil'})
        self.assertEqual(result.pending_clarification,pending)
        self.assertEqual(result.context_query,'How do I enroll?')
        self.assertEqual(result.language_preference,'fil')

    def test_greeting_tail_and_all_local_pattern_tokens_share_spelling_step(self):
        self.assertEqual(route_turn('hi, tell me abuot yourself?',semantic=False).kind,'identity')
        self.assertEqual(route_turn('hi, what are the programs ofered',semantic=False).query,'what are the programs offered')
        for text,kind in (('can you hepl me','capabilities'),('introduec yourself','identity'),
                          ('goodmorniing','greeting'),('salamat kaaayo','thanks')):
            with self.subTest(text=text):
                self.assertEqual(route_turn(text,semantic=False).kind,kind)

    def test_multi_social_never_discards_institutional_or_unknown_clauses(self):
        for text in ('who r u and wat can u do','sino ka at ano ang kaya mong gawin?'):
            self.assertEqual(route_turn(text,semantic=False).kind,'social_bundle')
        for text in ('who r u, what is your office policy?', 'thanks, ICT director',
                     'tell me about yourself, fees without documents in 2037',
                     'who r u, name the CEIT dean, thankyouuu', 'who r u, blorptastic'):
            self.assertEqual(route_turn(text,semantic=False).kind,'knowledge',text)

    def test_spacing_repairs_are_unique_and_do_not_consume_known_tokens(self):
        plan=matching_plan('prog rams offered')
        self.assertEqual(plan.matching,'programs offered')
        self.assertFalse(plan.needs_confirmation)
        self.assertEqual(matching_plan('in formation').matching,'in formation')
        self.assertEqual(matching_plan('ofered prog rams').matching,'offered programs')

    def test_matching_is_idempotent_and_original_is_immutable(self):
        text='  Hi, tell me abuot yourself?  '
        plan=matching_plan(text)
        self.assertEqual(plan.original,text)
        self.assertEqual(matching_plan(plan.matching).matching,plan.matching)
        with self.assertRaises(AttributeError):
            plan.original='changed'

    def test_unicode_view_preserves_original_and_acronym_capitalization(self):
        plan=matching_plan('Ｗｈａｔ programs are ofered at ＳＰＵＳ?')
        self.assertEqual(plan.original,'Ｗｈａｔ programs are ofered at ＳＰＵＳ?')
        self.assertEqual(plan.matching,'What programs are offered at SPUS?')

    def test_retrieval_receives_corrected_query_and_blocks_uncertain_plans(self):
        rag=RAGSearcher()
        with patch.object(rag,'search',return_value=[]) as search:
            rag.retrieve('What programs are ofered?')
            search.assert_called_once_with('What programs are offered?',5)
        for text in ('Who is Alice Santoz?', 'Who is the fean?','What is the preseidnt?'):
            with patch.object(rag,'search') as search:
                self.assertEqual(rag.retrieve(text).status,'ambiguous')
                search.assert_not_called()

    def test_existing_config_exemplars_use_same_local_boundary(self):
        from .conversation_config import conversation_config
        for kind,texts in conversation_config()['semantic']['exemplars'].items():
            for text in texts:
                route=route_turn(text,semantic=False)
                # The semantic acknowledgement class uses existing local yes/no
                # classes for their shorter canonical wording.
                expected={kind,'affirmation','negation'} if kind=='acknowledgement' else {kind}
                self.assertIn(route.kind,expected,text)


class SpellingPostgreSQLTests(TestCase):
    def setUp(self):
        self.faq=FAQ.objects.create(question='What programs are offered at SPUS?',answer='Reviewed fixture program catalog.',category='Fixture')
        self.staff=StaffMember.objects.create(name='Alice Santos',position='Dean',office='Fixture Office')
        Location.objects.create(name='Fixture Hall',description='Reviewed fixture location.')
        snapshot=patch('chatbot.spelling._public_lexicon',None)
        snapshot.start()
        self.addCleanup(snapshot.stop)
        prepare_vocabulary()

    def test_startup_snapshot_is_cached_immutable_and_public_only(self):
        with self.assertNumQueries(0):
            lexicon=prepare_vocabulary()
            self.assertIs(prepare_vocabulary(),lexicon)
        self.assertIn('offered',lexicon.words)
        self.assertIn('santos',lexicon.names)
        self.assertEqual(dict(lexicon.source_counts)['faq'],1)
        with self.assertRaises(TypeError):
            lexicon.by_length[4]=()

    def test_website_personnel_names_are_protected_without_ingestion(self):
        WebResource.objects.create(url='https://spus.edu.ph/administrator/',category='Website personnel',
            title='SPUS Personnel | Fixture | Director | Patricia Sample',
            content='Section: Fixture\nName: Patricia Sample\nRole: Director')
        with patch('chatbot.spelling._public_lexicon',None):
            lexicon=prepare_vocabulary()
            self.assertEqual(dict(lexicon.source_counts)['website_people'],1)
            plan=matching_plan('who is patrica sample')
        self.assertTrue(plan.protected_name)
        self.assertEqual(plan.matching,'who is patrica sample')

    def test_exact_retrieval_and_response_boundary_use_same_corrected_form(self):
        rag=RAGSearcher()
        with patch.object(rag,'_generate_embedding',side_effect=AssertionError('Exact FAQ requires no vector')):
            result=local_bot(rag).process_query('hi, what are the programs ofered')
        self.assertIn(self.faq.answer,result[0])
        self.assertEqual(result.answer_status,'ok')
        self.assertEqual(len(result[1]),1)

    def test_literal_staff_name_cannot_pick_a_different_vector_neighbor(self):
        StaffMember.objects.create(name='Alicia Santos',position='Director',office='Fixture Office')
        rag=RAGSearcher()
        with patch.object(rag,'_hybrid_search',side_effect=AssertionError('No name guessing')):
            exact=rag.retrieve('Who is Alice Santos?')
            missing=rag.retrieve('Who is Alice Unknown?')
        self.assertEqual([row['personnel_name'] for row in exact.evidence],['Alice Santos'])
        self.assertEqual(missing.evidence,[])

    def test_hybrid_embedding_and_keyword_gates_receive_same_form(self):
        rag=RAGSearcher()
        model=Mock()
        model.encode.return_value=SimpleNamespace(tolist=lambda:[1.0]+[0.0]*383)
        rag.model=model
        rag.retrieve('What programs are ofered without documents?')
        model.encode.assert_called_once_with('What programs are offered without documents?')

    def test_guest_typo_utterance_never_creates_history_under_existing_identity(self):
        from . import views
        user=CustomUser.objects.create_user(username='spelling-fixture',password='unused-test-password')
        request=APIRequestFactory().post('/api/chat',dict(message='tell me abuot yourself',mode='guest'),format='json')
        force_authenticate(request,user=user)
        with patch.object(views,'bot',local_bot(RAGSearcher())):
            response=views.chat_api(request)
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.data['saved'])
        self.assertEqual(response.data['response_mode'],'identity')
        self.assertEqual(Conversation.objects.count(),0)
        self.assertEqual(ChatHistory.objects.count(),0)

    def test_authenticated_history_keeps_submitted_typo_unchanged(self):
        from . import views
        user=CustomUser.objects.create_user(username='spelling-student',password='unused-test-password')
        original='tell me abuot yourself'
        request=APIRequestFactory().post('/api/chat',dict(message=original,mode='authenticated'),format='json')
        force_authenticate(request,user=user)
        with patch.object(views,'bot',local_bot(RAGSearcher())):
            response=views.chat_api(request)
        self.assertTrue(response.data['saved'])
        self.assertEqual(ChatHistory.objects.get(user=user).message,original)

    @override_settings(PAULA_LOG_UNANSWERED_QUERIES=True)
    def test_rehearsal_log_retains_original_not_corrected_input(self):
        from . import views
        request=APIRequestFactory().post('/api/chat',dict(message='What is the preseidnt?',mode='guest'),format='json')
        with patch.object(views,'bot',local_bot(RAGSearcher())), self.assertLogs('paula.rehearsal') as logs:
            response=views.chat_api(request)
        event=json.loads(logs.output[0].split(':',2)[2])
        self.assertEqual(event['query_text'],'What is the preseidnt?')
        self.assertFalse(response.data['saved'])

    def test_spelling_confirmation_uses_existing_frontend_choice_protocol(self):
        from . import views
        request=APIRequestFactory().post('/api/chat',dict(message='What is the preseidnt?',mode='guest'),format='json')
        with patch.object(views,'bot',local_bot(RAGSearcher())):
            response=views.chat_api(request)
        self.assertEqual(response.data['answer_status'],'clarification')
        self.assertEqual(response.data['suggestions_kind'],'choice')
        self.assertEqual(response.data['suggestions'],['What is the president?'])
