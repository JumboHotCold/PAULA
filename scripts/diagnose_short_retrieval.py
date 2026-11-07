"""Read-only retrieval diagnostics; use Docker manage.py shell."""
import json
from pathlib import Path
import time
from django.db import connection, transaction
from pgvector.django import CosineDistance
from chatbot.models import FAQ, Location, StaffMember, WebResource
from chatbot.grounding import eligible_evidence
from chatbot.rag import RAGSearcher

queries = ['What programs are offered?', 'What programs are offered at SPUS?', 'What courses are available?',
           'What scholarships are available?', 'What services are offered?']
rag = RAGSearcher()
rows = []
with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute('SET TRANSACTION READ ONLY')
    coverage = {model.__name__: model.objects.filter(embedding__isnull=True).count() for model in (FAQ, Location, StaffMember, WebResource)}
    for query in queries:
        vector = rag._generate_embedding(query)
        candidates = []
        for obj in FAQ.objects.annotate(distance=CosineDistance('embedding', vector)).order_by('distance', 'pk')[:15]:
            row = dict(question=obj.question, answer=obj.answer, record_type='faq', source_office=obj.source_office)
            candidates.append(dict(id=obj.pk, question=obj.question, distance=float(obj.distance), eligible=eligible_evidence(query, row)))
        start = time.perf_counter()
        outcome = rag.retrieve(query)
        rows.append(dict(query=query, status=outcome.status, ms=round((time.perf_counter()-start)*1000, 2),
                         selected=[dict(id=r.get('record_id'), title=r.get('question'), distance=r.get('distance')) for r in outcome.evidence],
                         faq_candidates=candidates))
Path('PAULA_SHORT_RETRIEVAL_DIAGNOSIS.json').write_text(json.dumps(dict(missing_embeddings=coverage, queries=rows), indent=2))
print(json.dumps([dict(query=r['query'], status=r['status'], selected=r['selected'], top_faq=r['faq_candidates'][:3]) for r in rows]))
