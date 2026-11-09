"""Answer diagnostics are payload-free unless rehearsal text logging is explicitly enabled."""
import json
import logging
from django.conf import settings
from .performance import diagnostic_outcome

rehearsal_logger = logging.getLogger('paula.rehearsal')
ANSWER_REASONS = {
    'no_match': 'NO_MATCH', 'clarification': 'UNCLEAR_INTENT', 'unavailable': 'RETRIEVAL_UNAVAILABLE',
    'conflict': 'SOURCE_CONFLICT', 'ambiguous': 'AMBIGUOUS_EVIDENCE',
    'selection_rejected': 'VALIDATION_REJECTED', 'partial': 'PARTIAL_ANSWER', 'unresolved': 'UNRESOLVED_PARTS',
}


def record_answer_outcome(query, result):
    status = getattr(result, 'answer_status', 'ok' if result[1] or result[2] else 'no_match')
    reason = ANSWER_REASONS.get(status)
    if reason is None:
        return
    parts = getattr(result, 'answer_parts', ())
    unresolved = [index for index, part in enumerate(parts, 1) if part.get('status') in ANSWER_REASONS]
    request_id = diagnostic_outcome('answer', reason, unresolved_parts=unresolved)
    if settings.PAULA_LOG_UNANSWERED_QUERIES:
        # Deliberate opt-in exception: logs can retain text. No history, identity,
        # cookies, context token or source/answer text is included in this event.
        rehearsal_logger.info(json.dumps({'event': 'unanswered_query_rehearsal', 'request_id': request_id,
            'reason_code': reason, 'query_text': query[:2000]}, ensure_ascii=True, separators=(',', ':')))
