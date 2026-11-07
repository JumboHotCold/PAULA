"""Live guest regression cases for compound overview/reason requests."""
import json
from pathlib import Path
import runpy
import time
from urllib.request import Request, urlopen
from uuid import uuid4

OVERVIEW = 'Sisters of St. Paul of Chartres'
BENEFIT = 'Faith-Based Education'
CASES = (
    ('TELL ME ABOUT SPUS AND WHY SHOULD I ENROL', (OVERVIEW, BENEFIT), 2),
    ('Tell me about SPUS and why should I enrol', (OVERVIEW, BENEFIT), 2),
    ('TELL ME ABOUT SPUS', (OVERVIEW,), 1),
    ('Why should I enroll at SPUS?', (BENEFIT,), 1),
    ('Tell me about SPUS and why should I choose it?', (OVERVIEW, BENEFIT), 2),
    ('WHAT IS SPUS AND WHY SHOULD I ENROLL?', (OVERVIEW, BENEFIT), 2),
    ('Tell me about SPUS and why should I study there?', (OVERVIEW, BENEFIT), 2),
    ('TELL ME ABOUT SPUS AND WHY SHOULD I ENROLL AT SPUS?', (OVERVIEW, BENEFIT), 2),
    ('What programs are offered?', ('Information Technology',), 1),
    ('Who is the ICT Director and CEIT Dean?', ('ICT',), 2),
    ('How do I enroll?', ('Are you enrolling',), 0),
)


def ask(query, context_id=None, history=None, token=None):
    payload = dict(message=query, mode='guest', context_id=context_id or str(uuid4()),
                   history=history or [], context_token=token)
    start = time.perf_counter()
    with urlopen(Request('http://127.0.0.1:8000/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}), timeout=25) as response:
        data = json.load(response)
        worker = response.headers.get('X-PAULA-Worker')
    assert not data['saved'] and data.get('conversation_id') is None
    return data, dict(query=query, ms=round((time.perf_counter()-start)*1000, 2), worker=worker,
                     response=data['response'], sources=data.get('sources', []))


rows = []
try:
    for query, expected, source_count in CASES:
        data, row = ask(query)
        assert all(fragment in data['response'] for fragment in expected), (query, data['response'])
        assert len(data.get('sources', [])) == source_count, (query, data['sources'])
        row['passed'] = True
        rows.append(row)
        print(json.dumps(dict(query=query, ms=row['ms'], sources=len(row['sources']), passed=True)), flush=True)

    for query in ('Tell me about SPUS and why should I enroll in 2037?',
                  'Tell me about SPUS and why should I enroll at UnknownXYZ Academy?'):
        data, row = ask(query)
        assert OVERVIEW in data['response'] and BENEFIT not in data['response']
        assert len(data['sources']) == 1
        rows.append(dict(row, passed=True, control='partial supported answer only'))
    data, row = ask('TELL ME ABOUT UNKNOWNXYZ')
    assert not data['sources'] and OVERVIEW not in data['response']
    rows.append(dict(row, passed=True, control='unknown acronym not ignored'))

    context_id, history, token = str(uuid4()), [], None
    for query, expected in (('Tell me about SPUS', OVERVIEW), ('Why should I enroll?', BENEFIT), ('How do I enroll?', 'Are you enrolling')):
        data, row = ask(query, context_id, history[-8:], token)
        assert expected in data['response'], (query, data['response'])
        rows.append(dict(row, passed=True, control='multi-turn'))
        token = data.get('context_token')
        history.extend([dict(role='user', content=query), dict(role='assistant', content=data['response'])])
    complete = True
finally:
    Path('PAULA_COMPOUND_REASON_AFTER.json').write_text(json.dumps(dict(complete=locals().get('complete', False), passed=len(rows), rows=rows), indent=2, ensure_ascii=False))

integrity_path = Path('PAULA_COMPOUND_REASON_INTEGRITY.json')
proof = json.loads(integrity_path.read_text())
proof['after'] = runpy.run_path('scripts/verify_csv_reference_integrity.py')['fingerprints']()
proof['unchanged'] = proof['before'] == proof['after']
integrity_path.write_text(json.dumps(proof, indent=2))
assert proof['unchanged'], 'Knowledge or history changed; inspect concurrent activity'
print(json.dumps(dict(passed=len(rows), data_unchanged=True)))
