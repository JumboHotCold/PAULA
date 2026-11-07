"""Direct lookup of category-specific Registrar enrollment evidence.

Common guided enrollment choices are structured retrieval requests, not a
semantic similarity contest. Facts still come solely from office FAQ records.
"""
import re

from .grounding import eligible_evidence, terms
from .intents import enrollment_category, enrollment_request, enrollment_subject
from .retrieval_types import EvidenceList
from .performance import timed


def enrollment_lookup_topic(query):
    if not enrollment_category(query) or not enrollment_request(query):
        return None
    # Keep dates, fees, school levels, named institutions, special cases and
    # additional constraints out of this shortcut rather than dropping them.
    allowed = {'enroll', 'admission', 'college', 'student', 'freshmen', 'transferee', 'continuing',
               'requirement', 'document', 'documents', 'papers', 'procedure', 'process', 'steps', 'step',
               'help', 'want', 'need', 'get', 'go', 'start', 'mag', 'incoming', 'first', 'year', 'new'}
    if not terms(query).issubset(allowed):
        return None
    return 'documents' if re.search(r'\b(requirements?|documents?|papers)\b', query, re.I) else 'procedure'


@timed('structured_enrollment')
def exact_enrollment_lookup(query, records=None):
    topic = enrollment_lookup_topic(query)
    if topic is None:
        return []
    if records is None:
        from .models import FAQ
        records = FAQ.objects.filter(source_type='office', source_office__iexact='Registrar').order_by('pk')
    answers = {}
    for obj in records:
        if obj.source_type != 'office' or (obj.source_office or '').casefold() != 'registrar':
            continue
        if enrollment_category(obj.question) != enrollment_category(query):
            continue
        subject = enrollment_subject(obj.question)
        documents = bool(re.search(r'\b(requirements?|documents?|papers)\b', subject, re.I))
        if documents != (topic == 'documents'):
            continue
        if topic == 'procedure' and not re.search(r'\b(procedure|process|steps?|how)\b', subject, re.I):
            continue
        row = dict(question=obj.question, answer=obj.answer, text=obj.answer,
                   document_title=f'FAQ ({obj.category}): {obj.question}', source_type=obj.source_type,
                   source_office=obj.source_office, source_url=None, retrieval_method='exact_registrar_enrollment')
        if eligible_evidence(query, row):
            answers.setdefault(obj.answer.strip(), row)
    # Distinct competing office answers require review, not arbitrary selection.
    return EvidenceList(answers.values()) if len(answers) == 1 else EvidenceList(status='conflict' if len(answers) > 1 else 'no_match')
