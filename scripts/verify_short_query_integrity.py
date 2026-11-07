"""Read-only PostgreSQL excerpt and full-row integrity verification."""
import json
from pathlib import Path
import runpy

from django.db import connection, transaction
from chatbot.grounding import render_evidence
from chatbot.models import FAQ, WebResource
from chatbot.personnel import structured_person, website_result


def main():
    path = Path('PAULA_SHORT_QUERY_INTEGRITY.json')
    report = json.loads(path.read_text(encoding='utf-8'))
    current = runpy.run_path('scripts/verify_csv_reference_integrity.py')['fingerprints']()
    assert current == report['before'], 'Knowledge, vectors or historical chat changed during checks'
    excerpts = []
    with transaction.atomic():
        assert connection.vendor == 'postgresql'
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        faqs, resources = list(FAQ.objects.all()), list(WebResource.objects.all())
        for row in json.loads(Path('PAULA_SHORT_QUERY_AFTER.json').read_text(encoding='utf-8')):
            for source in row['sources']:
                title = source['title']
                candidates = [dict(answer=faq.answer) for faq in faqs if f'FAQ ({faq.category}): {faq.question}' == title]
                candidates += [website_result(resource, structured_person(resource)) for resource in resources if resource.title == title]
                exact = any(render_evidence([candidate])[0] in row['response'] for candidate in candidates)
                assert exact, title
                excerpts.append(dict(title=title, exact=True))
    report.update(after=current, unchanged=True, cited_excerpts_checked=len(excerpts), exact_matches=len(excerpts), excerpts=excerpts,
                  limitation='Verbatim matching in synthetic live checks; not an independent institutional truth or freshness assessment')
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(unchanged=True, cited_excerpts_checked=len(excerpts), exact_matches=len(excerpts))))


if __name__ == '__main__':
    main()
