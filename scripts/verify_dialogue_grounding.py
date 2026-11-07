"""Verify cited excerpts in public synthetic HTTP artifacts against PostgreSQL.

This measures extractive preservation, not truth/currentness of source records
or exhaustive answer relevance. No LLM judging, embeddings, or database writes.
"""
import json
from pathlib import Path
import re

from django.db import connection, transaction
from chatbot.grounding import render_evidence
from chatbot.models import FAQ, StaffMember, WebResource
from chatbot.personnel import structured_person, website_result


def main():
    checks = []
    assert connection.vendor == 'postgresql'
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        faqs = list(FAQ.objects.all())
        resources = list(WebResource.objects.all())
        staff = list(StaffMember.objects.all())
        for filename in ('PAULA_DIALOGUE_LIVE_CHECKS.json', 'PAULA_ABOUT_SPUS_DIALOGUE_CHECKS.json', 'PAULA_COMPOUND_LIVE_CHECKS.json'):
            content = json.loads(Path(filename).read_text(encoding='utf-8'))
            rows = content.get('checks', []) if isinstance(content, dict) else content
            for check in rows:
                response = check['response']
                for source in check.get('sources', []):
                    if source.get('source_type') == 'campus_map':
                        continue  # Map directory is tested separately.
                    title = source['title']
                    candidates = [dict(answer=row.answer) for row in faqs if f'FAQ ({row.category}): {row.question}' == title]
                    candidates += [website_result(row, structured_person(row)) for row in resources if row.title == title]
                    for row in staff:
                        if title == f'Staff Directory: {row.position}':
                            text = f'{row.name} is the {row.position}.'
                            if row.office:
                                text += f' Office located at {row.office}.'
                            candidates.append(dict(answer=text))
                    exact = any(render_evidence([candidate])[0] in response for candidate in candidates)
                    checks.append(dict(artifact=filename, title=title, exact_excerpt_present=exact))
                    assert exact, (filename, title)
    report = dict(cited_excerpts=len(checks), exact_matches=sum(row['exact_excerpt_present'] for row in checks), checks=checks,
                  limitation='Verbatim preservation of cited knowledge in these cases; not a universal factual accuracy or freshness score')
    Path('PAULA_DIALOGUE_GROUNDING.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'checks'}))


if __name__ == '__main__':
    main()
