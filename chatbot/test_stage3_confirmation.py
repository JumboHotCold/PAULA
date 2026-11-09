from unittest.mock import patch,Mock
from django.test import SimpleTestCase,TestCase
from .logic import PauliBotLogic
from .context_tokens import encode_context,decode_dialogue_state
from .models import FAQ,CustomUser,Conversation,ChatHistory
from .rag import RAGSearcher
from .spelling import build_lexicon


def bot():
    value=PauliBotLogic.__new__(PauliBotLogic)
    value.rag=RAGSearcher();value.client=value.openai_client=value.gemini_model=None
    return value


class ConfirmationFlowTests(SimpleTestCase):
    def test_single_choice_affirmations_submit_only_the_offered_question(self):
        from .context_tokens import ConversationAnswer
        state={'pending':{'kind':'spelling','query':'Original','choices':['What is SPUS?']}}
        for reply in ('yes','oo','opo','sige','ok'):
            value=bot()
            with patch.object(value,'_process_knowledge',return_value=ConversationAnswer(('Stored answer',[],None,None))) as retrieve:
                result=value.process_query(reply,dialogue_state=state)
            retrieve.assert_called_once()
            self.assertEqual(retrieve.call_args.args[0],'What is SPUS?')
            self.assertEqual(result[0],'Stored answer')

    def test_multiple_choices_and_cancellation(self):
        state={'pending':{'kind':'spelling','query':'Original','choices':['What is SPUS?','Why choose SPUS?']}}
        for reply in ('yes','oo','opo','sige','ok'):
            result=bot().process_query(reply,dialogue_state=state)
            self.assertEqual(result.answer_status,'clarification')
            self.assertEqual(result.pending_clarification,state['pending'])
        for reply in ('no','hindi','dili'):
            result=bot().process_query(reply,dialogue_state=state)
            self.assertIsNone(result.pending_clarification)

    def test_signed_pending_is_bound_to_owner_thread_anchor(self):
        pending={'kind':'spelling','query':'Original','choices':['What is SPUS?']}
        token=encode_context('', 'user:1','thread',19,pending=pending)
        self.assertEqual(decode_dialogue_state(token,'user:1','thread',19)['pending'],pending)
        for owner,thread,anchor in (('guest','thread',19),('user:2','thread',19),('user:1','other',19),('user:1','thread',20)):
            self.assertEqual(decode_dialogue_state(token,owner,thread,anchor),{})


class OwnedConfirmationRestoreTests(TestCase):
    def test_refresh_restores_only_owned_server_saved_choices(self):
        from rest_framework.test import APIRequestFactory,force_authenticate
        from . import views
        FAQ.objects.create(question='What is the president?',answer='Reviewed fixture president role.',category='Fixture')
        user=CustomUser.objects.create_user(username='confirmation-fixture')
        value=bot()
        factory=APIRequestFactory()
        def send(message,mode='authenticated',conversation_id=None):
            request=factory.post('/api/chat',dict(message=message,mode=mode,conversation_id=conversation_id),format='json')
            force_authenticate(request,user=user)
            with patch.object(views,'bot',value):return views.chat_api(request)
        first=send('What is the preseidnt?')
        thread=first.data['conversation_id']
        second=send('yes',conversation_id=thread)  # no client token after refresh
        self.assertIn('Reviewed fixture',second.data['response'])
        self.assertEqual(ChatHistory.objects.count(),2)
        guest=send('yes',mode='guest',conversation_id=thread)
        self.assertFalse(guest.data['saved'])
        self.assertFalse(guest.data['sources'])
        self.assertEqual(ChatHistory.objects.count(),2)
