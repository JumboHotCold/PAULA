"""Validate actual benchmark results, multi-turn grounding, and data integrity."""
import json
from pathlib import Path
import runpy
from urllib.request import Request, urlopen
from uuid import uuid4


before = json.loads(Path('PAULA_LISTING_BENCHMARK_BEFORE.json').read_text())
after = json.loads(Path('PAULA_LISTING_BENCHMARK_AFTER.json').read_text())
assert after['catalog_successes'] == after['catalog_samples']
for row in after['rows']:
    query, text, sources = row['query'], row['response'], row['sources']
    if query == 'What programs are offered at CEIT?':
        assert sources and 'INFORMATION TECHNOLOGY' in text.upper() and 'NURSING' not in text.upper()
    elif query in ('What programs are offered in 2037?', 'What quantum teleportation degrees are offered?'):
        assert not sources and 'verified information' in text
    elif query == 'How do I enroll?':
        assert not sources and 'Are you enrolling' in text
    elif query == 'What scholarships are available?':
        assert sources and 'scholarship' in text.casefold()
    elif query == 'Who is the ICT Director and CEIT Dean?':
        assert len(sources) >= 2

history, token, context_id, conversation = [], None, str(uuid4()), []
for query, expected in (
        ('What programs are offered at CEIT?', 'INFORMATION TECHNOLOGY'),
        ('How about CHS?', 'NURSING'),
        ('How do I enroll?', 'ARE YOU ENROLLING')):
    payload = dict(message=query, mode='guest', context_id=context_id, context_token=token, history=history[-8:])
    with urlopen(Request('http://127.0.0.1:8000/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}), timeout=20) as response:
        data = json.load(response)
    assert expected in data['response'].upper(), (query, data['response'])
    assert not data['saved'] and data.get('conversation_id') is None
    if query == 'How about CHS?':
        assert 'MINING ENGINEERING' not in data['response'].upper()
    conversation.append(dict(query=query, response=data['response'], sources=data['sources'], passed=True))
    token = data.get('context_token')
    history.extend([dict(role='user', content=query), dict(role='assistant', content=data['response'])])

integrity_path = Path('PAULA_LISTING_DATA_INTEGRITY.json')
integrity = json.loads(integrity_path.read_text())
integrity['after'] = runpy.run_path('scripts/verify_csv_reference_integrity.py')['fingerprints']()
integrity['unchanged'] = integrity['before'] == integrity['after']
integrity_path.write_text(json.dumps(integrity, indent=2))
assert integrity['unchanged'], 'Knowledge or history changed; inspect concurrent activity before attributing changes'
report = dict(before={key: before[key] for key in ('catalog_successes', 'catalog_samples', 'catalog_p50_ms', 'catalog_p95_ms')},
              after={key: after[key] for key in ('catalog_successes', 'catalog_samples', 'catalog_p50_ms', 'catalog_p95_ms')},
              other_benchmark_controls_passed=True, multi_turn=conversation, data_unchanged=True,
              notes='Representative local warm-request measurements, not a general accuracy estimate or production latency guarantee. All factual text comes from stored sources.')
Path('PAULA_LISTING_RETRIEVAL_VERIFICATION.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
print(json.dumps({key: report[key] for key in ('before', 'after', 'other_benchmark_controls_passed', 'data_unchanged')}))
