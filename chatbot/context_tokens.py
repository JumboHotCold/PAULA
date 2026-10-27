"""Stateless, short-lived intent continuity. Tokens contain no answer facts."""
from django.core import signing

from .conversation_context import CONTEXT_TTL

SALT = 'paula.conversation.intent.v1'


class ConversationAnswer(tuple):
    """Preserve the existing four-value response contract with optional metadata."""
    def __new__(cls, values, query='', status=None, parts=()):
        value = super().__new__(cls, values)
        value.context_query = query
        value.answer_status = status or getattr(values, 'answer_status', 'ok')
        value.answer_parts = list(parts)
        return value


def encode_context(query, owner, thread, anchor=None):
    if not isinstance(query, str) or not query or len(query) > 2000:
        return None
    return signing.dumps({'query':query, 'owner':str(owner), 'thread':str(thread), 'anchor':anchor}, salt=SALT, compress=True)


def decode_context(token, owner, thread, anchor=None):
    if not isinstance(token, str) or len(token) > 6000:
        return ''
    try:
        data = signing.loads(token, salt=SALT, max_age=CONTEXT_TTL)
    except (signing.BadSignature, ValueError, TypeError):
        return ''
    if not isinstance(data, dict) or data.get('owner') != str(owner) or data.get('thread') != str(thread):
        return ''
    if anchor is not None and data.get('anchor') != anchor:
        return ''
    query = data.get('query')
    return query if isinstance(query, str) and len(query) <= 2000 else ''
