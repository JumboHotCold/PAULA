"""Verify repeatable CSV review and unchanged PostgreSQL facts/history.

Run through Docker's Django shell. Only the two JSON audit artifacts are written.
"""
import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connection, transaction

from chatbot.models import FAQ, StaffMember, WebResource, Conversation, ChatHistory


def encode(value):
    if hasattr(value, 'tolist'):
        return value.tolist()
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def fingerprints():
    assert connection.vendor == 'postgresql'
    result = {}
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        for model in (StaffMember, FAQ, WebResource, Conversation, ChatHistory):
            rows = list(model.objects.order_by('pk').values())
            result[model.__name__] = {
                'count': len(rows),
                'sha256': hashlib.sha256(json.dumps(rows, sort_keys=True, default=encode).encode()).hexdigest(),
            }
    return result


def main():
    root = Path(settings.BASE_DIR)
    output = root / 'PAULA_PERSONNEL_CSV_DRY_RUN.json'
    proof = root / 'PAULA_CSV_INTEGRITY_CHECK.json'
    prior = json.loads(proof.read_text(encoding='utf-8')) if proof.exists() else None
    before = fingerprints()
    call_command('audit_personnel_csv', output=output.name)
    first = output.read_bytes()
    call_command('audit_personnel_csv', output=output.name)
    assert output.read_bytes() == first, 'Audit output was not repeatable'
    after = fingerprints()
    assert before == after, 'Knowledge or conversation data changed during audit'
    knowledge = {key: after[key] for key in ('StaffMember', 'FAQ', 'WebResource')}
    if prior:
        assert prior['knowledge_fingerprints'] == knowledge, 'Earlier knowledge snapshot changed'
    audit = json.loads(first)
    directory = root / audit['directory']
    for item in audit['files']:
        assert hashlib.sha256((directory / item['file']).read_bytes()).hexdigest() == item['sha256']
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        khen = StaffMember.objects.filter(name='Khen Malaque', position='JSIT Moderator').exists()
        retired = StaffMember.objects.filter(name__icontains='Zotomayor').count()
    report = {
        'knowledge_fingerprints': knowledge,
        'facts_and_embeddings_unchanged': True,
        'history_unchanged_during_audit': True,
        'history_fingerprints': {key: after[key] for key in ('Conversation', 'ChatHistory')},
        'idempotent_report': True,
        'source_csv_hashes_match': True,
        'csv_database_writes': 0,
        'conversations': after['Conversation']['count'],
        'messages': after['ChatHistory']['count'],
        'khen_jsit_preserved': khen,
        'retired_staff_count': retired,
    }
    assert khen and retired == 0
    proof.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if 'fingerprints' not in key}))


if __name__ == '__main__':
    main()
