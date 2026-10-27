"""Read-only paired conversational retrieval evaluation; no provider calls.

Run through Docker's Django management shell. Measures literal fragment
retrieval versus the implemented resolver + retrieval on the same connection.
No test accounts, KB inserts, migrations or embedding writes are performed.
"""
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paulibot.settings')
os.environ['HF_HUB_OFFLINE'] = '1'

import django
django.setup()
from django.db import connection, transaction
from chatbot.conversation_context import resolve_conversation
from chatbot.rag import RAGSearcher


CASES = (
    ('procedure_transferee', 'How do old students enroll at SPUS?', 'How about transferee?', 'URO-PR-017'),
    ('procedure_freshmen', 'How do old students enroll at SPUS?', 'And freshmen?', 'URO-PR-005'),
    ('procedure_filipino', 'How do old students enroll at SPUS?', 'Paano naman ang transferee?', 'URO-PR-017'),
    ('documents_transferee', 'What documents do incoming freshmen need to enroll at SPUS?', 'What about transferees?', 'required documents for transferee'),
    ('faculty_chs', 'Who are the CEIT faculty?', 'How about CHS?', 'SPUS Faculty Directory | College of Health Sciences'),
    ('faculty_cbma_taglish', 'Who are the CEIT faculty?', 'Sa CBMA naman?', 'SPUS Faculty Directory | College of Business Management and Accountancy'),
)


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def main(repeats=20):
    if connection.vendor != 'postgresql':
        raise RuntimeError('Use the configured Docker PostgreSQL service.')
    from sentence_transformers import SentenceTransformer
    start = time.perf_counter()
    rag = RAGSearcher()
    rag.model = SentenceTransformer('all-MiniLM-L6-v2', local_files_only=True)
    model_ms = (time.perf_counter() - start) * 1000
    rag.ensure_embeddings = lambda: None
    report = {'repeats': repeats, 'mode': 'read-only; no LLM; warm paired retrieval',
              'model_load_ms_excluding_import': round(model_ms, 1), 'cases': [],
              'limitations': 'Six labeled positive cases in three families; not overall PAULA accuracy. Network, browser and provider time excluded.'}
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        vocabulary = rag.context_vocabulary()
        for name, previous, fragment, expected in CASES:
            history = [{'role':'user','content':previous}, {'role':'assistant','content':'Previously cited evidence.'}]
            record = {'case': name, 'previous':previous, 'fragment':fragment}
            for mode in ('baseline_fragment', 'contextual'):
                samples, rows = [], []
                for index in range(repeats + 1):
                    start = time.perf_counter()
                    plan = resolve_conversation(fragment, history, vocabulary) if mode == 'contextual' else None
                    query = plan.queries[0] if plan and plan.queries else fragment
                    rows = rag.search(query)
                    elapsed = (time.perf_counter() - start) * 1000
                    if index:
                        samples.append(elapsed)
                record[mode] = {'effective_query':query, 'expected_source_found':any(expected.casefold() in row['document_title'].casefold() for row in rows),
                                'source_count':len(rows), 'sources':[row['document_title'] for row in rows],
                                'p50_ms':round(statistics.median(samples), 2), 'p95_ms':round(percentile(samples, .95), 2)}
            report['cases'].append(record)
            print(json.dumps(record), flush=True)
        report['baseline_hits'] = sum(case['baseline_fragment']['expected_source_found'] for case in report['cases'])
        report['contextual_hits'] = sum(case['contextual']['expected_source_found'] for case in report['cases'])
        report['cutoff_unchanged'] = .45
    path = Path(__file__).resolve().parent.parent / 'PAULA_CONVERSATION_EVALUATION.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'baseline_hits':report['baseline_hits'],'contextual_hits':report['contextual_hits'],'cases':len(CASES),'output':str(path)}))


if __name__ == '__main__':
    main()
