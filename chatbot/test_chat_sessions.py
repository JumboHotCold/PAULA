"""Guest privacy and chat session contracts; no test accounts or DB writes."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from rest_framework.test import APIRequestFactory, force_authenticate
from . import views


class SessionPrivacyTests(unittest.TestCase):
    def request(self, payload, authenticated=True):
        request = APIRequestFactory().post('/api/chat', payload, format='json')
        if authenticated:
            force_authenticate(request, user=SimpleNamespace(pk=123, id=123, username='fixture', is_authenticated=True))
        return request

    def test_explicit_guest_with_authenticated_cookie_never_reads_or_saves_history(self):
        request = self.request({'message':'hello', 'mode':'guest', 'conversation_id':99, 'chat_session_id':str(uuid4())})
        bot = Mock()
        bot.process_query.return_value=('Hello.', [], None, None)
        with patch.object(views,'bot',bot), patch.object(views.Conversation.objects,'get') as get, \
                patch.object(views.Conversation.objects,'create') as create, patch.object(views.ChatHistory.objects,'filter') as history, \
                patch.object(views.ChatHistory.objects,'create') as save:
            response = views.chat_api(request)
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.data['saved'])
        self.assertEqual(response.data['user'],'guest')
        self.assertIsNone(response.data['conversation_id'])
        for mocked in (get,create,history,save): mocked.assert_not_called()

    def test_claiming_authenticated_mode_does_not_grant_anonymous_access(self):
        response=views.chat_api(self.request({'message':'hello','mode':'authenticated'},authenticated=False))
        self.assertEqual(response.status_code,401)

    def test_missing_conversation_id_reuses_same_owned_client_session(self):
        key=str(uuid4())
        conversation=SimpleNamespace(id=42,title='Fixture',is_active=True,save=Mock())
        bot=Mock(); bot.process_query.return_value=('Hello.',[],None,None)
        with patch.object(views,'bot',bot), patch.object(views.Conversation.objects,'filter') as lookup, \
                patch.object(views.Conversation.objects,'get_or_create') as create, \
                patch.object(views.ChatHistory.objects,'filter') as history, \
                patch.object(views.ChatHistory.objects,'create',return_value=SimpleNamespace(id=1)) as save:
            lookup.return_value.first.return_value=conversation
            history.return_value.order_by.return_value=[]
            for _ in range(3):
                response=views.chat_api(self.request({'message':'hello','mode':'authenticated','chat_session_id':key}))
                self.assertEqual(response.data['conversation_id'],42)
            self.assertEqual(save.call_count,3)
            create.assert_not_called()
            for call in lookup.call_args_list:
                self.assertEqual(call.kwargs['user'].pk,123)

    def test_foreign_or_missing_conversation_does_not_create_a_replacement(self):
        bot=Mock()
        with patch.object(views,'bot',bot), patch.object(views.Conversation.objects,'get',side_effect=views.Conversation.DoesNotExist), \
                patch.object(views.Conversation.objects,'create') as create:
            response=views.chat_api(self.request({'message':'hello','mode':'authenticated','conversation_id':99}))
        self.assertEqual(response.status_code,404)
        bot.process_query.assert_not_called()
        create.assert_not_called()

    def test_deleted_session_is_not_resurrected(self):
        with patch.object(views.Conversation.objects,'filter') as lookup:
            lookup.return_value.first.return_value=SimpleNamespace(id=42,is_active=False)
            response=views.chat_api(self.request({'message':'hello','mode':'authenticated','chat_session_id':str(uuid4())}))
        self.assertEqual(response.status_code,409)

    def test_invalid_mode_and_uuid_are_rejected(self):
        for body in ({'message':'hello','mode':'invalid'},{'message':'hello','chat_session_id':'invalid'}):
            self.assertEqual(views.chat_api(self.request(body)).status_code,400)

    def test_stale_browser_identity_cannot_write_to_another_logged_in_account(self):
        request=self.request({'message':'hello','mode':'authenticated','account_id':'another-account'})
        request._force_auth_user.student_id='current-account'
        response=views.chat_api(request)
        self.assertEqual(response.status_code,401)

    def test_cookie_without_explicit_authenticated_mode_defaults_to_unsaved(self):
        bot=Mock();bot.process_query.return_value=('Hello.',[],None,None)
        with patch.object(views,'bot',bot),patch.object(views.ChatHistory.objects,'create') as save:
            response=views.chat_api(self.request({'message':'hello'}))
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.data['saved'])
        save.assert_not_called()


if __name__=='__main__':
    unittest.main()
