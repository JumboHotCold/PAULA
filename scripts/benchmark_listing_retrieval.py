"""Identical guest-query benchmark, no persistence. Run in Docker."""
import argparse
import json
import math
from pathlib import Path
import time
from urllib.request import Request, urlopen
from uuid import uuid4

CATALOG_CASES = (
    'What programs are offered?', 'What programs are offered at SPUS?',
    'Which courses are available?', 'What courses does SPUS offer?',
    'What are the available programs?', 'List programs', 'What progrms are offered?',
    'Anong mga kursong inaalok sa SPUS?', 'Ano ang mga programa na offered?',
    'Anong available na mga kurso sa SPUS?',
)
OTHER_CASES = ('What programs are offered at CEIT?', 'What scholarships are available?',
               'How do I enroll?', 'What programs are offered in 2037?',
               'What quantum teleportation degrees are offered?', 'Who is the ICT Director and CEIT Dean?')


def percentile(values, fraction):
    values = sorted(values)
    return values[max(0, math.ceil(len(values) * fraction) - 1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--rounds', default=3, type=int)
    args = parser.parse_args()
    rows = []
    for iteration in range(args.rounds):
        for query in CATALOG_CASES + OTHER_CASES:
            payload = dict(message=query, mode='guest', context_id=str(uuid4()))
            start = time.perf_counter()
            with urlopen(Request('http://127.0.0.1:8000/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}), timeout=25) as response:
                data = json.load(response)
                worker = response.headers.get('X-PAULA-Worker')
            assert not data['saved'] and data.get('conversation_id') is None
            catalog_success = bool(data.get('sources')) and all(fragment in data['response'] for fragment in ('Information Technology', 'Nursing', 'Criminology'))
            rows.append(dict(query=query, iteration=iteration, ms=round((time.perf_counter()-start)*1000, 2),
                catalog_case=query in CATALOG_CASES, catalog_success=catalog_success,
                response=data['response'], sources=data.get('sources', []), worker=worker))
        print(f'Completed round {iteration+1}/{args.rounds}', flush=True)
    catalog = [row for row in rows if row['catalog_case']]
    times = [row['ms'] for row in catalog]
    report = dict(rounds=args.rounds, samples=len(rows), catalog_successes=sum(row['catalog_success'] for row in catalog),
        catalog_samples=len(catalog), catalog_p50_ms=percentile(times, .5), catalog_p95_ms=percentile(times, .95), rows=rows,
        notes='Warm HTTP guest requests in one local Docker environment. Catalog checks measure stored-list retrieval, not independent institutional fact verification; other queries are recorded for regression review.')
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({key: value for key, value in report.items() if key not in ('rows', 'notes')}))


if __name__ == '__main__':
    main()
