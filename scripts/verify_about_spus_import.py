"""Apply the About SPUS import and prove old PostgreSQL rows were preserved."""
import hashlib
import json
from io import StringIO
from pathlib import Path
import runpy

from django.conf import settings
from django.core.management import call_command
from chatbot.models import FAQ


def main():
    root = Path(settings.BASE_DIR)
    audit = runpy.run_path(str(root / 'scripts/verify_csv_reference_integrity.py'))
    fingerprints = audit['fingerprints']
    encode = audit['encode']
    before = fingerprints()
    ids = list(FAQ.objects.order_by('pk').values_list('pk', flat=True))

    def existing_faq_hash():
        return hashlib.sha256(json.dumps(list(FAQ.objects.filter(pk__in=ids).order_by('pk').values()),
                                        sort_keys=True, default=encode).encode()).hexdigest()

    original_faqs = existing_faq_hash()
    call_command('ingest_about_spus', stdout=StringIO())
    report = json.loads((root / 'PAULA_ABOUT_SPUS_INGESTION.json').read_text(encoding='utf-8'))
    after = fingerprints()
    assert original_faqs == existing_faq_hash(), 'An existing FAQ changed'
    assert after['FAQ']['count'] == before['FAQ']['count'] + report['created']
    assert all(before[key] == after[key] for key in before if key != 'FAQ')
    for row in report['entries']:
        for pk in row['record_ids']:
            assert FAQ.objects.get(pk=pk).embedding is not None
    call_command('ingest_about_spus', report='PAULA_ABOUT_SPUS_REPEAT.json', stdout=StringIO())
    assert after == fingerprints(), 'Repeat import was not idempotent'
    proof = dict(before=before, after=after, existing_faqs_and_embeddings_unchanged=True,
                 other_knowledge_and_history_unchanged=True, repeat_import_created_zero_records=True,
                 created=report['created'], reused=report['reused'])
    (root / 'PAULA_ABOUT_SPUS_INTEGRITY.json').write_text(json.dumps(proof, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in proof.items() if key not in ('before', 'after')}))


if __name__ == '__main__':
    main()
