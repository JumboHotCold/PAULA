"""Bounded deterministic coordination parsing, without institutional facts.

Only clear question clauses, shared grammatical slots, and typed entity lists
are expanded. Conjunctions inside known labels, quotes, and parentheses stay
intact. Unclear relationships remain atomic for normal grounding/clarification.
"""
from dataclasses import dataclass
import re

from .query_normalization import roles_in

MAX_PARTS = 4
MAX_QUERY_CHARS = 2000
QUESTION_START = re.compile(
    r'^(?:who|what|which|where|when|why|how|sino|ano|saan|nasaan|kailan|paano|'
    r'tell me|explain|compare|ihambing)\b', re.I)
HEAD = re.compile(
    r'^(?P<head>(?:(?:who|what|where)\s+(?:is|are)|sino\s+(?:ang|sina)|'
    r'(?:saan|nasaan)\s+(?:ang|yung)|ano\s+ang)(?:\s+(?:the|mga))?\s+)(?P<body>.+)$', re.I)
FOLLOW_HEAD = re.compile(r'^(?P<head>(?:how about|what about|paano naman(?: ang| sa)?|sa|and)\s+)(?P<body>.+)$', re.I)
SEPARATOR = re.compile(r'\s*,\s*(?:(?:and|at|pati|tsaka)\s+)?|\s*;\s*|\s+\b(?:and|at|pati|tsaka)\b\s+|\s+&\s+|[?]\s+(?=\w)', re.I)
CONDITION = re.compile(r'\s+((?:in|during|as of|before|after|without|except|excluding|at|sa)\s+.+)$', re.I)
RELATION = re.compile(r'\b(?:between|difference|relationship|distinction|versus|vs|compare|ihambing|pagkakaiba)\b', re.I)
DEPENDENT_ACTION = re.compile(r'(?:how (?:do|can) i (?:apply|register|renew)|paano(?: ako)? mag[- ]?apply)[?.! ]*', re.I)


@dataclass(frozen=True)
class QueryPlan:
    queries: tuple = ()
    clarification: str = ''
    reason: str = 'atomic'


def question(text):
    return text.strip(' ,;?!.') + '?'


def topic_subject(text):
    """Extract an explicit grammatical object, never an answer from history."""
    clean = text.strip(' ?!.')
    match = re.match(r'^(?:what|which)\s+(.+?)\s+(?:is|are)\s+(?:available|offered)\b', clean, re.I)
    if not match:
        match = re.match(r'^(?:what (?:is|are)|ano ang)\s+(?:the\s+)?(.+)$', clean, re.I)
    return match.group(1) if match else ''


def bind_dependent(query, prior):
    """A short action question may reuse its immediately named resource."""
    if DEPENDENT_ACTION.fullmatch(query):
        subject = topic_subject(prior)
        if subject:
            return question(query.rstrip(' ?!.') + ' for ' + subject)
    return query


def _protected(text, vocabulary):
    spans = [(a, b) for a, b, _ in vocabulary.mentions(text)]
    spans.extend((m.start(), m.end()) for m in re.finditer(r'"[^"\n]*"|“[^”\n]*”|\([^()]*\)', text))
    return spans


def _segments(text, vocabulary):
    protected = _protected(text, vocabulary)
    matches = [m for m in SEPARATOR.finditer(text)
               if not any(a <= m.start() < b or a < m.end() <= b for a, b in protected)
               and not (m.group().strip().lower() == 'at' and not
                        re.search(r'\b(sino|ano|saan|nasaan|paano|ang|mga)\b', text, re.I))]
    if not matches:
        return [text]
    pieces = []
    start = 0
    for match in matches:
        pieces.append(text[start:match.start()].strip())
        start = match.end()
    pieces.append(text[start:].strip(' ?!.'))
    return pieces


def _entity_slots(pieces, vocabulary):
    mentions = [vocabulary.mentions(piece) for piece in pieces]
    common = set.intersection(*({entity.group for _, _, entity in row} for row in mentions))
    # Roles with different offices are handled as noun phrases, not as a
    # replacement of the role word while accidentally retaining the old office.
    common.discard('role')
    for group in sorted(common):
        selected = [[row for row in rows if row[2].group == group] for rows in mentions]
        if any(len(rows) != 1 for rows in selected):
            continue
        first_start = selected[0][0][0]
        prefix = pieces[0][:first_start]
        if not prefix.strip():
            continue
        # Every later fragment must start with its entity; only its own suffix
        # may follow. This prevents dropping unsupported conditions/commands.
        if any(piece[:rows[0][0]].strip() for piece, rows in zip(pieces[1:], selected[1:])):
            continue
        tails = [piece[rows[0][1]:] for piece, rows in zip(pieces, selected)]
        common_tail = tails[-1] if all(not tail.strip() for tail in tails[:-1]) else ''
        output = []
        for piece, rows, tail in zip(pieces, selected, tails):
            a, b, _ = rows[0]
            output.append(question(prefix + piece[a:b] + (tail or common_tail)))
        return output
    return None


def _expand(pieces, vocabulary):
    # Distinct complete clauses have independent scopes. Pronouns/actions in
    # later clauses are subsequently resolved against the prior clause.
    if all(QUESTION_START.match(piece) for piece in pieces):
        return [question(piece) for piece in pieces]
    starts = [index for index, piece in enumerate(pieces) if QUESTION_START.match(piece)]
    if starts and starts[0] == 0 and len(starts) > 1:
        output = []
        for a, b in zip(starts, starts[1:] + [len(pieces)]):
            group = pieces[a:b]
            expanded = [question(group[0])] if len(group) == 1 else _expand(group, vocabulary)
            if expanded is None:
                return None
            output.extend(expanded)
        return output
    if RELATION.search(' '.join(pieces)):
        return None
    slots = _entity_slots(pieces, vocabulary)
    if slots:
        return slots
    lead = HEAD.match(pieces[0]) or FOLLOW_HEAD.match(pieces[0])
    if not lead:
        return None
    body = lead.group('body')
    fragments = [body, *pieces[1:]]
    # A shared predicate over role-bearing noun phrases works for all offices
    # and roles represented by the existing role vocabulary.
    if all(roles_in(fragment) for fragment in fragments):
        tail = CONDITION.search(fragments[-1])
        output = []
        for index, fragment in enumerate(fragments):
            suffix = ' ' + tail.group(1) if tail and index < len(fragments)-1 and not CONDITION.search(fragment) else ''
            output.append(question(lead.group('head') + fragment + suffix))
        return output
    # Unknown future named resources can share a grammatical for/about/of slot
    # without requiring a new topic-specific branch or entity registry entry.
    slot = re.match(r'^(.*\b(?:for|about|of)\s+)([^?]+)$', body, re.I)
    if slot and all(0 < len(fragment.split()) <= 8 for fragment in [slot.group(2), *pieces[1:]]):
        return [question(lead.group('head') + slot.group(1) + fragment)
                for fragment in [slot.group(2), *pieces[1:]]]
    return None


def decompose_query(text, vocabulary):
    if len(text) > MAX_QUERY_CHARS:
        return QueryPlan(clarification='Please shorten the question to 2,000 characters.', reason='limit')
    if re.search(r'\b(?:and|pati|tsaka)\s*[?!. ]*$', text, re.I):
        return QueryPlan(clarification='Please complete each part of your question.', reason='incomplete')
    pieces = _segments(text, vocabulary)
    if len(pieces) == 1:
        return QueryPlan((text,))
    if not all(pieces):
        return QueryPlan(clarification='Please complete each part of your question.', reason='incomplete')
    if len(pieces) > 32:
        return QueryPlan(clarification=f'Please ask at most {MAX_PARTS} parts at a time.', reason='limit')
    expanded = _expand(pieces, vocabulary)
    if not expanded:
        return QueryPlan((text,))
    unique = tuple(dict.fromkeys(expanded))
    if len(unique) > MAX_PARTS:
        return QueryPlan(clarification=f'Please ask at most {MAX_PARTS} parts at a time.', reason='limit')
    return QueryPlan(unique, reason='compound' if len(unique) > 1 else 'collapsed')
