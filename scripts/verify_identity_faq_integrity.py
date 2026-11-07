"""Read-only source excerpt verification and PostgreSQL fingerprint comparison."""
import json
from pathlib import Path
import runpy

from django.db import connection, transaction
from chatbot.grounding import render_evidence
from chatbot.models import FAQ


def main():
    path = Path('PAULA_IDENTITY_FAQ_INTEGRITY.json')
    report = json.loads(path.read_text(encoding='utf-8'))
    current = runpy.run_path('scripts/verify_csv_reference_integrity.py')['fingerprints']()
    assert current == report['before'], 'Audited facts, vectors, or historical chats changed'
    checked = []
    with transaction.atomic():
        assert connection.vendor == 'postgresql'
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        records = list(FAQ.objects.all())
        for row in json.loads(Path('PAULA_IDENTITY_FAQ_AFTER.json').read_text(encoding='utf-8'))['checks']:
            for source in row['sources']:
                matches = [faq for faq in records if f'FAQ ({faq.category}): {faq.question}' == source['title']]
                assert any(render_evidence([dict(answer=faq.answer)])[0] in row['response'] for faq in matches), source['title']
                checked.append(dict(query=row['query'], source=source['title'], exact_excerpt=True))
    report.update(after=current, unchanged=True, checked_excerpts=len(checked), excerpt_checks=checked,
                  limitation='Cited excerpt preservation in synthetic checks; source truth/freshness is not independently established')
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(unchanged=True, checked_excerpts=len(checked))))


if __name__ == '__main__':
    main()
