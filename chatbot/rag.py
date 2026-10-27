"""Hybrid retrieval with independent relevance gates and raw cosine scores."""
import logging
import re
import time
from threading import Lock

from django.conf import settings
from django.db.models import Q
from pgvector.django import CosineDistance

from .grounding import DEPARTMENTS, departments, normalize, rank_evidence, terms
from .retrieval_types import EvidenceList, RetrievalOutcome
from .evidence_identity import consolidate_evidence

logger = logging.getLogger(__name__)
_vocabulary_cache = None
_vocabulary_expires = 0
_vocabulary_lock = Lock()


class RAGSearcher:
    def __init__(self):
        self.model = None

    def _generate_embedding(self, text):
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
        return self.model.encode(text).tolist()

    def ensure_embeddings(self):
        from .models import FAQ, Location, StaffMember, WebResource
        formats = (
            (Location, lambda obj: f'Location: {obj.name}. {obj.description}'),
            (StaffMember, lambda obj: f'Staff: {obj.name}, {obj.position}. Office located at {obj.office}.'),
            (FAQ, lambda obj: f'FAQ about {obj.category}: {obj.question} - {obj.answer}'),
            (WebResource, lambda obj: f'{obj.category} - {obj.title}: {obj.content}'),
        )
        for model, format_text in formats:
            for obj in model.objects.filter(embedding__isnull=True):
                obj.embedding = self._generate_embedding(format_text(obj))
                obj.save(update_fields=['embedding'])

    @staticmethod
    def context_vocabulary():
        """Cache public KB labels only; never cache a user's conversation.

        New FAQ subjects, offices and locations become entity candidates without
        adding a follow-up branch to the resolver. Refresh is bounded to 60 s.
        """
        from .conversation_context import Entity, Vocabulary, builtin_vocabulary
        from .models import FAQ, Location, StaffMember, WebResource, Announcement
        global _vocabulary_cache, _vocabulary_expires
        with _vocabulary_lock:
            if _vocabulary_cache is not None and time.monotonic() < _vocabulary_expires:
                return _vocabulary_cache
            entities = list(builtin_vocabulary().entities)
            for name in Location.objects.values_list('name', flat=True)[:300]:
                if name:
                    entities.append(Entity('office', name.casefold(), name, (name,)))
            offices = set(FAQ.objects.exclude(source_office__isnull=True).values_list('source_office', flat=True)[:300])
            offices.update(StaffMember.objects.values_list('office', flat=True)[:300])
            for name in offices:
                if name and len(name) <= 100:
                    entities.append(Entity('office', name.casefold(), name, (name,)))
            for question in FAQ.objects.values_list('question', flat=True)[:1500]:
                subject = re.search(r'\b(?:for|about|of)\s+(.+?)(?:\s*\(Document|\?|$)', question, re.I)
                if subject:
                    name = subject.group(1).strip(' .?')
                    if 3 <= len(name) <= 100:
                        entities.append(Entity('subject', name.casefold(), name, (name,)))
            for name in StaffMember.objects.values_list('name', flat=True)[:500]:
                entities.append(Entity('person', name.casefold(), name, (name,)))
            for name in Announcement.objects.filter(is_active=True).values_list('title', flat=True)[:100]:
                entities.append(Entity('subject', name.casefold(), name, (name,)))
            for name in WebResource.objects.values_list('title', flat=True)[:1000]:
                if 3 <= len(name) <= 100 and '|' not in name:
                    entities.append(Entity('subject', name.casefold(), name, (name,)))
            # Existing adapter aliases win duplicate spans over dynamic labels.
            known = set()
            unique = []
            for entity in entities:
                aliases = tuple(a for a in entity.aliases if a.casefold() not in known)
                known.update(a.casefold() for a in aliases)
                if aliases:
                    unique.append(Entity(entity.group, entity.key, entity.label, aliases))
            _vocabulary_cache = Vocabulary(unique)
            _vocabulary_expires = time.monotonic() + 60
            return _vocabulary_cache

    def retrieve(self, query, limit=5, allow_fallback=False):
        started = time.perf_counter()
        try:
            rows = self.search(query, limit)
            rows_status = getattr(rows, 'status', None)
            rows = consolidate_evidence(rows)
            if rows_status:rows=EvidenceList(rows,status=rows_status)
            status = getattr(rows, 'status', 'ok' if rows else 'no_match')
            attempts = 1
            from .enrollment import enrollment_lookup_topic
            # Other search paths already exhaust hybrid retrieval. Retrying
            # them wastes vector work and can bypass their identity filter.
            structured = enrollment_lookup_topic(query)
            if not rows and status == 'no_match' and allow_fallback and structured:
                rows = self._hybrid_search(query, limit)
                attempts = 2
            answers = {}
            for row in rows:
                # Same attributed subject with incompatible stored excerpts is
                # a data conflict across ANY knowledge topic, not a selector tie.
                key = (normalize(row.get('question') or row.get('document_title') or ''),
                       row.get('source_type'), row.get('source_office'))
                answers.setdefault(key, set()).add(normalize(row.get('answer') or row.get('text') or ''))
            if any(len(values) > 1 for values in answers.values()):
                return RetrievalOutcome(status='conflict', attempts=attempts,
                                        elapsed_ms=(time.perf_counter() - started) * 1000)
            return RetrievalOutcome(list(rows), 'ok' if rows else status, attempts,
                                    (time.perf_counter() - started) * 1000)
        except Exception as exc:
            logger.warning('Retrieval failed (%s)', type(exc).__name__)
            return RetrievalOutcome(status='unavailable', elapsed_ms=(time.perf_counter() - started) * 1000)

    def search(self, query, limit=5):
        from .models import FAQ, Location, StaffMember, WebResource
        if re.search(r'\bannouncements?\b', query, re.I):
            return self._announcements(query, limit)
        from .enrollment import exact_enrollment_lookup, enrollment_lookup_topic
        if enrollment_lookup_topic(query):
            # Return only the requested office procedure/documents, including
            # abstention if no unique supported answer exists. No model needed.
            rows = exact_enrollment_lookup(query)
            return EvidenceList(rows[:limit], status=getattr(rows, 'status', 'ok' if rows else 'no_match'))
        from .personnel import exact_personnel_lookup, lookup_kind
        exact = exact_personnel_lookup(query)
        if getattr(exact, 'status', '') in ('ambiguous', 'conflict'):
            return exact
        if exact:
            return exact[:limit]
        # A missing exact match is not evidence that the entire KB lacks a
        # record. Try local exact roles/names, then the same gated hybrid path.
        if re.search(r'\b(who|sino)\b', query, re.I):
            # Exact role lookup is reusable for locally maintained positions
            # not yet reflected in the website directory (e.g. an appointed
            # organization moderator). Do not infer a new holder from vectors.
            query_terms = terms(query)
            staff = [obj for obj in StaffMember.objects.all() if terms(obj.position) == query_terms]
            if staff:
                if len({obj.name.casefold() for obj in staff}) > 1:
                    return EvidenceList(status='ambiguous')
                obj = staff[0]
                answer = f'{obj.name} is the {obj.position}.'
                if obj.office:
                    answer += f' Office located at {obj.office}.'
                return [dict(question=f'Who is the {obj.position}?', document_title=f'Staff Directory: {obj.position}',
                             answer=answer, text=answer, source_type='staff_directory', source_office=obj.office,
                             personnel_role=obj.position, personnel_name=obj.name, source_url=None, retrieval_method='exact_staff_role')]
        rows=self._hybrid_search(query, limit)
        if lookup_kind(query) in ('role','name'):
            from .grounding import NAME_RE
            # An office location or handbook job description is not an answer
            # identifying a person, even when it contains the requested title.
            rows=[row for row in rows if row.get('personnel_name') or NAME_RE.search(row.get('answer') or '')]
        return rows

    @staticmethod
    def _announcements(query, limit):
        from .models import Announcement
        from .grounding import eligible_evidence
        # Announcements already form an authoritative structured public source.
        # Inactive records must never leak through conversational retrieval.
        rows = []
        for obj in Announcement.objects.filter(is_active=True).order_by('-created_at')[:30]:
            answer = f'{obj.title}\n{obj.content}\nPublished: {obj.created_at.date().isoformat()}'
            row = dict(question=f'Announcement: {obj.title}', answer=answer, text=answer,
                       document_title=f'Announcement: {obj.title}', source_type='announcement',
                       source_office=None, source_url=None, record_type='announcement', record_id=obj.pk)
            if eligible_evidence(query, row):
                rows.append(row)
        return rows[:limit]

    def _hybrid_search(self, query, limit=5):
        from .models import FAQ, Location, StaffMember, WebResource
        self.ensure_embeddings()
        vector = self._generate_embedding(query)
        pool_size = max(15, limit * 3)
        keywords = sorted(terms(query))[:12]
        for department in sorted(departments(query)):
            keywords.extend(DEPARTMENTS[department])
        if 'faculty' in keywords:
            keywords.extend(('instructor', 'professor', 'lecturer', 'teacher'))

        candidates = []
        specs = (
            (Location, ('name', 'description')),
            (StaffMember, ('name', 'position', 'office')),
            (FAQ, ('question', 'answer', 'category', 'source_office')),
            (WebResource, ('title', 'content', 'category')),
        )
        for model, fields in specs:
            base = model.objects.exclude(embedding__isnull=True).annotate(
                distance=CosineDistance('embedding', vector))
            records = {obj.pk: obj for obj in base.order_by('distance', 'pk')[:pool_size]}
            # Rescue acronyms through lexical candidates, subject to the same
            # cosine and entity gates as semantic candidates.
            if keywords:
                lexical = Q()
                for keyword in keywords:
                    for field in fields:
                        lexical |= Q(**{f'{field}__icontains': keyword})
                records.update({obj.pk: obj for obj in base.filter(lexical).order_by('distance', 'pk')[:pool_size]})
            for obj in records.values():
                distance = float(obj.distance)
                if model is Location:
                    result = dict(question=f'Where is {obj.name}?', answer=obj.description,
                                  document_title=f'Location: {obj.name}', source_type='campus_map', source_office=None)
                elif model is StaffMember:
                    result = dict(question=f'Who is the {obj.position}?',
                                  answer=f'{obj.name} is the {obj.position}.' + (f' Office located at {obj.office}.' if obj.office else ''),
                                  document_title=f'Staff Directory: {obj.position}',
                                  source_type='staff_directory', source_office=obj.office,
                                  personnel_role=obj.position, personnel_name=obj.name)
                elif model is FAQ:
                    result = dict(question=obj.question, answer=obj.answer,
                                  document_title=f'FAQ ({obj.category}): {obj.question}',
                                  source_type=obj.source_type or 'curated', source_office=obj.source_office)
                else:
                    result = dict(question=obj.title, answer=obj.content,
                                  document_title=obj.title, source_type='website', source_office=None)
                    from .personnel import structured_person
                    if obj.category=='Website personnel':
                        person=structured_person(obj)
                        if person:
                            result.update(personnel_name=person['name'],personnel_role=person['role'],
                                          personnel_section=person['section'],source_office=person['section'],
                                          answer=f"{person['name']} — {person['role']}")
                result.update(text=result['answer'], distance=distance, record_id=obj.pk,
                              record_type=model._meta.model_name,
                              source_url=obj.url if model is WebResource else None)
                candidates.append(result)

        results = rank_evidence(query, candidates, limit=limit,
                                max_distance=getattr(settings, 'RAG_MAX_COSINE_DISTANCE', 0.45))
        # No automatic live scraping: an unreviewed search hit is not evidence.
        logger.info('Retrieval candidates=%d accepted=%d', len(candidates), len(results))
        return results

