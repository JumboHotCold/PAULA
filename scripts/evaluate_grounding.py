"""Read-only retrieval smoke evaluation against the configured PostgreSQL DB.

Run via the Docker web service only. Uses cached embeddings/model, refuses
SQLite, disables embedding writes, and enforces a read-only DB transaction.
Does not call LLM providers. This is not a labeled accuracy benchmark.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paulibot.settings')
os.environ['HF_HUB_OFFLINE'] = '1'

import django
django.setup()

from django.db import connection, transaction
from sentence_transformers import SentenceTransformer
from chatbot.models import FAQ, Location, StaffMember, WebResource
from chatbot.rag import RAGSearcher


def main():
    if connection.vendor != 'postgresql':
        raise RuntimeError('Evaluation requires the configured Docker PostgreSQL database.')
    rag = RAGSearcher.__new__(RAGSearcher)
    rag.model = SentenceTransformer('all-MiniLM-L6-v2', local_files_only=True)
    rag.ensure_embeddings = lambda: None
    queries = (
        'who are the CEIT faculty lineup',
        'Sino ang mga guro sa CEIT?',
        'What programs are offered at SPUS?',
        'Does SPUS offer scholarships?',
        'How much is the tuition fee?',
        'How do incoming freshmen enroll at SPUS?',
        'What are the PBMO office hours?',
        'What is the school calendar?',
        'What are the exact enrollment dates for 2099?',
        'Who is the president of Mars?',
    )
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        print(json.dumps({'missing_embeddings': {
            model.__name__: model.objects.filter(embedding__isnull=True).count()
            for model in (FAQ, Location, StaffMember, WebResource)}}))
        for query in queries:
            results = rag.search(query)
            print(json.dumps({'query': query, 'accepted': [
                {'title': row['document_title'], 'cosine_distance': round(row['distance'], 4)}
                for row in results]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
