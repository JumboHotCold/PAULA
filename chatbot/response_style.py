"""Friendly framing around unchanged source excerpts; no generated facts."""
from .context_tokens import ConversationAnswer

INTROS = {
    'en': ('Sure—here is the information from the stored sources.', 'Here is what I found in the stored sources.'),
    'fil': ('Sige—narito ang impormasyon mula sa mga nakaimbak na sanggunian.', 'Ito ang nakita ko sa mga nakaimbak na sanggunian.'),
}
ACKS = {
    'greeting': {'en': 'Hi!', 'fil': 'Kumusta!'},
    'thanks': {'en': "You're welcome!", 'fil': 'Walang anuman!'},
    'feedback': {'en': 'Thanks for pointing that out. Here is what the stored sources show.',
                 'fil': 'Salamat sa pagsabi. Narito ang nasa mga nakaimbak na sanggunian.'},
}


def strip_intro(text):
    for prefix in [*INTROS['en'], *INTROS['fil'], *[value for pair in ACKS.values() for value in pair.values()]]:
        if text.startswith(prefix + '\n\n'):
            return text[len(prefix):].lstrip()
    return text


def frame_answer(result, language='en', acknowledgement='', atomic=False):
    text, sources, action, data = result
    # Localize our own UI questions only. Never machine-translate evidence,
    # names, qualifications, amounts, dates or institutional instructions.
    if not sources:
        from .intents import ENROLL_QUESTION, ENROLL_QUESTION_FIL, NAV_QUESTION, NAV_QUESTION_FIL
        for english, filipino in ((ENROLL_QUESTION, ENROLL_QUESTION_FIL), (NAV_QUESTION, NAV_QUESTION_FIL),
                ('For basic education or graduate school, please specify your level.',
                 'Kung basic education o graduate school, sabihin ang iyong level.')):
            text = text.replace(english if language == 'fil' else filipino,
                                filipino if language == 'fil' else english)
    prefix = ACKS.get(acknowledgement, {}).get(language, '')
    followup = ('Here is the information from the SPUS sources for your follow-up.',
                'Narito ang impormasyon mula sa SPUS sources para sa iyong follow-up.')
    if not prefix and sources and not atomic and not text.startswith(followup):
        prefix = INTROS[language][0]
    if prefix:
        text = prefix + '\n\n' + text
    return ConversationAnswer((text, sources, action, data), getattr(result, 'context_query', ''),
                              status=getattr(result, 'answer_status', None), parts=getattr(result, 'answer_parts', ()),
                              mode='mixed' if acknowledgement else 'knowledge')
