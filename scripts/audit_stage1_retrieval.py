"""Inspect actual compatible vectors and evidence gates; no indexing or LLM calls."""
import json
from pathlib import Path
import time
from unittest.mock import patch
from django.db import connection, transaction
from pgvector.django import CosineDistance
from chatbot.embedding_runtime import runtime
from chatbot.grounding import eligible_evidence, terms
from chatbot.models import FAQ
from chatbot.rag import RAGSearcher


def main():
    started = time.perf_counter()
    model = runtime.initialize()
    report = dict(model_dimension=model.get_sentence_embedding_dimension(),
                  offline_initialization_ms=round((time.perf_counter()-started)*1000, 2), rows=[])
    rag = RAGSearcher()
    rag.model = model
    for query in ('why should i enroll in SPUS institution?', 'why should i enroll at SPUS?',
                  'What programs are offered?', 'why spus?'):
        start = time.perf_counter()
        vector = rag._generate_embedding(query)
        encoding_ms = round((time.perf_counter()-start)*1000, 2)
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
            with patch.object(rag, '_generate_embedding', return_value=vector):
                outcome = rag.retrieve(query)
            nearest = []
            for row in FAQ.objects.exclude(embedding__isnull=True).annotate(distance=CosineDistance('embedding', vector)).order_by('distance', 'pk')[:8]:
                candidate = dict(question=row.question, answer=row.answer, record_type='faq', source_type=row.source_type,
                                 source_office=row.source_office)
                nearest.append(dict(id=row.pk, question=row.question, distance=float(row.distance),
                                    passes_raw_cutoff=float(row.distance) <= .45,
                                    passes_evidence_gate=eligible_evidence(query, candidate)))
        report['rows'].append(dict(query=query, terms=sorted(terms(query)), query_encoding_ms=encoding_ms,
            retrieval_status=outcome.status, retrieved=[{k:row.get(k) for k in ('record_id', 'record_type', 'question', 'retrieval_method')} for row in outcome.evidence],
            nearest_faqs=nearest))
    output = Path('artifacts/stage1/retrieval.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(model_dimension=report['model_dimension'], offline_initialization_ms=report['offline_initialization_ms'],
                         outcomes=[dict(query=row['query'], status=row['retrieval_status'], top_faq=row['nearest_faqs'][0]) for row in report['rows']])))


if __name__ in ('__main__', '<run_path>'):
    main()
