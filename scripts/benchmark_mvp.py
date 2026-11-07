"""Repeatable live guest smoke matrix. Never writes accounts or chat history.

Run separately from unit tests. External providers may be called by the running
service; checks measure this scripted matrix, not independent factual accuracy.
"""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from uuid import uuid4

CASES = (
    ('ty', 'social', 'thanks'), ('thankyoui', 'social', 'thanks'),
    ('THANK YOU', 'social', 'thanks'), ('salamat kaayo', 'social', 'thanks'),
    ('who you?', 'social', 'identity'), ('tell me about yourself?', 'social', 'identity'),
    ('What programs are offered?', 'knowledge', 'Information Technology'),
    ('Tell me about SPUS', 'knowledge', 'Sisters of St. Paul of Chartres'),
    ('why spus?', 'knowledge', 'Faith-Based Education'),
    ('TELL ME ABOUT SPUS AND WHY SHOULD I ENROL', 'compound', 'Faith-Based Education'),
    ('Who is the university preseidnt?', 'knowledge', None),
    ('Who is the ICT Director and CEIT Dean?', 'compound', None),
    ('Who are the deans of CEIT and CHS?', 'compound', None),
    ('What are the requirements for freshmen and transferees?', 'compound', None),
    ('Where is the Registrar office?', 'navigation', 'registrar_office'),
    ('How are announcements and promotional materials broadcast across the SPUS campus?', 'knowledge', 'Unified Multimedia Communication Network'),
    ('What scholarships are available?', 'knowledge', None),
    ('What programs are offered? TY!!', 'knowledge', 'Information Technology'),
    ('What is the TY scholarship?', 'unsupported', None),
    ('Who is the SPUS President in 2037?', 'unsupported', None),
    ('What is quantum entanglement?', 'unsupported', None),
    ('Tell me about SPUS and why enroll at UnknownXYZ Academy?', 'partial', 'Sisters of St. Paul of Chartres'),
)
TURNS = (
    ('How do I enroll?', 'clarify', 'Are you enrolling'),
    ('Old/continuing college student', 'knowledge', 'URO-PR-016'),
    ('How about transferee?', 'knowledge', 'URO-PR-017'),
    ('Ano naman ang requirements?', 'knowledge', None),
    ('What programs are offered?', 'knowledge', 'Information Technology'),
    ('salamat kaayo', 'social', 'thanks'),
)


def percentile(values, q):
    return sorted(values)[math.ceil(len(values) * q) - 1] if values else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('before', 'after'), required=True)
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    rows = []
    for iteration in range(args.rounds):
        thread, history, token = str(uuid4()), [], None
        for index, (query, kind, expected) in enumerate(CASES + TURNS):
            continuity = index >= len(CASES)
            payload = dict(message=query, mode='guest', context_id=thread if continuity else str(uuid4()),
                           history=history[-8:] if continuity else [], context_token=token if continuity else None)
            started = time.perf_counter()
            row = dict(query=query, kind=kind, iteration=iteration, continuity=continuity)
            try:
                with urlopen(Request(args.base_url + '/api/chat', data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'}), timeout=30) as response:
                    data = json.load(response)
                    row.update(http_status=response.status, request_id=response.headers.get('X-Request-ID'),
                               worker=response.headers.get('X-PAULA-Worker'), server_timing=response.headers.get('Server-Timing'))
                text, sources = data.get('response', ''), data.get('sources', [])
                valid = bool(text) and data.get('saved') is False and data.get('conversation_id') is None
                if kind == 'social':
                    valid &= data.get('response_mode') == expected and not sources
                elif kind == 'unsupported':
                    valid &= not sources
                elif kind == 'navigation':
                    valid &= data.get('action') == 'navigate_map' and data.get('action_data', {}).get('destination') == expected
                elif kind == 'clarify':
                    valid &= bool(expected and expected in text) and not sources
                else:
                    valid &= bool(sources) and (expected is None or expected.casefold() in text.casefold())
                    if kind == 'compound':
                        valid &= len(sources) >= 2
                    if kind == 'partial':
                        valid &= len(sources) == 1 and 'Faith-Based Education' not in text
                row.update(passed=bool(valid), sources=sources, response=text, answer_status=data.get('answer_status'),
                           response_mode=data.get('response_mode'))
                if continuity:
                    token = data.get('context_token')
                    history.extend([dict(role='user', content=query), dict(role='assistant', content=text)])
            except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                row.update(passed=False, error_type=type(exc).__name__, http_status=getattr(exc, 'code', None))
            row['ms'] = round((time.perf_counter() - started) * 1000, 2)
            rows.append(row)
        print(f'Completed {args.phase} round {iteration + 1}/{args.rounds}', flush=True)
    groups = {}
    for kind in sorted({row['kind'] for row in rows}):
        group = [row for row in rows if row['kind'] == kind]
        values = [row['ms'] for row in group]
        groups[kind] = dict(samples=len(group), passed=sum(row['passed'] for row in group),
                            p50_ms=percentile(values, .5), p95_ms=percentile(values, .95))
    report = dict(phase=args.phase, measured_at=datetime.now(timezone.utc).isoformat(), base_url=args.base_url, samples=len(rows), passed=sum(row['passed'] for row in rows),
                  groups=groups, workers=sorted({row['worker'] for row in rows if row.get('worker')}), rows=rows,
                  limitation='Small sequential synthetic regression matrix, warm workers; not a load test or independent institutional fact review.')
    Path(f'PAULA_MVP_HTTP_{args.phase.upper()}.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key not in ('rows',)}))
    if args.phase == 'after' and report['passed'] != report['samples']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
