"""Read-only PostgreSQL, FAQ lookup, vector and dependency audit."""
import importlib.metadata as metadata
import numpy as np
from django.conf import settings
from django.db import connection, transaction
from chatbot.models import FAQ, Location, StaffMember, WebResource
from chatbot.query_normalization import faq_question_key, normalized_text
from chatbot.rag import RAGSearcher


def audit():
    report = dict(database_vendor=connection.vendor, model_revision=settings.PAULA_EMBEDDING_REVISION,
                  cutoff=settings.RAG_MAX_COSINE_DISTANCE, debug=settings.DEBUG, models={}, faq_conflicts=[])
    assert connection.vendor == 'postgresql'
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
            cursor.execute('SHOW server_version')
            report['postgres_version'] = cursor.fetchone()[0]
            cursor.execute('SELECT extversion FROM pg_extension WHERE extname=%s', ['vector'])
            report['vector_extension'] = cursor.fetchone()[0]
        for model in (FAQ, Location, StaffMember, WebResource):
            rows = list(model.objects.all())
            missing = invalid = zero = 0
            for row in rows:
                if row.embedding is None:
                    missing += 1
                    continue
                vector = np.asarray(row.embedding)
                invalid += int(vector.shape != (384,) or not np.isfinite(vector).all())
                zero += int(np.linalg.norm(vector) < 1e-8)
            with connection.cursor() as cursor:
                cursor.execute('SELECT format_type(a.atttypid,a.atttypmod) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid WHERE c.relname=%s AND a.attname=%s', [model._meta.db_table, 'embedding'])
                column_type = cursor.fetchone()[0]
            report['models'][model.__name__] = dict(count=len(rows), missing_embeddings=missing,
                invalid_embeddings=invalid, zero_vectors=zero, column_type=column_type)
        faqs = list(FAQ.objects.all())
        groups = {}
        for row in faqs:
            groups.setdefault(faq_question_key(row.question), []).append(row)
        report['faq_conflicts'] = [dict(ids=[row.pk for row in group], question=group[0].question)
            for group in groups.values() if len({normalized_text(row.answer) for row in group}) > 1]
        statuses, failures = {}, []
        for row in faqs:
            result = RAGSearcher._exact_faq_lookup(row.question, faqs)
            statuses[result.status] = statuses.get(result.status, 0) + 1
            if not result:
                failures.append(dict(id=row.pk, question=row.question, status=result.status))
        report['faq_self_matches'] = statuses
        report['faq_self_match_failures'] = failures
    packages = ('Django', 'djangorestframework', 'django-unfold', 'pgvector', 'groq', 'torch',
                'sentence-transformers', 'transformers', 'whitenoise', 'numpy', 'opencv-python-headless', 'gunicorn')
    report['dependencies'] = {name: metadata.version(name) for name in packages}
    return report


