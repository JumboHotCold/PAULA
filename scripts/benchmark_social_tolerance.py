"""Identical before/after guest intent requests, no accounts or history writes."""
import argparse
import json
import math
from pathlib import Path
import time
from urllib.request import Request, urlopen
from uuid import uuid4

CASES = (
    ('ty', 'thanks'), ('thankyoui', 'thanks'), ('thank you', 'thanks'), ('THANK YOU', 'thanks'),
    ('ThAnK YoU', 'thanks'), ('thx', 'thanks'), ('tnx', 'thanks'), ('tq', 'thanks'),
    ('TYSM PAULA!!', 'thanks'), ('thnak you', 'thanks'), ('thnks', 'thanks'), ('thankss', 'thanks'),
    ('thankyou', 'thanks'), ('thank   you', 'thanks'), ('thanks!!!', 'thanks'),
    ('goodmorning', 'greeting'), ('howareyou', 'wellbeing'), ('salamat kaayo', 'thanks'),
    ('daghang salamat', 'thanks'), ('yes', 'affirmation'), ('no', 'negation'),
    ('okay', 'acknowledgement'), ('sure', 'affirmation'), ('dili', 'negation'),
    ('help', 'capabilities'), ('explain', 'clarification'), ('bye', 'farewell'),
)
CONTROLS = ('ty, who is the ICT Director?', 'What programs are offered? TY!!',
            'TELL ME ABOUT SPUS AND WHY SHOULD I ENROL', 'Where is the Registrar office?',
            'What is the TY scholarship?', 'Who handles thank you cards without fees in 2037?')


def percentile(values, ratio):
    return sorted(values)[math.ceil(len(values) * ratio) - 1]


args = argparse.ArgumentParser()
args.add_argument('--phase', choices=('before', 'after'), required=True)
args.add_argument('--rounds', type=int, default=3)
options = args.parse_args()
rows = []
complete = False
try:
    for iteration in range(options.rounds):
        for query, expected in CASES + tuple((query, 'knowledge') for query in CONTROLS):
            start = time.perf_counter()
            with urlopen(Request('http://127.0.0.1:8000/api/chat', data=json.dumps(dict(message=query, mode='guest', context_id=str(uuid4()))).encode(), headers={'Content-Type': 'application/json'}), timeout=25) as response:
                data = json.load(response)
                request_id = response.headers.get('X-Request-ID')
                worker = response.headers.get('X-PAULA-Worker')
            assert not data['saved'] and data.get('conversation_id') is None
            passed = data.get('response_mode') == expected if expected != 'knowledge' else data.get('response_mode') in ('knowledge', 'mixed')
            rows.append(dict(query=query, iteration=iteration, ms=round((time.perf_counter()-start)*1000, 2),
                expected=expected, actual=data.get('response_mode'), passed=passed, response=data['response'],
                sources=data.get('sources', []), action=data.get('action'), action_data=data.get('action_data'), request_id=request_id, worker=worker))
            if options.phase == 'after' and query in CONTROLS:
                if query in CONTROLS[:3]:
                    assert data['sources'], (query, data)
                elif query == CONTROLS[3]:
                    assert data.get('action') == 'navigate_map' and data.get('action_data', {}).get('destination') == 'registrar_office'
                else:
                    assert not data['sources'], (query, data)
        print(f'Completed {options.phase} round {iteration+1}/{options.rounds}', flush=True)
    if options.phase == 'after':
        assert all(row['passed'] for row in rows), [(row['query'], row['actual']) for row in rows if not row['passed']]
    complete = True
finally:
    social = [row for row in rows if row['expected'] != 'knowledge']
    times = [row['ms'] for row in social]
    report = dict(phase=options.phase, complete=complete, samples=len(rows),
        social_successes=sum(row['passed'] for row in social), social_samples=len(social),
        social_p50_ms=percentile(times, .5) if times else None, social_p95_ms=percentile(times, .95) if times else None,
        controls_passed=sum(row['passed'] for row in rows if row['expected'] == 'knowledge'), rows=rows,
        notes='Small, sequential developer regression matrix. Warm HTTP latency, no concurrency/load or independent-language-accuracy claim.')
    Path(f'PAULA_SOCIAL_TOLERANCE_{options.phase.upper()}_BENCHMARK.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({key: value for key, value in report.items() if key not in ('rows', 'notes')}))
