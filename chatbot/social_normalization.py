"""Bounded whole-utterance social matching; never rewrites a factual request.

Canonical phrases and abbreviations are maintained, not every spelling error.
Only one confident edit is allowed, with a protected prefix and conservative
substitutions. Ambiguous short words and unknown content fail closed.
"""
from dataclasses import dataclass
import re
from .intents import _distance
from .performance import timed
from .query_normalization import normalized_text


FORMS = {
    'greeting': ('hello', 'good morning', 'good afternoon', 'good evening', 'kumusta', 'kamusta'),
    'wellbeing': ('how are you',),
    'thanks': ('thanks', 'thank you', 'thank you so much', 'salamat', 'maraming salamat',
               'daghang salamat', 'salamat kaayo', 'daghang salamat kaayo'),
    'farewell': ('goodbye', 'see you', 'see you later', 'good night', 'paalam'),
}
ABBREVIATIONS = {'ty': 'thanks', 'thx': 'thanks', 'tnx': 'thanks', 'tq': 'thanks', 'tysm': 'thanks'}
SUFFIX = re.compile(r'(?:\s+(?:paula|po|naman|kaayo))+$')
EXACT = {phrase.replace(' ', ''): kind for kind, forms in FORMS.items() for phrase in forms}
TARGETS = tuple((phrase.replace(' ', ''), kind, len(phrase.split())) for kind, forms in FORMS.items() for phrase in forms)


@dataclass(frozen=True)
class SocialMatch:
    kind: str
    method: str
    score: float | None = None
    reply_language: str | None = None


@timed('social_normalization')
def match_social(message):
    if not isinstance(message, str) or len(message) > 120:
        return None
    # Numbers, URLs, identifiers, and explicit controls never enter this path.
    if re.search(r'\d|https?://|[_/\\\[\]<>]', message, re.I):
        return None
    text = normalized_text(message)
    language = 'ceb' if re.search(r'\b(?:daghang|kaayo)\b', text) else None
    text = SUFFIX.sub('', text)
    if text in ABBREVIATIONS:
        return SocialMatch(ABBREVIATIONS[text], 'abbreviation', reply_language=language)
    words = text.split()
    if not words or len(words) > 5:
        return None
    compact = ''.join(words)
    if compact in EXACT:
        if compact.startswith('daghang') or compact.endswith('kaayo'):
            language = 'ceb'
        return SocialMatch(EXACT[compact], 'normalized_social', reply_language=language)
    if not compact.isascii() or not compact.isalpha() or not 5 <= len(compact) <= 24:
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
        if score >= .82:
            candidates.append((score, kind))
    if not candidates or len({kind for _, kind in candidates}) != 1:
        return None
    return SocialMatch(candidates[0][1], 'social_typo', max(score for score, _ in candidates), language)
