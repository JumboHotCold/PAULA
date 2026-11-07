"""Guest-only live checks for source-backed About SPUS answers."""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from uuid import uuid4


CASES = (
    ('What is SPUS?', ('Sisters of St. Paul of Chartres',)),
    ('Tell me about SPUS', ('Sisters of St. Paul of Chartres',)),
    ('Ano ang SPUS?', ('Sisters of St. Paul of Chartres',)),
    ('What is the vision of SPUS?', ('Empowered Paulinians',)),
    ('What is the mission of SPUS?', ('Transformative Formation',)),
    ('What are the Paulinian core values?', ('Charism', 'Christ-Centered', 'Commission', 'Community', 'Charity')),
    ('What are the complete definitions of the Paulinian core values at SPUS?', ('The Paulinian develops', 'underprivileged')),
    ('Why choose SPUS?', ('Faith-Based Education', 'Academic Excellence')),
    ('why should i choose spus?', ('Faith-Based Education', 'Academic Excellence', 'Vibrant Campus Life', 'Global Alumni Network')),
    ('Why should we choose SPUS?', ('Faith-Based Education', 'Academic Excellence')),
    ('What are the two campuses of SPUS?', ('Luna', 'main campus')),
    ('What is the early history of SPUS?', ('1906', 'San Nicolas School')),
    ('What is the early history of SPUS and San Nicolas School?', ('1906', 'San Nicolas School')),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8080/api/chat')
    parser.add_argument('--output', default='PAULA_ABOUT_SPUS_LIVE_CHECKS.json')
    args = parser.parse_args()
    deadline = time.monotonic() + 240
    while True:
        try:
            with urllib.request.urlopen('http://127.0.0.1:8080/api/health/ready', timeout=3) as response:
                if json.load(response).get('ready'):
                    break
        except (OSError, urllib.error.URLError):
            pass
        if time.monotonic() > deadline:
            raise RuntimeError('Backend did not become ready')
        time.sleep(2)
    checks = []
    for query, expected in (*CASES, ('What is the 2030 SPUS enrollment deadline?', ())):
        request = urllib.request.Request(
            args.url,
            data=json.dumps({'message': query, 'mode': 'guest', 'context_id': str(uuid4())}).encode(),
            headers={'Content-Type': 'application/json'},
        )
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
        sources = data.get('sources', [])
        assert data.get('saved') is False and data.get('conversation_id') is None
        passed = bool(sources) and all(part.casefold() in data['response'].casefold() for part in expected)
        if not expected:
            passed = not sources and '2030' not in data['response']
        check = dict(query=query, url=args.url, passed=passed, elapsed_ms=round((time.perf_counter()-started)*1000, 2),
                     response=data['response'], sources=sources)
        checks.append(check)
        print(json.dumps({key: check[key] for key in ('query', 'passed', 'elapsed_ms')}), flush=True)
    Path(args.output).write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
    assert all(check['passed'] for check in checks), 'Some live checks failed; see the JSON report'


if __name__ == '__main__':
    main()
