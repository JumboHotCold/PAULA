"""Read-only, request-local follow-ups selected from public knowledge labels."""
from collections import defaultdict
import json
import logging
import re

from .grounding import terms, eligible_evidence
from .query_normalization import faq_question_key, roles_in
from .performance import stage

logger = logging.getLogger(__name__)
MAX_ASKED = 64
MAX_QUESTION_CHARS = 500
MARKER = re.compile(r'\[SUGGESTIONS:\s*(.*?)\]', re.S)
QUESTION_START = re.compile(r'^(?:what|why|how|who|where|when|which|does|do|is|are|can|ano|sino|saan|paano)\b', re.I)


def question_key(question):
    """Deduplicate lexical paraphrases, retaining topics, dates and qualifiers."""
    words = terms(question) - {'information', 'offered', 'details', 'detail', 'anong', 'mag'}
    key = faq_question_key(question)
    # Institutional names are intentionally stopwords in retrieval. All-empty
    # overview subjects refer to the same broad introduction, not a new topic.
    return ' '.join(sorted(words)) or ('institution overview' if key.startswith('information about ') else key)


def bounded_questions(value):
    if not isinstance(value, list):
        return []
    return [text.strip() for text in value[-MAX_ASKED:]
            if isinstance(text, str) and 0 < len(text.strip()) <= MAX_QUESTION_CHARS]


def parse_controls(text):
    match = MARKER.search(text)
    if not match:
        return []
    try:
        values = json.loads('[' + match.group(1).replace(' | ', ',') + ']')
    except (ValueError, TypeError):
        return []
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and
                             0 < len(value) <= MAX_QUESTION_CHARS and not re.search(r'[\[\]|\n\r]', value)))[:3]


def with_controls(text, questions):
    body = MARKER.sub('', text).strip()
    if questions:
        body += '\n\n[SUGGESTIONS: ' + ' | '.join(json.dumps(q, ensure_ascii=False) for q in questions) + ']'
    return body


def load_catalog():
    from django.db.models import BooleanField, Case, When, Value
    from django.db.models.functions import MD5
    from .models import FAQ
    # Include all public question keys/digests so an excluded duplicate cannot
    # hide a conflict. Public answers are validated locally, never sent to an
    # LLM. No accounts, conversations, or embedding arrays are loaded.
    return list(FAQ.objects.annotate(answer_digest=MD5('answer'), embedding_ready=Case(
        When(embedding__isnull=False, then=Value(True)), default=Value(False), output_field=BooleanField())).values(
            'pk', 'question', 'answer', 'category', 'source_type', 'source_office',
            'embedding_ready', 'answer_digest').order_by('pk'))


def supported_faq(record, question):
    if (record.get('source_type') == 'handbook' or record.get('embedding_ready') is False or
            ('answer' in record and not record['answer'].strip())):
        return False
    # Personnel identity lookups have additional live directory/conflict gates.
    # Do not promise their answerability from an FAQ record alone.
    if re.match(r'^(?:who|sino)\b', question, re.I) and roles_in(question):
        return False
    return 'answer' not in record or eligible_evidence(question, {
        **record, 'record_type': 'faq', 'question': record.get('question', question)})


def starter_questions(catalog, asked=()):
    """Common entry points backed by exact FAQs or existing grounded actions."""
    from types import SimpleNamespace
    from .intents import ENROLL_CHOICES, enrollment_resolution, navigation_destinations, navigation_intent
    from .enrollment import exact_enrollment_lookup
    seen = {question_key(question) for question in asked}
    grouped = defaultdict(list)
    for record in catalog:
        grouped[faq_question_key(record.get('question', ''))].append(record)
    selected = []
    for question in ('What programs are offered at SPUS?', 'How do I enroll at SPUS?', 'Where is the Registrar office?'):
        if question_key(question) in seen:
            continue
        matches = grouped.get(faq_question_key(question), [])
        supported = (bool(matches) and len({row.get('answer_digest') for row in matches}) == 1 and
                     any(supported_faq(row, question) for row in matches))
        if question == 'How do I enroll at SPUS?':
            records = [SimpleNamespace(**record) for record in catalog if 'answer' in record]
            supported = all(bool(exact_enrollment_lookup(enrollment_resolution(choice)[1], records))
                            for choice in ENROLL_CHOICES)
        if navigation_intent(question):
            supported = len(navigation_destinations(question)) == 1
        if supported:
            selected.append(question)
    return selected


def select_followups(current, sources, asked=(), resolved='', parts=(), catalog=(), limit=3):
    from .conversation_context import builtin_vocabulary
    vocabulary = builtin_vocabulary()
    current_entities = defaultdict(set)
    for _, _, entity in vocabulary.mentions(current + ' ' + resolved):
        current_entities[entity.group].add(entity.key)
    seen = {question_key(q) for q in (*asked, current, resolved) if q}
    seen.update(question_key(part['query']) for part in parts if part.get('query'))
    categories, offices, context = set(), set(), set()
    for source in sources:
        title = source.get('title') or ''
        match = re.match(r'^FAQ \((.+)\):\s*(.+)$', title)
        if match:
            categories.add(match.group(1).casefold())
            seen.add(question_key(match.group(2)))
        if source.get('source_office'):
            offices.add(source['source_office'].casefold())
            context |= terms(source['source_office'])
            for _, _, entity in vocabulary.mentions(source['source_office']):
                current_entities[entity.group].add(entity.key)
        context |= terms(title)
    current_words = terms(current + ' ' + resolved)
    current_numbers = set(re.findall(r'\b\d+\b', current + ' ' + resolved))
    answered_digests = {row.get('answer_digest') for row in catalog
                        if row.get('answer_digest') and question_key(row.get('question', '')) in seen}
    grouped, digests = defaultdict(list), defaultdict(set)
    for record in catalog:
        digests[faq_question_key(record.get('question', ''))].add(record.get('answer_digest'))
    for record in catalog:
        question = re.sub(r'^\s*\[[^\]\n]+\]\s*', '', record.get('question') or '').strip()
        if (not QUESTION_START.match(question) or question.count('?') > 1 or
                not 8 <= len(question) <= 110 or re.search(r'[\[\]|<>\n\r]', question) or
                re.search(r'\(\s*Document\b', question, re.I) or
                re.search(r'\b(?:and|or)\s+(?:what|why|how|who|where|when|which|does|do|is|are|can)\b', question, re.I)):
            continue
        if not supported_faq(record, question):
            continue
        if (record.get('source_type') == 'curated' and
                re.fullmatch(r'What is the .+ information\??', question, re.I)):
            continue  # Legacy import headings are not natural FAQ wording.
        if not set(re.findall(r'\b\d+\b', question)).issubset(current_numbers):
            continue  # Do not introduce an unrequested year, grade or other numeric scope.
        # Extracted handbook headings and executable marker syntax never become
        # buttons. A visible suggestion is the stored question, not new prose.
        grouped[faq_question_key(question)].append((record, question))
    ranked = []
    authority = {'office': 3, 'website': 2, 'curated': 1}
    for matches in grouped.values():
        if len(digests[faq_question_key(matches[0][1])]) > 1:
            continue  # Conflicting questions are not advertised as answerable.
        record, question = max(matches, key=lambda item: authority.get(item[0].get('source_type'), 0))
        key = question_key(question)
        if key in seen or record.get('answer_digest') in answered_digests:
            continue
        words = terms(question)
        candidate_entities = defaultdict(set)
        for _, _, entity in vocabulary.mentions(question):
            candidate_entities[entity.group].add(entity.key)
        if any(current_entities[group] and candidate_entities[group] and
               not current_entities[group] & candidate_entities[group] for group in ('audience', 'college')):
            continue
        category = (record.get('category') or '').casefold()
        office = (record.get('source_office') or '').casefold()
        if offices and office and office not in offices:
            continue  # Shared words such as "student" cannot switch the responsible office.
        # Broad words such as "student" and "campus" alone do not connect an
        # office publication procedure to an unrelated university question.
        specific = words - {'student', 'college', 'campus', 'information', 'detail', 'faq'}
        score = (3 * len(specific & current_words) + len(specific & context) +
                 6 * (category in categories) + 4 * bool(office and office in offices) +
                 4 * sum(len(keys & current_entities[group]) for group, keys in candidate_entities.items()) -
                 0.5 * bool(re.search(r'\b20\d{2}\b', question)))
        score -= max(0, len(question) - 70) / 40
        if score <= 0:
            score -= len(candidate_entities['office']) + len(candidate_entities['college'])
        ranked.append((-score, -authority.get(record.get('source_type'), 0), record.get('pk', 0),
                       key, category, question, record.get('answer_digest')))
    ranked.sort()
    # Two good related questions are more useful than padding to three with an
    # unrelated office policy. Broad discovery is used only without a topic match.
    ranked = [row for row in ranked if row[0] < 0]
    selected, counts = [], defaultdict(int)
    for _, _, _, key, category, question, digest in ranked:
        if key in seen or (digest and digest in answered_digests) or counts[category] >= 2:
            continue
        selected.append(question)
        seen.add(key)
        counts[category] += 1
        if digest:
            answered_digests.add(digest)
        if len(selected) >= limit:
            break
    return selected


def response_suggestions(result, current, history=(), asked=(), catalog=None):
    """Preserve required choices; replace generic follow-ups at the API boundary."""
    text, sources, action, _ = result
    explicit = parse_controls(text)
    if explicit:
        # Logic only emits explicit clarification/navigation controls now.
        return with_controls(text, explicit), explicit, 'choice'
    status = getattr(result, 'answer_status', None)
    introducing = getattr(result, 'response_mode', '') in ('identity', 'capabilities')
    if not introducing and (action or status in ('clarification', 'conflict', 'ambiguous', 'unavailable') or (not sources and status != 'no_match')):
        return with_controls(text, []), [], 'related'
    previous = bounded_questions(list(asked))
    previous += [item['content'] for item in history if item.get('role') == 'user' and isinstance(item.get('content'), str)]
    try:
        with stage('followup_suggestions'):
            available = load_catalog() if catalog is None else catalog
            questions = (starter_questions(available, previous) if introducing else
                         select_followups(current, sources, previous, getattr(result, 'context_query', ''),
                                         getattr(result, 'answer_parts', []),
                                         available))
    except Exception as exc:
        logger.info('Follow-up catalog unavailable (%s)', type(exc).__name__)
        questions = []
    return with_controls(text, questions), questions, 'related'
