"""Bounded whole-utterance social matching; never rewrites a factual request.

Canonical phrases and abbreviations are maintained, not every spelling error.
Single-word fuzzy recognition retains conservative stem checks. Whole configured
phrases allow at most two edits and require one supported intent. Repeated runs
are collapsed in this social view only, never in the factual matching query.
"""
from .conversation_config import conversation_config
from dataclasses import dataclass
import re
from .spelling import edit_distance as _distance, social_variants, literal_fragments, vocabulary
from .performance import timed
from .query_normalization import normalize_input


FORMS = conversation_config()['social']['forms']
ABBREVIATIONS = conversation_config()['social']['abbreviations']
SUFFIX = re.compile(conversation_config()['social']['suffix_pattern'])
EXACT = {phrase.replace(' ', ''): kind for kind, forms in FORMS.items() for phrase in forms}
TARGETS = tuple((phrase.replace(' ', ''), kind, len(phrase.split())) for kind, forms in FORMS.items() for phrase in forms)


@dataclass(frozen=True)
class SocialMatch:
    kind: str
    method: str
    score: float | None = None
    reply_language: str | None = None


@timed('social_normalization')
def _match_social(message):
    if not isinstance(message, str) or len(message) > 120:
        return None
    # Numbers, URLs, identifiers, and explicit controls never enter this path.
    if re.search(r'\d|https?://|[_/\\\[\]<>]', message, re.I):
        return None
    view = normalize_input(message)
    text = view.spaced
    language = 'ceb' if re.search(r'\b(?:daghang|kaayo)\b', text) else None
    without_suffix = SUFFIX.sub('', text)
    if without_suffix != text:
        view = normalize_input(without_suffix)
        text = view.spaced
    if text in ABBREVIATIONS:
        return SocialMatch(ABBREVIATIONS[text], 'abbreviation', reply_language=language)
    words = text.split()
    if not words or len(words) > 5:
        return None
    compact = view.squashed
    if compact in EXACT:
        if compact.startswith('daghang') or compact.endswith('kaayo'):
            language = 'ceb'
        return SocialMatch(EXACT[compact], 'normalized_social', reply_language=language)
    if not compact.isascii() or not compact.isalpha() or not 4 <= len(compact) <= 24:
        return None
    candidates = []
    for target, kind, word_count in TARGETS:
        # Fused phrases or matching word counts only: an extra clause is not a typo.
        if len(words) not in (1, word_count) or abs(len(compact) - len(target)) > 1:
            continue
        if compact[:2] != target[:2] or _distance(compact, target) != 1:
            continue
        # Same-length substitutions must retain a longer lexical stem. This
        # rejects valid lookalikes such as "thinks", "thunks", "shanks", "tanks".
        if len(compact) == len(target):
            transposed = any(compact == target[:i] + target[i+1] + target[i] + target[i+2:] for i in range(len(target)-1))
            if not transposed and compact[:4] != target[:4]:
                continue
        score = 1 - 1 / max(len(compact), len(target))
        if score >= .80:
            candidates.append((score, kind))
    if not candidates or len({kind for _, kind in candidates}) != 1:
        return None
    return SocialMatch(candidates[0][1], 'social_typo', max(score for score, _ in candidates), language)


def _local_phrases():
    config = conversation_config()
    phrases = [(normalize_input(text).spaced, kind) for kind, texts in config['social']['forms'].items() for text in texts]
    from .chat_language import expand_shorthand
    phrases += [(normalize_input(expand_shorthand(text)).spaced,kind) for kind,texts in config['semantic']['exemplars'].items()
                if kind!='knowledge' for text in texts]
    for kind, pattern in config['social']['fast_patterns'].items():
        full = re.compile(r'^(?:'+pattern+r')[!.?,\s]*$', re.I)
        phrases.extend((normalize_input(text).spaced,kind) for text in literal_fragments(pattern) if full.fullmatch(text))
    return tuple(dict.fromkeys(phrases))


LOCAL_PHRASES = _local_phrases()
LOCAL_EXACT = {}
for _phrase,_kind in LOCAL_PHRASES:
    LOCAL_EXACT.setdefault(_phrase,set()).add(_kind)


@timed('social_matching')
def match_social(message):
    """Whole social/self utterances only; intent consensus never rewrites tokens."""
    if not isinstance(message,str) or len(message)>120 or re.search(r'\d|https?://|[_/\\\[\]<>]',message,re.I):
        return None
    from .chat_language import social_core
    core,modifier_language=social_core(message)
    for variant in (*social_variants(message),*social_variants(core)):
        exact = _match_social(variant)
        if exact:
            if modifier_language:
                from dataclasses import replace
                return replace(exact,reply_language=modifier_language)
            return exact
        from .dialogue import FAST_PATTERNS, KNOWLEDGE
        social_text = normalize_input(variant).punctuated
        local = next((kind for kind,pattern in FAST_PATTERNS.items() if pattern.fullmatch(social_text)),None)
        if local:
            return SocialMatch(local,'normalized_local',reply_language=modifier_language)
        kinds=LOCAL_EXACT.get(normalize_input(variant).spaced,())
        if len(kinds)==1:
            return SocialMatch(next(iter(kinds)),'configured_exemplar')
    view = normalize_input(message)
    text, compact = view.spaced, view.squashed
    from .dialogue import KNOWLEDGE
    if KNOWLEDGE.search(text):
        return None
    # Abbreviation ambiguity can agree on an intent (e.g. two gratitude
    # aliases). No ambiguous spelling candidate is selected or substituted.
    abbreviations = conversation_config()['social']['abbreviations']
    if compact.isascii() and compact.isalpha() and 4<=len(compact)<=5 and ' ' not in text:
        scored = [(_distance(compact,alias),kind) for alias,kind in abbreviations.items()]
        distance = min((score for score,_ in scored),default=99)
        kinds = {kind for score,kind in scored if score==distance}
        if distance==1 and len(kinds)==1 and any(compact[:2]==alias[:2] for alias in abbreviations if _distance(compact,alias)==distance):
            return SocialMatch(kinds.pop(),'abbreviation_consensus',1-distance/max(len(compact),4))
    if not compact.isascii() or not compact.isalpha() or not 8<=len(compact)<=80:
        return None
    candidates=[]
    for phrase,kind in LOCAL_PHRASES:
        target=phrase.replace(' ','')
        if abs(len(compact)-len(target))>2 or compact[:2]!=target[:2]:
            continue
        distance=_distance(compact,target)
        score=1-distance/max(len(compact),len(target))
        if distance<=2 and score>=.82:
            # A known content word cannot be removed/changed just because a
            # complete self phrase is nearby. Only OOV/short grammatical slots.
            extras=set(text.split())-set(phrase.split())
            if distance and (any(word in vocabulary().words and len(word)>2 for word in extras) or len(text.split())>len(phrase.split())):
                continue
            candidates.append((distance,score,kind))
    if not candidates:
        return None
    best=min(distance for distance,_,_ in candidates)
    kinds={kind for distance,_,kind in candidates if distance==best}
    if len(kinds)!=1:
        return None
    return SocialMatch(kinds.pop(),'local_phrase',max(score for distance,score,_ in candidates if distance==best))
