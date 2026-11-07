"""Public guest checks for short questions, typos, repair and source preservation."""
import json
from pathlib import Path
import time
import urllib.request
from uuid import uuid4


CASES = (
    ('why spus?', 'Faith-Based Education', 'knowledge', True),
    ('Why choose SPUS', 'Faith-Based Education', 'knowledge', True),
    ('wht is spus?', 'Sisters of St. Paul of Chartres', 'knowledge', True),
    ('helo', 'Hello', 'greeting', False),
    ('asdasdasd', 'rephrase', 'repair', False),
    ('who is the university preseidnt?', 'Marie Rosanne Mallillin', 'knowledge', True),
    ('why choos SPUS?', 'Faith-Based Education', 'knowledge', True),
    ('bakit SPUS?', 'Faith-Based Education', 'knowledge', True),
    ('What progrms are offered at SPUS?', 'Information Technology', 'knowledge', True),
    ('hwo do I enorll at SPUS?', 'Are you enrolling', 'knowledge', False),
    ('Wher is the registar?', 'Opening the campus map', 'knowledge', False),
    ('sorry typo', 'No worries', 'repair', False),
    ('???', 'No worries', 'repair', False),
    ('why SPUS in 2030?', 'verified information', 'knowledge', False),
)


def main():
    results = []
    for query, fragment, mode, sourced in CASES:
        request = urllib.request.Request('http://localhost:5173/api/chat', headers={'Content-Type': 'application/json'},
            data=json.dumps(dict(message=query, mode='guest', context_id=str(uuid4()))).encode())
        start = time.perf_counter()
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.load(response)
            request_id = response.headers.get('X-Request-ID')
        assert not data['saved'] and data['conversation_id'] is None
        assert fragment.casefold() in data['response'].casefold(), (query, data)
        assert data['response_mode'] == mode, (query, data)
        assert bool(data['sources']) == sourced, (query, data)
        results.append(dict(query=query, ms=round((time.perf_counter()-start)*1000, 2), response=data['response'],
                            sources=data['sources'], mode=data['response_mode'], request_id=request_id, passed=True))
        print(json.dumps({key: results[-1][key] for key in ('query', 'ms', 'mode', 'passed')}), flush=True)

    thread, token, history = str(uuid4()), None, []
    for query, expected in (('How do I enroll?', 'Are you enrolling'), ('sorry typo', 'No worries'),
                            ('asdasdasd', 'rephrase'), ('I am a transferee', 'URO-PR-017')):
        request = urllib.request.Request('http://localhost:5173/api/chat', headers={'Content-Type': 'application/json'},
            data=json.dumps(dict(message=query, mode='guest', context_id=thread, context_token=token, history=history)).encode())
        start = time.perf_counter()
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.load(response)
        assert expected in data['response'], (query, data)
        assert not data['saved'] and data['conversation_id'] is None
        results.append(dict(query=query, context_sequence=True, ms=round((time.perf_counter()-start)*1000, 2),
            response=data['response'], sources=data['sources'], mode=data['response_mode'], passed=True))
        token = data.get('context_token')
        history.extend([dict(role='user', content=query), dict(role='assistant', content=data['response'])])
        history = history[-8:]
    Path('PAULA_SHORT_QUERY_AFTER.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(dict(passed=len(results))))


if __name__ == '__main__':
    main()
