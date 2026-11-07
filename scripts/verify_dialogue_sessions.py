"""PostgreSQL integration with existing accounts; all temporary writes roll back.

The RAG fixture has no institutional claims. This tests session ownership and
continuity, not live retrieval quality. No external providers are contacted.
"""
import json
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from django.db import connection, transaction
from django.test import Client

from chatbot.context_tokens import decode_dialogue_state
from chatbot.logic import PauliBotLogic
from chatbot.models import ChatHistory, Conversation, CustomUser


def main():
    assert connection.vendor == 'postgresql'
    accounts = list(CustomUser.objects.filter(is_active=True).order_by('is_superuser', 'pk')[:2])
    assert len(accounts) == 2, 'Two existing accounts required; no account will be created'
    baseline = (Conversation.objects.count(), ChatHistory.objects.count())
    value = PauliBotLogic.__new__(PauliBotLogic)
    value.rag = Mock()
    value.rag.search.return_value = []
    value.client = value.openai_client = value.gemini_model = None
    value.model_name = 'test'
    checks = []

    def passed(name, condition):
        assert condition, name
        checks.append(dict(check=name, passed=True))

    with transaction.atomic(), patch('chatbot.views.bot', value):
        client = Client(HTTP_HOST='localhost')
        client.force_login(accounts[0])
        session_id = str(uuid4())

        def ask(message, token=None, **options):
            payload = dict(message=message, mode='authenticated', chat_session_id=session_id, context_token=token)
            payload.update(options)
            response = client.post('/api/chat', json.dumps(payload), content_type='application/json')
            assert response.status_code == 200, response.status_code
            return response.json()

        first = ask('How do I enroll?')
        thread = first['conversation_id']
        thanks = ask('Thanks', first['context_token'])
        language = ask('Taglish please', thanks['context_token'])
        okay = ask('Okay', language['context_token'])
        passed('one_authenticated_thread_for_all_turns', all(row['conversation_id'] == thread for row in (first, thanks, language, okay)))
        passed('preference_follows_owned_session', 'Sige' in okay['response'])
        saved_state = decode_dialogue_state(okay['context_token'], f'user:{accounts[0].pk}', thread, okay['chat_history_id'])
        passed('pending_category_survives_social_turns', saved_state['pending']['kind'] == 'enrollment')
        value.rag.search.reset_mock()
        category = ask('I am a transferee', okay['context_token'])
        passed('natural_category_uses_original_query', 'enroll' in value.rag.search.call_args.args[0] and 'transferee' in value.rag.search.call_args.args[0])
        passed('five_prompts_grouped_in_one_thread', ChatHistory.objects.filter(conversation_id=thread).count() == 5)
        before_guest = (Conversation.objects.count(), ChatHistory.objects.count())
        guest = ask('Hello', okay['context_token'], mode='guest', context_id='guest-tab', conversation_id=thread)
        passed('guest_drops_student_identity_and_history', not guest['saved'] and guest['conversation_id'] is None and
               (Conversation.objects.count(), ChatHistory.objects.count()) == before_guest)
        passed('guest_cannot_inherit_student_language', guest['response'].startswith('Hello'))
        new = ask('Hello', okay['context_token'], chat_session_id=str(uuid4()))
        passed('new_thread_cannot_inherit_previous_token', new['response'].startswith('Hello') and new['conversation_id'] != thread)
        client.logout()
        guest = ask('Hello', okay['context_token'], mode='guest', context_id='after-logout')
        passed('logout_cannot_replay_student_state', not guest['saved'] and guest['response'].startswith('Hello'))
        client.force_login(accounts[1])
        other = ask('Hello', okay['context_token'])
        passed('another_account_cannot_replay_state', other['response'].startswith('Hello') and other['conversation_id'] != thread)
        denied = client.post('/api/chat', json.dumps(dict(message='Hello', mode='authenticated', conversation_id=thread)), content_type='application/json')
        passed('foreign_conversation_still_forbidden', denied.status_code == 404)
        transaction.set_rollback(True)
    assert baseline == (Conversation.objects.count(), ChatHistory.objects.count())
    report = dict(passed=len(checks), checks=checks, temporary_writes_rolled_back=True, new_accounts_created=0,
                  note='Existing accounts; fixture retriever, actual PostgreSQL session and persistence logic')
    Path('PAULA_DIALOGUE_SESSIONS.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
