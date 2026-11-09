"""Bounded non-factual social replies, selected locally without API calls."""
from .conversation_config import conversation_config


REPLIES = conversation_config()['replies']


def candidates(kind, language='en', history=()):
    choices = REPLIES.get(kind, REPLIES['chat_clarification']).get(language, REPLIES['chat_clarification']['en'])
    prior = {row.get('content', '').strip() for row in history if row.get('role') == 'assistant'}
    return [text for text in choices if text not in prior] or list(choices)
