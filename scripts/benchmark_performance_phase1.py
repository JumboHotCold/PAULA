"""Identical guest-only before/after HTTP corpus; no chat-history writes."""
import argparse
import json
import math
from pathlib import Path
import statistics
import time
import urllib.request
import uuid


CASES = (
    ('personnel', 'Who is the ICT Director?', ('Arnold A. Magalona',)),
    ('structured_compound', 'Who is the ICT Director and CEIT Dean?', ('Arnold A. Magalona', 'Karen T. Plaza')),
    ('enrollment', 'What are the requirements for freshmen and transferees?', ('Freshmen', 'Transferee')),
    ('semantic_calendar', 'What is the school calendar?', ('semester',)),
    ('scholarships', 'What scholarships are available?', ()),
    ('policy', 'What is the SPUS Quality Policy?', ()),
    ('semantic_compound', 'What scholarships are available, and what is the school calendar?', ('semester',)),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--samples', type=int, default=20)
    parser.add_argument('--url', default='http://localhost:5173/api/chat')
    parser.add_argument('--interval', type=float, default=0, help='Diagnostic pacing between requests; not included in latency')
    parser.add_argument('--selector-interval', type=float, default=0, help='Extra diagnostic pacing for selector cases to respect free-tier token limits')
    args = parser.parse_args()
    checks = []
    for name, query, expected in CASES:
        samples, initial, workers, traces, outcomes = [], [], set(), [], []
        for index in range(args.samples + 2):
            payload = {'message': query, 'mode': 'guest', 'context_id': str(uuid.uuid4())}
            request = urllib.request.Request(args.url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
            start = time.perf_counter()
            with urllib.request.urlopen(request, timeout=120) as response:
                first = time.perf_counter()
                data = json.load(response)
                headers = {key.lower(): value for key, value in response.headers.items()}
            elapsed = (time.perf_counter() - start) * 1000
            assert data.get('saved') is False and data.get('conversation_id') is None
            assert all(fragment.casefold() in data['response'].casefold() for fragment in expected), (name, data)
            record = {'elapsed_ms': round(elapsed, 2), 'ttfb_ms': round((first-start)*1000, 2),
                      'worker': headers.get('x-paula-worker'), 'request_id': headers.get('x-request-id'),
                      'server_timing': headers.get('server-timing')}
            (initial if index < 2 else samples).append(record)
            if record['worker']:
                workers.add(record['worker'])
            outcomes.append({'source_count': len(data.get('sources', [])),
                             'parts': [part['status'] for part in data.get('answer_parts', [])]})
            pause = max(args.interval, args.selector_interval if name in ('scholarships', 'policy', 'semantic_compound') else 0)
            if pause > 0:
                time.sleep(pause)
        durations = sorted(row['elapsed_ms'] for row in samples)
        row = {'case': name, 'query': query, 'n': len(samples), 'p50_ms': round(statistics.median(durations), 2),
               'p95_ms': durations[math.ceil(.95*len(durations))-1], 'max_ms': max(durations),
               'initial': initial, 'samples': samples, 'workers': sorted(workers), 'outcomes': outcomes,
               'last_response': data['response'], 'last_sources': data.get('sources', [])}
        checks.append(row)
        print(json.dumps({key: row[key] for key in ('case', 'n', 'p50_ms', 'p95_ms', 'workers')}), flush=True)
    report = {'samples_per_case': args.samples, 'url': args.url, 'interval_seconds': args.interval,
              'selector_interval_seconds': args.selector_interval, 'checks': checks,
              'notes': 'Sequential local guest HTTP pilot; first two samples separated, not proof all workers were warm. '
                       'No browser React paint time. Sources are existing stored snapshots; unsupported answers are recorded, not invented.'}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
