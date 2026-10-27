"""Pure, testable evidence gates shared by retrieval and response rendering.

Scores are ranking signals, not probabilities. Authority never makes an
irrelevant entry eligible. Generated prose is never treated as evidence.
"""

import json
import math
import re

from .intents import enrollment_category, enrollment_request, enrollment_subject
from .query_normalization import canonical_text, normalized_text, FRESHNESS_WORDS, roles_in, role_supported
from .evidence_identity import consolidate_evidence


DEPARTMENTS = {
    'ceit': ('ceit', 'college of engineering and information technology',
             'engineering and information technology'),
    'chs': ('chs', 'college of health sciences'),
    'cbma': ('cbma', 'college of business management and accountancy'),
    'ceas': ('ceas', 'college of education arts and sciences'),
    'ccje': ('ccje', 'college of criminal justice education'),
    'gsps': ('gsps', 'graduate school and professional studies', 'graduate school'),
    'pbmo': ('pbmo', 'publication brand and marketing office'),
}
STOPWORDS = set('''a an the is are was were be been who what which how do does
    did can could would should will i me my we our you your they their it its
    of for in on at to as and or with about please tell give show list all lineup
    available current latest official offered offer offers much name names any spus saint st paul university surigao
    ang mga ng sa sino ano paano po ba naman meron may uh um hey hello'''.split())
SYNONYMS = {
    'announcements': 'announcement',
    'faculties': 'faculty', 'teachers': 'faculty', 'teacher': 'faculty',
    'instructors': 'faculty', 'instructor': 'faculty', 'professors': 'faculty',
    'professor': 'faculty', 'lecturer': 'faculty', 'lecturers': 'faculty',
    'guro': 'faculty', 'courses': 'program', 'course': 'program',
    'programs': 'program', 'degrees': 'program', 'kurso': 'program',
    'programa': 'program', 'enrollment': 'enroll', 'enrolment': 'enroll',
    'enrol': 'enroll', 'admissions': 'admission', 'requirements': 'requirement',
    'enrolling': 'enroll', 'enrolled': 'enroll', 'documents': 'document',
    'papers': 'document',
    'scholarships': 'scholarship', 'fees': 'fee', 'payments': 'payment',
    'registrars': 'registrar', 'academics': 'academic',
    'freshman': 'freshmen', 'transferees': 'transferee',
    'students': 'student', 'old': 'continuing',
    'kailan': 'when', 'magkano': 'fee', 'nasaan': 'location', 'saan': 'location',
    'where': 'location', 'located': 'location', 'offer': 'offered',
}
FACULTY_RE = re.compile(r'\b(faculty|faculties|teachers?|instructors?|professors?|lecturers?|guro)\b', re.I)
NAME_RE = re.compile(
    r'\b(?:Dr|Mr|Mrs|Ms|Engr|Prof|Sr|Fr)\.\s+[A-Z][\w\'-]+', re.UNICODE)


def normalize(text):
    return normalized_text(text)


def departments(text):
    text = ' ' + normalize(text) + ' '
    return {key for key, aliases in DEPARTMENTS.items()
            if any(' ' + alias + ' ' in text for alias in department_aliases(aliases))}


def department_aliases(aliases):
    # The organization noun phrase remains the same when "Office" is omitted
    # in a role title. This applies to any future office alias configuration.
    return tuple(dict.fromkeys(alias.removesuffix(' office') for alias in aliases))+tuple(aliases)


def terms(text):
    text = canonical_text(text)
    text = re.sub(r'\bhigher education\b', 'college', text)
    text = re.sub(r'\bvice president\b', 'vp', text)
    text = re.sub(r'\bline up\b', 'lineup', text)
    for key, aliases in DEPARTMENTS.items():
        for alias in sorted(department_aliases(aliases), key=len, reverse=True):
            text = re.sub(r'\b' + re.escape(alias) + r'\b', key, text)
    return {SYNONYMS.get(word, word) for word in text.split()
            if word not in STOPWORDS and word not in FRESHNESS_WORDS and len(word) > 1}


def eligible_evidence(query, result):
    """Require topic/entity support before applying any authority preference.

    A faculty catalog must actually contain named personnel, not merely mention
    a college in a program catalog. Mixed-college chunks are refused rather than
    associating a name with a nearby, unrelated department heading.
    """
    body = (result.get('answer') or result.get('text') or '').strip()
    if not body:
        return False
    title = result.get('question') or result.get('document_title') or result.get('title') or ''
    scope = ' '.join([title, result.get('source_office') or '', body])
    requested = departments(query)
    found = departments(scope)
    if requested and not requested.issubset(found):
        return False
    # A generic calendar cannot substantiate a requested year's exact dates.
    years = set(re.findall(r'\b20\d{2}\b', query))
    if years and not years.issubset(set(re.findall(r'\b20\d{2}\b', scope))):
        return False
    for acronym in re.findall(r'\b[A-Z]{2,}\b', query):
        if acronym.lower() not in DEPARTMENTS and acronym != 'SPUS':
            if acronym.casefold() not in canonical_text(scope).split():
                return False
    # Specific roles are mandatory constraints, not optional overlap points.
    if not role_supported(query, result.get('personnel_role') or scope):
        return False
    if result.get('personnel_role') and roles_in(query):
        qualifiers=terms(query)-roles_in(query)-terms(result.get('personnel_name',''))-{'members','services','service','office'}
        if not qualifiers.issubset(terms(result['personnel_role'])):
            return False
    if 'president' in roles_in(query):
        actual_role = result.get('personnel_role')
        if actual_role and not re.fullmatch(r'(?:university\s+)?president', actual_role, re.I):
            return False
    if FACULTY_RE.search(query):
        # A dean/office holder alone is not a faculty lineup.
        personnel_body = re.sub(r'\bfaculty\s+(?:room|office|lounge|development)\b', '', body, flags=re.I)
        if not FACULTY_RE.search(personnel_body):
            return False
        if result.get('source_type') == 'staff_directory' and not FACULTY_RE.search(
                result.get('personnel_role') or title):
            return False
        named_line = any(
            FACULTY_RE.search(line) and
            re.search(r'^\s*[-*\d.) ]*[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4}'
                      r'\s*(?:[,|:–—-]|is\s+(?:an?|the)\b)', line)
            for line in body.splitlines())
        if not NAME_RE.search(body) and not named_line:
            return False
        faculty_scope = departments(result.get('personnel_section') or scope)
        if requested and faculty_scope != requested:
            return False
    query_terms = terms(query)
    if not query_terms:
        return False
    body_terms = terms(scope)
    title_terms = terms(title)
    if enrollment_request(query):
        audience = enrollment_category(query)
        if audience and enrollment_category(title) != audience:
            return False
        if re.search(r'\b(requirements?|documents?|papers)\b', query, re.I):
            if not re.search(r'\b(requirements?|documents?|papers)\b', enrollment_subject(title), re.I):
                return False
    # Distinguish the entry's subject from an incidental mention in a long
    # answer (e.g. a scholarship paragraph inside a program catalog).
    for topic in ('program', 'scholarship', 'tuition', 'fee', 'calendar'):
        if topic in query_terms and topic not in title_terms:
            if not (topic in ('tuition', 'fee') and title_terms & {'tuition', 'fee', 'payment'}):
                return False
    for audience in ('freshmen', 'transferee', 'continuing'):
        if audience in query_terms and audience not in title_terms:
            return False
    if re.search(r'\b(how|paano)\b', query, re.I) and 'enroll' in query_terms:
        if not re.search(r'\b(procedure|process|steps?|how|paano)\b', title, re.I):
            return False
    # Each substantive constraint must have meaningful support. Department names
    # alone cannot make a program/fee/calendar entry answer a faculty question.
    overlap = query_terms & body_terms
    if not overlap:
        return False
    minimum_coverage = 1.0 if len(query_terms) <= 2 else 0.6
    return len(overlap) / len(query_terms) >= minimum_coverage


def rank_evidence(query, results, limit=5, max_distance=0.45):
    """Filter using *raw cosine distance*, then rank bounded eligible evidence.

    The conservative default needs calibration against SPUS evaluation queries.
    Legacy/unknown scores and non-finite values fail closed.
    """
    eligible = []
    for original in results:
        distance = original.get('distance')
        if not isinstance(distance, (int, float)) or not math.isfinite(distance):
            continue
        if distance < 0 or distance > max_distance or not eligible_evidence(query, original):
            continue
        result = dict(original)
        body = result.get('answer') or result.get('text') or ''
        overlap = len(terms(query) & terms(result.get('question') or result.get('document_title') or ''))
        authority = {'office': 0, 'website': 1, 'staff_directory': 2, 'handbook': 3}.get(result.get('source_type'), 4)
        # Authority is a tie-breaker between similarly relevant candidates.
        eligible.append((distance - min(overlap, 4) * 0.02, authority, result))
    eligible.sort(key=lambda item: (round(item[0], 1), item[1], item[0]))
    return consolidate_evidence([item[2] for item in eligible])[:limit]


def selected_evidence(payload, count):
    """Accept only existing evidence IDs; reject model-authored factual text."""
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or set(data) != {'evidence_ids'}:
        return None
    ids = data['evidence_ids']
    if not isinstance(ids, list) or len(ids) > count:
        return None
    if any(type(index) is not int or not 1 <= index <= count for index in ids):
        return None
    return list(dict.fromkeys(ids))


def source_for(result):
    return {
        'title': result.get('document_title') or result.get('title') or result.get('question') or 'Knowledge base entry',
        'page': None,
        'url': result.get('source_url') or result.get('url'),
        'source_type': result.get('source_type', 'curated'),
        'source_office': result.get('source_office'),
        'retrieved_at': result.get('retrieved_at'),
        'supporting_sources': result.get('supporting_sources', []),
        'review_notes': result.get('review_notes', []),
    }


def render_evidence(results):
    """Render stored answers verbatim and cite only evidence actually displayed."""
    blocks, sources = [], []
    for result in results:
        body = result.get('answer') or result.get('text') or ''
        # The UI uses this delimiter as controls, never accept it from evidence.
        body = re.sub(r'\[SUGGESTIONS:.*?\]', '', body, flags=re.S).strip()
        if body:
            blocks.append(body)
            sources.append(source_for(result))
    return '\n\n'.join(blocks), sources
