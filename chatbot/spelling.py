"""Bounded spelling plans for matching only. No user-text cache or data writes.

The public vocabulary is immutable per worker and refreshed on worker restart.
Only OOV words with a unique nearest ordinary word are eligible. Names and
acronyms are evidence identifiers, never spelling-correction targets.
"""
from dataclasses import dataclass
from functools import lru_cache
import re
from threading import Lock
from types import MappingProxyType

from .conversation_config import conversation_config
from .performance import timed
from .query_normalization import normalize_input, person_key

WORD = re.compile(r"\b[^\W\d_]+\b", re.UNICODE)


def edit_distance(left, right):
    """Optimal-string-alignment distance, including adjacent transpositions."""
    rows = [list(range(len(right) + 1))]
    for i, a in enumerate(left, 1):
        row = [i]
        for j, b in enumerate(right, 1):
            value = min(row[-1]+1, rows[-1][j]+1, rows[-1][j-1]+(a != b))
            if i > 1 and j > 1 and a == right[j-2] and left[i-2] == b:
                value = min(value, rows[i-2][j-2]+1)
            row.append(value)
        rows.append(row)
    return rows[-1][-1]


def literal_fragments(pattern):
    """Read literal vocabulary from existing regexes, without expanding regexes."""
    # Regex stems (e.g. a noun prefix followed by \w*) are not vocabulary
    # words. Admitting them would turn a valid complete word into a stem.
    plain = re.sub(r'[A-Za-z]+\\w[+*?]?', ' ', pattern)
    plain = re.sub(r'\\(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|[sSwWbdD])', ' ', plain)
    return re.findall(r"[^\W\d_]+(?:[ '\u2019][^\W\d_]+)*", plain, re.UNICODE)


@dataclass(frozen=True)
class Lexicon:
    words: frozenset
    names: frozenset
    acronyms: frozenset
    by_length: object
    deletions: object
    social_words: frozenset = frozenset()
    source_counts: tuple = ()
    name_collisions: frozenset = frozenset()
    name_deletions: object = None


def build_lexicon(texts=(), names=(), acronyms=(), *, source_counts=()):
    """Pure constructor also used by isolated tests; never read chat/user tables."""
    config = conversation_config()
    public = [text for examples in config['semantic']['exemplars'].values() for text in examples]
    public += [text for forms in config['social']['forms'].values() for text in forms]
    public += list(config['social']['abbreviations'])
    public += [text for pattern in config['social']['fast_patterns'].values() for text in literal_fragments(pattern)]
    social_words = frozenset(word for text in public for word in normalize_input(text).spaced.split())
    # Existing valid-word guards and navigation aliases are vocabulary, not a
    # list of misspellings. Retain their previous compatibility guarantees.
    from .intents import VOCABULARY, PROTECTED_WORDS, DESTINATIONS
    public += list(VOCABULARY | PROTECTED_WORDS)
    public += [alias for _, aliases in DESTINATIONS.values() for alias in aliases]
    # Existing local grammar/gate words are known, valid tokens too. In
    # particular, a short factual noun must not become a social verb.
    from .grounding import STOPWORDS, SYNONYMS
    from . import dialogue
    from .query_understanding import LISTING_PATTERNS, LISTING_CONSTRAINT
    public += list(STOPWORDS | set(SYNONYMS) | set(SYNONYMS.values()))
    public += [fragment for pattern in (dialogue.KNOWLEDGE,dialogue.EMOTION,dialogue.SELF_SOCIAL)
               for fragment in literal_fragments(pattern.pattern)]
    public += [fragment for pattern in (*LISTING_PATTERNS,LISTING_CONSTRAINT) for fragment in literal_fragments(pattern.pattern)]
    public += list(texts)
    name_keys = frozenset(person_key(name) for name in names if person_key(name))
    protected_names = frozenset(word for name in name_keys for word in name.split())
    name_signatures, collisions = {}, set()
    for name in sorted(name_keys):
        variants = {name} | {name[:i]+name[i+1:] for i in range(len(name))}
        others = {other for variant in variants for other in name_signatures.get(variant,())}
        others |= {name[:i]+name[i+1]+name[i]+name[i+2:] for i in range(len(name)-1)} & name_keys
        for other in others:
            if other!=name and edit_distance(name,other)<=1:
                collisions.update((name,other))
        for variant in variants:
            name_signatures.setdefault(variant,set()).add(name)
    protected_acronyms = frozenset([word.casefold() for word in acronyms] +
        [word.casefold() for text in public for word in re.findall(r'\b[A-Z]{2,}\b', text)])
    words = frozenset(word for text in public for word in normalize_input(text).spaced.split()) | protected_names | protected_acronyms
    # Ordinary inflections already supported by the old normalizer stay valid.
    words |= frozenset(word+'s' for word in VOCABULARY if not word.endswith('s'))
    lengths, deletions = {}, {}
    name_deletions = {}
    for name in protected_names:
        for variant in {name} | {name[:i]+name[i+1:] for i in range(len(name))}:
            name_deletions.setdefault(variant,set()).add(name)
    for word in sorted(words - protected_names - protected_acronyms - PROTECTED_WORDS):
        if not word.isalpha() or not 3 <= len(word) <= 32:
            continue
        lengths.setdefault(len(word), []).append(word)
        for i in range(len(word)):
            deletions.setdefault(word[:i]+word[i+1:], set()).add(word)
    return Lexicon(words, protected_names, protected_acronyms,
                   MappingProxyType({key:tuple(value) for key,value in lengths.items()}),
                   MappingProxyType({key:tuple(sorted(value)) for key,value in deletions.items()}), social_words, tuple(source_counts),frozenset(collisions),
                   MappingProxyType({key:tuple(sorted(value)) for key,value in name_deletions.items()}))


@lru_cache(maxsize=1)
def config_lexicon():
    return build_lexicon()


_public_lexicon = None
_lock = Lock()


def prepare_vocabulary():
    """Called once before worker readiness. Failure leaves the worker unready."""
    global _public_lexicon
    with _lock:
        if _public_lexicon is not None:
            return _public_lexicon
        from .models import FAQ, StaffMember, Location, WebResource
        from .personnel import structured_person
        questions = list(FAQ.objects.order_by('pk').values_list('question', flat=True))
        staff = list(StaffMember.objects.order_by('pk').values_list('name', 'position', 'office'))
        locations = list(Location.objects.order_by('pk').values_list('name', flat=True))
        people = [person for obj in WebResource.objects.filter(category='Website personnel').only('content')
                  for person in [structured_person(obj)] if person]
        names = [row[0] for row in staff] + [row['name'] for row in people]
        texts = questions + locations + [text for row in staff for text in row if text]
        texts += [row['role'] for row in people]
        _public_lexicon = build_lexicon(texts, names,
            source_counts=(('faq',len(questions)), ('staff',len(staff)), ('location',len(locations)), ('website_people',len(people))))
        return _public_lexicon


def vocabulary():
    # Pure local utilities/tests work without a DB. Web workers always prepare
    # the complete snapshot before serving ready; no request-time DB scans.
    return _public_lexicon or config_lexicon()


@dataclass(frozen=True)
class Correction:
    original: str
    replacement: str
    distance: int
    confidence: float


@dataclass(frozen=True)
class SpellingPlan:
    original: str
    matching: str
    corrections: tuple = ()
    ambiguous: tuple = ()
    protected_name: bool = False

    @property
    def needs_confirmation(self):
        return bool(self.ambiguous) or (bool(self.corrections) and min(item.confidence for item in self.corrections) < .80)


def confirmation_questions(plan):
    """Offer choices without selecting an ambiguous replacement."""
    if plan.ambiguous:
        word = plan.ambiguous[0]
        _, candidates = nearest(word,vocabulary())
        return tuple(re.sub(r'\b'+re.escape(word)+r'\b',candidate,plan.matching,count=1,flags=re.I) for candidate in candidates[:3])
    return (plan.matching,)


def nearest(word, lexicon):
    """Unique best edit candidate. Two edits permitted only for long words."""
    maximum = 2 if len(word) >= 8 else 1
    candidates = set(lexicon.deletions.get(word, ()))
    variants = {word[:i]+word[i+1:] for i in range(len(word))} | {word}
    for variant in variants:
        if variant in lexicon.words and variant not in lexicon.names | lexicon.acronyms:
            candidates.add(variant)
        candidates.update(lexicon.deletions.get(variant, ()))
    # Adjacent transpositions are one edit, not two.
    for i in range(len(word)-1):
        swapped = word[:i]+word[i+1]+word[i]+word[i+2:]
        if swapped in lexicon.words and swapped not in lexicon.names | lexicon.acronyms:
            candidates.add(swapped)
    scored = [(edit_distance(word,candidate),candidate) for candidate in candidates]
    if maximum == 2 and not any(distance<=1 for distance,_ in scored):
        for length in range(len(word)-2, len(word)+3):
            candidates.update(lexicon.by_length.get(length, ()))
    candidates = {candidate for candidate in candidates if len(candidate)>=4 or
                  (len(word)==len(candidate) and any(word==candidate[:i]+candidate[i+1]+candidate[i]+candidate[i+2:]
                                                    for i in range(len(candidate)-1)))}
    scored = [(edit_distance(word,candidate),candidate) for candidate in candidates]
    best = min((distance for distance,_ in scored), default=99)
    return best, tuple(sorted(candidate for distance,candidate in scored if distance == best)) if best <= maximum else ()


def _segments(word, lexicon):
    # Missing spaces: accept a unique two-word split only; no arbitrary
    # multiword segmentation and no names/acronyms. Short fragments are unsafe.
    return tuple((word[:i],word[i:]) for i in range(2,len(word)-1)
                 if word[:i] in lexicon.words and word[i:] in lexicon.words and
                 not ({word[:i],word[i:]} & (lexicon.names | lexicon.acronyms)))


def person_lookup_request(text,lexicon):
    """Protection is scoped to a request for a person, never a nearby noun."""
    from .dialogue import local_self_intent
    if local_self_intent(text):
        return False
    if re.match(r'^(?:please\s+)?(?:who\s+is|who\s+are|sino\s+(?:si|ang)|(?:contact|email|phone)(?:\s+(?:of|for))?|(?:dean|head|director)\s+of)\b',text,re.I):
        return True
    if re.match(r'^(?:please\s+)?tell\s+me\s+about\b',text,re.I):
        # A named-person request can use this frame, but an institutional
        # policy/program request cannot acquire a person guard through it.
        from .dialogue import KNOWLEDGE
        return not KNOWLEDGE.search(text) and bool(set(normalize_input(text).spaced.split()) & lexicon.names)
    return False


@timed('spelling_matching')
def matching_plan(message, lexicon=None):
    lexicon = lexicon or vocabulary()
    original = message if isinstance(message,str) else ''
    # Preserve the original capitalization/punctuation in the matching view
    # unless replacing a token; existing uppercase acronym gates still apply.
    text = normalize_input(original).cased
    if len(text)>2000:
        return SpellingPlan(original,text)
    corrections, ambiguous = [], []
    name_risk = False
    person_lookup=person_lookup_request(text,lexicon)
    matches = list(WORD.finditer(text))
    replacements = []
    opaque = [(m.start(),m.end()) for m in re.finditer(r'https?://\S+|\b\S+@\S+\b|\b[\w.-]*\d[\w.-]*\b',text,re.I)]
    covered = set()
    for index,(left,right) in enumerate(zip(matches,matches[1:])):
        a,b=left.group().casefold(),right.group().casefold()
        joined=a+b
        if (index not in covered and text[left.end():right.start()].isspace() and
                not any(start<=left.start()<end or start<=right.start()<end for start,end in opaque) and
                a not in lexicon.words and b not in lexicon.words and joined in lexicon.words and
                len(joined)>=6 and joined not in lexicon.names|lexicon.acronyms and
                not left.group().isupper() and not right.group().isupper()):
            corrections.append(Correction(text[left.start():right.end()],joined,1,1-1/len(joined)))
            replacements.append((left.start(),right.end(),joined))
            covered.update((index,index+1))
    for index,match in enumerate(matches):
        if index in covered or any(start<=match.start()<end for start,end in opaque):
            continue
        raw, word = match.group(), match.group().casefold()
        if word in lexicon.words or len(word)<3 or len(word)>32 or not word.isascii():
            continue
        # Alphanumeric identifiers and uppercase unknown abbreviations are
        # opaque. Never reinterpret a typo inside a student/document code.
        if raw.isupper() or (match.start() and (text[match.start()-1].isdigit() or text[match.start()-1]=='_')) or (
                match.end()<len(text) and (text[match.end()].isdigit() or text[match.end()]=='_')):
            continue
        name_candidates={name for variant in {word}|{word[:i]+word[i+1:] for i in range(len(word))}
                         for name in lexicon.name_deletions.get(variant,())}
        name_candidates |= {word[:i]+word[i+1]+word[i]+word[i+2:] for i in range(len(word)-1)} & lexicon.names
        close_name = any(edit_distance(word,name)<=1 for name in name_candidates if len(name)>=3)
        if close_name:
            name_risk = person_lookup
            continue
        if raw[0].isupper() and match.start() and re.search(r'\b(?:who|sino|name)\b',text,re.I):
            # Unknown proper names cannot be inferred from their nearest noun.
            continue
        distance, candidates = nearest(word,lexicon)
        if len(candidates)>1:
            ambiguous.append(word)
            continue
        if candidates:
            target = candidates[0]
            if len(matches)==1 and target in lexicon.social_words and len(word)<=7:
                transposed = any(word==target[:i]+target[i+1]+target[i]+target[i+2:] for i in range(len(target)-1))
                if word[:2]!=target[:2] or (len(word)==len(target) and not transposed and word[:4]!=target[:4]):
                    continue
            score = 1-distance/max(len(word),len(target))
            if distance>1:
                score=min(score,.79)  # A two-edit factual repair always asks.
            if match.start()==0 and target in {'what','where','when','which','how','who','why'} and distance==1:
                score = max(score,.80)  # Unique leading grammatical repair.
            corrections.append(Correction(raw,target,distance,round(score,6)))
            replacements.append((match.start(),match.end(),target))
        else:
            splits = _segments(word,lexicon)
            if len(splits)==1:
                target = ' '.join(splits[0])
                corrections.append(Correction(raw,target,1,.78))
                replacements.append((match.start(),match.end(),target))
    for start,end,target in sorted(replacements,reverse=True):
        text = text[:start]+target+text[end:]
    from .personnel import name_request
    if person_lookup and name_request(text) in lexicon.name_collisions:
        name_risk=True
    return SpellingPlan(original,text,tuple(corrections),tuple(ambiguous),name_risk)


def social_variants(text):
    """Social-only repeated runs; never used for retrieval, facts or names."""
    yield text
    for width in (1,2):
        value = re.sub(r'([a-zA-Z])\1{1,}', lambda m:m.group(1)*width, text, flags=re.I)
        if value!=text and len(normalize_input(value).squashed)>=4:
            yield value
