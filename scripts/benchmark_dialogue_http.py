"""Public synthetic, guest-only before/after samples; no account or DB writes."""
import argparse
import json
import math
from pathlib import Path
import time
import urllib.request
from uuid import uuid4


CASES = (
    ('social', 'Hello'), ('social', 'Okay'), ('social', 'How are you?'),
    ('social', 'Thank you'), ('social', 'Can you tell me a short joke?'),
    ('social', 'Kumusta ka?'), ('social', 'I feel nervous today'),
    ('social', 'What do you do for fun?'),
    ('mixed', 'Hi! Who is the ICT Director?'),
    ('knowledge', 'Who is the ICT Director and CEIT Dean?'),
    ('knowledge', 'Why should I choose SPUS?'),
    ('knowledge', 'How do I enroll at SPUS?'),
)


def summary(values):
    ordered = sorted(values)
    return dict(n=len(values), p50_ms=round(ordered[math.ceil(.5*len(values))-1], 2),
                p95_ms=round(ordered[math.ceil(.95*len(values))-1], 2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=('before', 'after'), required=True)
    parser.add_argument('--url', default='http://127.0.0.1:8080/api/chat')
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    results = []
    for repeat in range(args.repeats):
        for category, query in CASES:
            started = time.perf_counter()
            request = urllib.request.Request(args.url, headers={'Content-Type': 'application/json'},
                data=json.dumps(dict(message=query, mode='guest', context_id=str(uuid4()))).encode())
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.load(response)
                headers = {key: response.headers.get(key) for key in ('X-Request-ID', 'X-PAULA-Worker', 'Server-Timing')}
            elapsed = round((time.perf_counter()-started)*1000, 2)
            assert data.get('saved') is False and data.get('conversation_id') is None
            results.append(dict(category=category, query=query, repeat=repeat, elapsed_ms=elapsed,
                response=data['response'], sources=data.get('sources', []), mode=data.get('response_mode'), headers=headers))
            print(json.dumps(dict(query=query, elapsed_ms=elapsed, mode=data.get('response_mode'))), flush=True)
    report = dict(phase=args.phase, url=args.url, percentiles='nearest rank; small sequential sample, not a load test',
        groups={category: summary([row['elapsed_ms'] for row in results if row['category'] == category])
                for category in ('social', 'mixed', 'knowledge')}, results=results)
    Path(f'PAULA_DIALOGUE_{args.phase.upper()}.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
