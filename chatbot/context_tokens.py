"""Stateless, short-lived intent continuity. Tokens contain no answer facts."""
from django.core import signing

from .conversation_context import CONTEXT_TTL

SALT = 'paula.conversation.intent.v1'


class ConversationAnswer(tuple):
    """Preserve the existing four-value response contract with optional metadata."""
    def __new__(cls, values, query='', status=None, parts=(), mode='knowledge', language=None, pending=None):
        value = super().__new__(cls, values)
        value.context_query = query
        value.answer_status = status or getattr(values, 'answer_status', 'ok')
        value.answer_parts = list(parts)
        value.response_mode = mode
        value.language_preference = language
        value.pending_clarification = pending
        return value


def encode_context(query, owner, thread, anchor=None, language=None, pending=None):
    if not isinstance(query, str) or len(query) > 2000:
        return None
    state = {'query':query, 'owner':str(owner), 'thread':str(thread), 'anchor':anchor}
    if language in ('en', 'fil'):
        state['language'] = language
    if isinstance(pending, dict) and set(pending) == {'kind', 'query'} and pending.get('kind') in ('enrollment', 'navigation'):
        if isinstance(pending.get('query'), str) and 0 < len(pending['query']) <= 2000:
            state['pending'] = pending
    if not query and 'language' not in state and 'pending' not in state:
        return None
    return signing.dumps(state, salt=SALT, compress=True)


def decode_dialogue_state(token, owner, thread, anchor=None):
    if not isinstance(token, str) or len(token) > 6000:
        return {}
    try:
        data = signing.loads(token, salt=SALT, max_age=CONTEXT_TTL)
    except (signing.BadSignature, ValueError, TypeError):
        return {}
    if not isinstance(data, dict) or data.get('owner') != str(owner) or data.get('thread') != str(thread):
        return {}
    if anchor is not None and data.get('anchor') != anchor:
        return {}
    query = data.get('query')
    if not isinstance(query, str) or len(query) > 2000:
        return {}
    state = {'query': query}
    if data.get('language') in ('en', 'fil'):
        state['language'] = data['language']
    pending = data.get('pending')
    if (isinstance(pending, dict) and set(pending) == {'kind', 'query'} and
            pending.get('kind') in ('enrollment', 'navigation') and isinstance(pending.get('query'), str) and
            0 < len(pending['query']) <= 2000):
        state['pending'] = pending
    return state


def decode_context(token, owner, thread, anchor=None):
    return decode_dialogue_state(token, owner, thread, anchor).get('query', '')
