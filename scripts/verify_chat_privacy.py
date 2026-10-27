"""Actual PostgreSQL/session integration checks, rolled back in full.

Uses existing accounts with Django's test client, never replacement accounts.
No identities, historic messages, passwords or session keys are printed/saved.
All temporary chats, auth-session changes and last-login updates roll back.
"""
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.db import connection, transaction
from django.test import Client
from chatbot.models import Conversation, ChatHistory, CustomUser


def main():
    assert connection.vendor=='postgresql'
    accounts=list(CustomUser.objects.filter(is_active=True).order_by('is_superuser','pk')[:2])
    if len(accounts)<2:
        raise RuntimeError('Two existing accounts are needed; no test account will be created.')
    baseline=(Conversation.objects.count(),ChatHistory.objects.count())
    checks=[]
    with transaction.atomic(), patch('chatbot.views.bot') as bot:
        bot.process_query.return_value=('Verification response.',[],None,None)
        client=Client(enforce_csrf_checks=True,HTTP_HOST='localhost')
        status=client.get('/api/session')
        assert status.status_code==200 and 'csrftoken' in client.cookies
        checks.append({'check':'public_session_status_sets_csrf_cookie','passed':True})
        client.force_login(accounts[0])
        assert client.get('/chat/').status_code==200

        def post(path,payload):
            token=client.cookies.get('csrftoken')
            return client.post(path,json.dumps(payload),content_type='application/json',
                               HTTP_X_CSRFTOKEN=token.value if token else '')

        def passed(name,condition):
            assert condition,name
            checks.append({'check':name,'passed':True})

        key=str(uuid4())
        first=post('/api/chat',{'message':'session first','mode':'authenticated','chat_session_id':key})
        passed('authenticated_first_prompt',first.status_code==200 and first.json()['saved'])
        thread=first.json()['conversation_id']
        second=post('/api/chat',{'message':'session second','mode':'authenticated','chat_session_id':key})
        passed('missing_id_reuses_thread',second.status_code==200 and second.json()['conversation_id']==thread)
        passed('two_messages_one_conversation',ChatHistory.objects.filter(conversation_id=thread).count()==2)
        passed('refresh_retains_group',client.get('/api/conversations').status_code==200 and
               any(row['id']==thread and row['client_session_id']==key for row in client.get('/api/conversations').json()))
        new=post('/api/chat',{'message':'new chat','mode':'authenticated','chat_session_id':str(uuid4())})
        passed('new_chat_is_separate',new.status_code==200 and new.json()['conversation_id']!=thread)
        resumed=post('/api/chat',{'message':'resumed message','mode':'authenticated','conversation_id':thread})
        passed('resume_owned_thread',resumed.status_code==200 and ChatHistory.objects.filter(conversation_id=thread).count()==3)
        before_guest=(Conversation.objects.count(),ChatHistory.objects.count())
        guest=post('/api/chat',{'message':'guest with existing student cookie','mode':'guest','conversation_id':thread,
                               'chat_session_id':key})
        passed('guest_overrides_existing_authenticated_cookie',guest.status_code==200 and not guest.json()['saved'] and
               guest.json()['conversation_id'] is None and guest.json()['user']=='guest')
        passed('guest_adds_zero_database_history',before_guest==(Conversation.objects.count(),ChatHistory.objects.count()))
        logged_out=post('/api/logout',{})
        passed('post_logout_clears_django_identity',logged_out.status_code==200 and '_auth_user_id' not in client.session)
        denied=post('/api/chat',{'message':'expired login','mode':'authenticated','chat_session_id':key})
        passed('logged_out_cannot_save_as_student',denied.status_code==401)
        anonymous=post('/api/chat',{'message':'anonymous guest','mode':'guest'})
        passed('logged_out_guest_remains_unsaved',anonymous.status_code==200 and not anonymous.json()['saved'])
        client.force_login(accounts[1]);client.get('/chat/')
        stale=post('/api/chat',{'message':'stale account tab','mode':'authenticated','chat_session_id':str(uuid4()),
                                'account_id':accounts[0].student_id or accounts[0].username})
        passed('stale_account_tab_cannot_write_under_new_identity',stale.status_code==401)
        identity=client.get('/api/session').json()
        passed('restored_identity_comes_from_django_session',identity.get('authenticated') is True and
               identity.get('id')==(accounts[1].student_id or accounts[1].username))
        forbidden=client.get(f'/api/conversations/{thread}')
        passed('other_account_cannot_read_thread',forbidden.status_code==404)
        forbidden=post('/api/chat',{'message':'cross account','mode':'authenticated','conversation_id':thread})
        passed('other_account_cannot_append_thread',forbidden.status_code==404)
        other=post('/api/chat',{'message':'second account own thread','mode':'authenticated','chat_session_id':key})
        passed('same_client_uuid_isolated_by_account',other.status_code==200 and other.json()['conversation_id']!=thread)
        visible=client.get('/api/conversations').json()
        passed('other_account_sidebar_excludes_foreign_thread',all(row['id']!=thread for row in visible))
        transaction.set_rollback(True)
    assert baseline==(Conversation.objects.count(),ChatHistory.objects.count()), 'Temporary verification data was not rolled back'
    report={'passed':len(checks),'checks':checks,'all_temporary_changes_rolled_back':True,
            'existing_conversations':baseline[0],'existing_messages':baseline[1],'new_accounts_created':0}
    target=Path('/app/PAULA_CHAT_PRIVACY_VERIFICATION.json')
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':
    main()
