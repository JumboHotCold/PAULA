"""Source-backed grammatical completion/equivalence, never authored facts.

A short 'why SUBJECT?' can omit an action from an existing FAQ question.
Complete only an exact subject match; multiple actions require clarification.
Names, identifiers, conditions and factual answers are never guessed.
Listing frames share exact subject/scope signatures across lookup and grounding.
"""
import re

from .query_normalization import faq_question_key, normalized_text

REASON_ACTIONS = r'(?:apply for|study at|enroll at|choose|use|join|consider|follow|visit|contact)'
REASON_SOURCE = re.compile(r'^why (?P<action>' + REASON_ACTIONS + r') (?P<subject>.+)$')
REPHRASE_EN = "I'm not sure what you mean yet. Could you rephrase or add a little more detail?"
REPHRASE_FIL = 'Hindi ko pa malinaw ang ibig mong sabihin. Puwede mong ulitin o dagdagan ang tanong?'


def short_reason_subject(query):
    if not isinstance(query, str) or len(query) > 250:
        return None
    match = re.fullmatch(r'\s*(?:why|bakit)\s+(.+?)\s*[?!.]*\s*', query, re.I)
    if not match:
        return None
    subject = match.group(1).rstrip(' ?!.').strip()
    words = normalized_text(subject).split()
    if (not words or len(words) > 8 or re.search(r'\d|[;,:|\n\[\]<>]|https?://', subject) or
            set(words) & {'not', 'no', 'never', 'hindi', 'without', 'except', 'over', 'versus', 'vs',
                          'should', 'must', 'can', 'could', 'would', 'why', 'what', 'how', 'and', 'or', 'at', 'pati'} or
            re.match(r'^(?:' + REASON_ACTIONS + r')\b', normalized_text(subject))):
        return None
    return subject


def reason_completions(query, questions):
    subject = short_reason_subject(query)
    if subject is None:
        return ()
    found = {}
    for question in questions:
        if not isinstance(question, str) or len([part for part in question.split('?') if part.strip()]) > 1:
            continue  # Multi-question sources do not establish one meaning.
        source_key = faq_question_key(question)
        if source_key == 'why ' + normalized_text(subject):
            # An explicitly stored short question takes precedence over a
            # grammatical inference. Its conflicting answers still reach the
            # existing exact-FAQ conflict checks.
            return (f'Why {subject}?',)
        match = REASON_SOURCE.fullmatch(source_key)
        if match and match.group('subject') == normalized_text(subject):
            completed = f"Why {match.group('action')} {subject}?"
            found.setdefault(faq_question_key(completed), completed)
    return tuple(found.values())


def incomplete_request(query):
    """A missing predicate is a request for clarification, not missing facts."""
    value = normalized_text(query)
    if not value:
        return True
    if len(value.split()) > 3 or re.search(r'\d|https?://', query):
        return False
    return not re.search(r'\b(?:who|what|where|when|why|how|which|sino|ano|saan|nasaan|kailan|paano|bakit|'
                         r'tell|list|give|show|find|explain|requirements?|documents?|fees?|tuition|'
                         r'hours|scholarships?|enroll\w*|policy|policies|programs?|courses?)\b', value)


LISTING_PATTERNS = tuple(re.compile(pattern) for pattern in (
    r'^(?:what|which) (?:are |is )?(?P<subject>.+?) (?:(?:are|is) )?(?:offered|available)(?: (?P<scope>.+))?$',
    r'^(?:what|which) (?:are|is) (?:the )?(?:available|offered) (?P<subject>.+)$',
    r'^(?:what|which) (?P<subject>.+?) (?:does|do) (?P<scope>.+?) (?:offer|provide)$',
    r'^(?:list|show|give)(?: me)? (?:the )?(?:available |offered )?(?P<subject>.+)$',
    r'^(?:ano|anong|alin|aling) (?:(?:ang|mga) )*(?P<subject>.+?) (?:(?:ang|ay|na) )?(?:inaalok|offered|available)(?: (?P<scope>.+))?$',
    r'^(?:ano|anong) (?:(?:ang|mga) )*(?:available|inaalok)(?: na)? (?P<subject>.+)$',
))
LISTING_CONSTRAINT = re.compile(
    r'\b(?:not|no|never|without|except|unless|only|excluding|instead|versus|vs|compare|'
    r'hindi|wala|maliban|huwag|or|either|all|lahat|every|complete|full|current|latest|'
    r'currently|now|today|ngayon|kasalukuyan)\b')


def listing_signature(question):
    """Recognize equivalent list requests, not arbitrary bag-of-words matches.

    Subject/scope terms must be equal, never a subset. Only grammatical frames
    and the existing shared lexical aliases are normalized. Qualified, dated,
    negative, comparison and multi-question requests retain ordinary retrieval.
    Multi-question source labels do not establish a single unambiguous scope.
    """
    from .grounding import terms
    if not isinstance(question, str) or len(question) > 500:
        return None
    if len([part for part in question.split('?') if part.strip()]) > 1:
        return None
    text = normalized_text(re.sub(r'^\s*\[[^\]\n]+\]\s*', '', question))
    text = re.sub(r'^please ', '', text)
    if re.search(r'\d', text) or LISTING_CONSTRAINT.search(text):
        return None
    for pattern in LISTING_PATTERNS:
        match = pattern.fullmatch(text)
        if match:
            subject = match.group('subject')
            scope = match.groupdict().get('scope') or ''
            content = frozenset(terms(subject + ' ' + scope))
            return ('listing', content) if content else None
    return None
