"""Per-request conversation resolution. History describes intent, never facts.

The core operates on interchangeable entity groups, grammatical substitutions,
and validated edit plans. It has no dependency on a particular knowledge model
or university topic. A caller can supply additional public entity groups.
"""
from dataclasses import dataclass
import json
import re
import time
from .query_normalization import roles_in
from .performance import timed
from .compound_queries import INSTITUTION_REFERENCE, compatible_reference

MAX_MESSAGES = 8
MAX_USER_CHARS = 2000
MAX_ASSISTANT_CHARS = 3000
CONTEXT_TTL = 900
SMALLTALK = re.compile(r'^(?:hi|hello|hey|thanks|thank you|salamat|ok|okay|got it|sige|understood)[!. ]*$', re.I)
FOLLOW = re.compile(r'^(?:how about|what about|and(?: for)?|also(?: for)?|paano naman(?: ang| sa)?|'
                    r'ano naman(?: ang| sa)?|sa|para sa|kumusta naman|at sa)\s+(.+?)[?.!]*$', re.I)
PRONOUN = re.compile(r'\b(' + INSTITUTION_REFERENCE + r'|it|its|they|their|them|that|those|this|there|ito|iyan|iyon|nito|niyan|nila|doon)\b', re.I)
QUESTION = re.compile(r'^(?:who|what|where|when|why|how|does|do|is|are|can|which|sino|ano|saan|nasaan|kailan|paano)\b', re.I)
FILLERS = re.compile(r'\b(?:please|po|naman|ang|sa|the|a|an)\b', re.I)
ATTRIBUTE_CONTEXT_INTRO = r'(?:how about|what about|ano(?: naman)?(?: ang)?|paano naman(?: ang)?)'
ATTRIBUTE = re.compile(r'^(?:what(?: are| is)?|' + ATTRIBUTE_CONTEXT_INTRO + r')\s+'
                       r'(?:the |its |their |mga )?(?:requirements?|documents?|fees?|cost|office hours|hours|schedule|deadline|'
                       r'eligibility|qualifications?|contact|location|policy|policies|process|procedure|steps?)\b', re.I)


@dataclass(frozen=True)
class Entity:
    group: str
    key: str
    label: str
    aliases: tuple


class Vocabulary:
    def __init__(self, entities=()):
        self.entities = tuple(entities)
        self.patterns = [(entity, re.compile(r'(?<!\w)(?:' + '|'.join(
            re.escape(alias) for alias in sorted(set(entity.aliases), key=len, reverse=True) if alias) + r')(?!\w)', re.I))
            for entity in self.entities if entity.aliases]

    def mentions(self, text):
        matches = [(match.start(), match.end(), entity) for entity, pattern in self.patterns for match in pattern.finditer(text)]
        accepted = []
        for start, end, entity in sorted(matches, key=lambda row: -(row[1] - row[0])):
            if not any(start < b and end > a for a, b, _ in accepted):
                accepted.append((start, end, entity))
        return sorted(accepted, key=lambda row: row[0])


def builtin_vocabulary():
    # Existing directory/intent definitions are adapters, not resolver branches.
    from .grounding import DEPARTMENTS
    from .intents import DESTINATIONS, CATEGORY_LABELS
    entities = [Entity('college', key, key.upper(), tuple(aliases)) for key, aliases in DEPARTMENTS.items() if key != 'pbmo']
    entities += [Entity('office', key, label, tuple(aliases) + (label,)) for key, (label, aliases) in DESTINATIONS.items()
                 if key not in DEPARTMENTS]
    audience_aliases = {
        'freshmen': ('incoming college freshman', 'incoming freshmen', 'freshmen', 'freshman', 'first year students'),
        'transferee': ('transferee college students', 'transferee students', 'transferee student', 'transferees', 'transferee'),
        'continuing': ('old continuing college students', 'old/continuing college student', 'old or continuing college student',
                       'continuing college students', 'old college students', 'old college student', 'old students', 'old student',
                       'continuing students', 'continuing student'),
    }
    entities += [Entity('audience', key, label, audience_aliases.get(key, (label,))) for key, label in CATEGORY_LABELS.items()]
    entities.append(Entity('office', 'pbmo', 'PBMO', ('pbmo', 'Publication Brand and Marketing Office')))
    from .query_normalization import ROLE_WORDS
    entities.extend(Entity('role',role,role, (role,)) for role in ROLE_WORDS)
    entities.append(Entity('role','vp','vp',('vice president','bise presidente','bise pangulo')))
    return Vocabulary(entities)


def bounded_history(value, now=None):
    """Accept complete role pairs only, bound memory, and reject stale context.

    Assistant text can establish a known clarification marker, not an answer.
    Long assistant excerpts may be shortened; user constraints are never cut.
    """
    if not isinstance(value, list) or not 2 <= len(value) <= MAX_MESSAGES or len(value) % 2:
        return []
    now = time.time() if now is None else now
    rows = []
    for index, row in enumerate(value):
        if not isinstance(row, dict) or row.get('role') != ('user' if index % 2 == 0 else 'assistant'):
            return []
        content = row.get('content')
        if not isinstance(content, str) or (index % 2 == 0 and len(content) > MAX_USER_CHARS):
            return []
        timestamp = row.get('timestamp')
        if timestamp is not None:
            if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool) or not timestamp <= now + 60:
                return []
            if timestamp < now - CONTEXT_TTL:
                # Forget the stale prefix, while allowing newer complete pairs
                # to form a fresh topic after an idle period.
                rows = []
                continue
        rows.append({'role': row['role'], 'content': content[:MAX_ASSISTANT_CHARS] if index % 2 else content})
    return rows if len(rows) % 2 == 0 and (not rows or rows[0]['role'] == 'user') else []


@dataclass
class Resolution:
    queries: tuple = ()
    relation: str = 'standalone'
    clarification: str = ''
    reference: int | None = None
    previous: str = ''
    entity: str = ''
    language: str = 'en'
    provider_used: bool = False
    blocked: bool = False


def language(text):
    return 'fil' if re.search(r'\b(paano|naman|saan|nasaan|ano|sino|ang|mga|po|ito|iyon|nito|nila|doon|para sa|guro|kamusta|kumusta)\b', text, re.I) else 'en'


def clarification(text):
    return ('Aling paksa o detalye ang tinutukoy mo? Pakibanggit ang opisina, programa, o tanong.'
            if language(text) == 'fil' else
            'Which topic or detail do you mean? Please specify the office, program, or question.')


def _clean_fragment(text):
    return FILLERS.sub('', text).strip(' ?!.')


def _swap(previous, fragment, vocabulary):
    fresh = vocabulary.mentions(fragment)
    old = vocabulary.mentions(previous)
    if not fresh:
        # Any future named concept can use quoted or "for/of/about X" slots.
        quoted = re.findall(r'["“]([^"”]+)["”]', previous)
        if len(quoted) == 1:
            return previous.replace(quoted[0], fragment.strip('"“”')), fragment
        suffix = re.search(r'\b(for|about|of)\s+([^?()]+?)\s*[?.!]?$', previous, re.I)
        if suffix and not re.search(r'\d|\b(not|without|except|hindi)\b', suffix.group(2), re.I) and len(fragment.split()) <= 8 and not QUESTION.match(fragment):
            return previous[:suffix.start(2)] + fragment.strip(' ?!.') + '?', fragment
        subject = _subject(previous, vocabulary)
        if subject and previous.count(subject) == 1 and not re.search(r'\d|\b(not|without|except|hindi)\b', subject, re.I):
            return previous.replace(subject, fragment), fragment
        return None
    groups = {entity.group for _, _, entity in fresh}
    if len(groups) != 1 or len({entity.key for _, _, entity in fresh}) != 1:
        return None
    target = fresh[0][2]
    replacements = [(a, b) for a, b, entity in old if entity.group == target.group]
    if not replacements or len({entity.key for _, _, entity in old if entity.group == target.group}) != 1:
        return None
    # Every substantive fragment token must be represented; don't discard
    # "without credentials", a year, or an additional requirement.
    remainder = fragment
    for a, b, _ in reversed(fresh):
        remainder = remainder[:a] + remainder[b:]
    if target.group!='role' and _clean_fragment(remainder):
        return None
    replacement=_clean_fragment(fragment) if target.group=='role' else target.label
    rewritten = previous
    for a, b in reversed(replacements):
        rewritten = rewritten[:a] + replacement + rewritten[b:]
    return rewritten, replacement


def _subject(previous, vocabulary):
    # Reusable grammatical object extraction, independent of topic names.
    match = re.search(r'\b(?:for|about|of)\s+(.+?)[?.!]*$', previous, re.I)
    if match:
        return match.group(1).rstrip(' ?!.')
    from .compound_queries import topic_subject
    topic = topic_subject(previous)
    if topic:
        return topic
    mentions = vocabulary.mentions(previous)
    if mentions:
        # Multiple entities of different kinds can be meaningful together.
        return ' '.join(dict.fromkeys(entity.label for _, _, entity in mentions))
    match = re.match(r'^(?:what is|what are|tell me about|explain|ano ang)\s+(?:the )?(.+?)[?.!]*$', previous, re.I)
    return match.group(1).rstrip(' ?!.') if match else ''


def _attribute_query(text, previous, vocabulary):
    subject = _subject(previous, vocabulary)
    if not subject:
        return None
    if re.search(r'\b' + INSTITUTION_REFERENCE + r'\b', text, re.I):
        return PRONOUN.sub(subject, text) if compatible_reference(text, subject, vocabulary) else None
    # Retain the user's complete attribute request; translate only structural
    # question words, never university facts. Dates/conditions stay attached.
    value = re.sub(r'^' + ATTRIBUTE_CONTEXT_INTRO + r'\s+', 'What are ', text, flags=re.I)
    value = re.sub(r'\b(?:its|their|it|them|nito|nila)\b', 'the', value, flags=re.I).rstrip(' ?!.')
    years = re.findall(r'\b20\d{2}\b', previous)
    tail = ''.join(' in ' + year for year in years if year not in value and year not in subject)
    return value + ' for ' + subject + tail + '?'


@timed('context_resolution')
def resolve_turn(text, previous='', vocabulary=None):
    from .compound_queries import decompose_query
    vocabulary = vocabulary or builtin_vocabulary()
    locale = language(text)
    base = dict(previous=previous, language=locale)
    # A predicate repeated about an explicit previous subject can reuse that
    # subject, without filling facts from a previous assistant answer.
    repeat=re.fullmatch(r'(?:who is|sino ang)\s+(?:currently |now |ngayon )?(?:holding|in|may hawak ng)\s+(?:that|the same|that same|ng parehong)\s+(?:role|position)[?.! ]*',text,re.I)
    if repeat:
        unique_previous = previous and len(decompose_query(previous, vocabulary).queries) == 1
        return Resolution((previous,), 'reference', **base) if unique_previous else Resolution(clarification=clarification(text), **base)
    comparison = re.match(r'^(?:compare (?:it|that|them)|ihambing (?:ito|iyan))\s+(?:with|to|sa)\s+(.+?)[?.!]*$', text, re.I)
    if comparison:
        unique_previous = previous and len(decompose_query(previous, vocabulary).queries) == 1
        swapped = _swap(previous, comparison.group(1).strip(' ?!.'), vocabulary) if unique_previous else None
        return (Resolution((previous, swapped[0]), 'comparison', entity=swapped[1], **base) if swapped else
                Resolution(clarification=clarification(text), **base))
    if re.search(r'\b(compare|versus|vs|ihambing)\b', text, re.I):
        mentions = vocabulary.mentions(text)
        if len(mentions) == 2 and mentions[0][2].group == mentions[1][2].group:
            a, b, first = mentions[0]
            c, d, second = mentions[1]
            connector = text[b:c]
            if re.fullmatch(r'\s*(?:and|versus|vs\.?|at)\s*', connector, re.I):
                template = text[:a] + '{entity}' + text[d:]
                identity = bool(roles_in(text))
                template = re.sub(r'^(?:compare|ihambing)\s+', 'Who are ' if identity else 'What are ', template, flags=re.I)
                if identity:
                    template = template.rstrip(' ?!.') + '?'
                return Resolution((template.format(entity=first.label), template.format(entity=second.label)), 'comparison', **base)
        # A role plus college creates more than two entity spans. Reuse the
        # coordination parser rather than requiring exactly two raw mentions.
        explicit = re.match(r'^(?:compare|ihambing)\s+(.+)$', text, re.I)
        if explicit:
            from .compound_queries import decompose_query
            prefix = 'Who are ' if roles_in(explicit.group(1)) else 'What are '
            compared = decompose_query(prefix + explicit.group(1), vocabulary)
            if compared.clarification:
                return Resolution(clarification=compared.clarification, blocked=True, **base)
            if len(compared.queries) > 1:
                return Resolution(compared.queries, 'comparison', **base)
    reference = re.search(r'\b(?:step|item|number|hakbang)\s*(\d{1,2})\b', text, re.I)
    if reference and re.search(r'\b(explain|elaborate|clarify|repeat|detail|ipaliwanag|paliwanag|ulit)\b', text, re.I):
        unique_previous = previous and len(decompose_query(previous, vocabulary).queries) == 1
        return Resolution((previous,), 'reference', reference=int(reference.group(1)), **base) if unique_previous else Resolution(clarification=clarification(text), **base)
    from .compound_queries import MAX_PARTS, bind_dependent, decompose_query, dependent_request
    plan = decompose_query(text, vocabulary)
    if plan.clarification:
        return Resolution(clarification=plan.clarification, blocked=True, **base)
    if plan.reason == 'collapsed':
        return resolve_turn(plan.queries[0], previous, vocabulary)
    if len(plan.queries) > 1:
        queries = []
        prior = previous
        for part in plan.queries:
            antecedent = '; '.join(queries) if len(queries) > 1 and (PRONOUN.search(part) or dependent_request(part)) else prior
            if not (len(queries) > 1 and dependent_request(part)):
                part = bind_dependent(part, antecedent, vocabulary)
            result = resolve_turn(part, antecedent, vocabulary)
            # Keep an unresolved part as a question; orchestration will ask
            # about that part without discarding independently supported ones.
            queries.extend(result.queries or (part,))
            prior = result.queries[0] if len(result.queries) == 1 else ''
        queries = tuple(dict.fromkeys(queries))
        if len(queries) > MAX_PARTS:
            return Resolution(clarification=f'Please ask at most {MAX_PARTS} parts at a time.', blocked=True, **base)
        return Resolution(queries, 'compound', **base)
    # A prior multi-part turn does not establish a unique singular referent.
    # Explicit entity follow-ups may select the one compatible prior slot.
    prior_plan = decompose_query(previous, vocabulary) if previous else None
    if dependent_request(text):
        bound = bind_dependent(text, previous, vocabulary) if not prior_plan or len(prior_plan.queries) == 1 else text
        return (Resolution((bound,), 'followup', **base) if bound != text else
                Resolution(clarification=clarification(text), **base))
    if prior_plan and len(prior_plan.queries) > 1 and (FOLLOW.match(text) or PRONOUN.search(text) or ATTRIBUTE.match(text)):
        if PRONOUN.search(text) and not vocabulary.mentions(text):
            if ATTRIBUTE.match(text) and re.search(r'\b(their|them|nila)\b', text, re.I):
                results = [resolve_turn(text, query, vocabulary) for query in prior_plan.queries]
                if all(len(result.queries) == 1 for result in results):
                    return Resolution(tuple(dict.fromkeys(result.queries[0] for result in results)), 'compound', **base)
            return Resolution(clarification=clarification(text), **base)
        candidates = [resolve_turn(text, query, vocabulary) for query in prior_plan.queries]
        unique = tuple(dict.fromkeys(query for result in candidates for query in result.queries
                                     if result.relation != 'standalone'))
        return (Resolution(unique, 'followup', **base) if len(unique) == 1 else
                Resolution(clarification=clarification(text), **base))
    follow = FOLLOW.match(text.strip())
    # An explicit full new question wins over history, including navigation.
    if not follow and not PRONOUN.search(text) and not ATTRIBUTE.match(text):
        return Resolution((text,), **base)
    if not previous:
        if not follow and not PRONOUN.search(text) and QUESTION.match(text):
            return Resolution((text,), **base)
        return Resolution(clarification=clarification(text), **base)
    fragment = follow.group(1).strip(' ?!.') if follow else ''
    fragment = re.sub(r'\s+naman$', '', fragment, flags=re.I)
    if follow and PRONOUN.fullmatch(fragment):
        return Resolution(clarification=clarification(text), **base)
    if not follow and not PRONOUN.search(text) and (vocabulary.mentions(text) or re.search(r'\b(for|about|of|at)\s+\w+', text, re.I)):
        return Resolution((text,), **base)
    if ATTRIBUTE.match(text) and (not follow or not vocabulary.mentions(fragment)):
        query = _attribute_query(text, previous, vocabulary)
        if query:
            return Resolution((query,), 'attribute', **base)
    if follow:
        swapped = _swap(previous, fragment, vocabulary)
        if swapped:
            return Resolution((swapped[0],), 'followup', entity=swapped[1], **base)
    # Explicitly named offices/colleges in a complete attribute question are a
    # topic switch, not permission to append the old topic.
    if not follow and vocabulary.mentions(text):
        return Resolution((text,), **base)
    if ATTRIBUTE.match(text):
        query = _attribute_query(text, previous, vocabulary)
        if query:
            return Resolution((query,), 'attribute', **base)
    if PRONOUN.search(text):
        subject = _subject(previous, vocabulary)
        # A multi-entity answer is not a unique physical destination/referent.
        unique = {(entity.group, entity.key) for _, _, entity in vocabulary.mentions(previous)}
        groups = {group for group, _ in unique}
        qualified_role = ('role' in groups and all(sum(g == group for g, _ in unique) == 1 for group in groups))
        if subject and (len(unique) <= 1 or qualified_role) and compatible_reference(text, subject, vocabulary):
            rewritten = PRONOUN.sub(subject, text)
            return Resolution((rewritten,), 'reference', **base)
    return Resolution(clarification=clarification(text), **base)


def dialogue_history(history):
    """Social interludes never replace a task or pending clarification."""
    from .dialogue import route_turn
    from .query_understanding import incomplete_request, REPHRASE_EN, REPHRASE_FIL
    from .response_style import strip_intro
    rows = bounded_history(history)
    result = []
    for index in range(0, len(rows), 2):
        route = route_turn(rows[index]['content'])
        if route.kind != 'knowledge':
            continue
        if (incomplete_request(route.query) and
                strip_intro(rows[index + 1]['content']).startswith((REPHRASE_EN, REPHRASE_FIL))):
            continue
        result.extend([{**rows[index], 'content': route.query or rows[index]['content']}, rows[index + 1]])
    return result


def conversation_anchor(history=None, vocabulary=None, *, filtered=False):
    from .intents import enrollment_resolution, enrollment_request, enrollment_category, normalize_query
    history = history if filtered else dialogue_history(history)
    previous = ''
    for index in range(0, len(history), 2):
        user = normalize_query(history[index]['content'])
        if SMALLTALK.fullmatch(user):
            continue
        pending, legacy = enrollment_resolution(user, history[:index])
        if legacy != user:
            previous = user if enrollment_request(user) and enrollment_category(user) else legacy
            continue
        result = resolve_turn(user, previous, vocabulary)
        if len(result.queries) > 1:
            previous = '; '.join(result.queries) if result.relation == 'compound' else ''
        elif result.queries and not pending:
            previous = result.queries[-1]
        elif result.relation == 'standalone':
            previous = user
    return previous


def resolve_conversation(text, history=None, vocabulary=None):
    return resolve_turn(text, conversation_anchor(history, vocabulary), vocabulary)


def validated_edit(payload, current, previous):
    """Optional provider outputs an edit, never a factual answer or whole essay.

    Both sides of the replacement must be exact spans of user requests. No
    deleted dates/numbers, added institutions, invented entities or new facts.
    """
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or set(data) != {'anchor', 'replacement'}:
        return None
    anchor, replacement = data['anchor'], data['replacement']
    if not isinstance(anchor, str) or not isinstance(replacement, str) or not anchor or not replacement:
        return None
    if len(anchor) > 150 or len(replacement) > 150 or previous.count(anchor) != 1 or replacement not in current:
        return None
    if re.search(r'\d|\b(not|without|except|hindi)\b', anchor, re.I):
        return None
    # Reject plans that erase negation or numeric constraints in the follow-up.
    residual = current.replace(replacement, '')
    if re.search(r'\d|\b(not|without|except|hindi)\b', residual, re.I):
        return None
    scaffold = set('how what about and also compare it that them with to for please paano naman ano ang sa para po'.split())
    if set(re.findall(r'\w+', residual.lower())) - scaffold:
        return None
    if re.search(r'\b(who|what|where|when|how|why|sino|ano|paano|for|without|except|in|at)\b', anchor, re.I):
        return None
    return previous.replace(anchor, replacement)
