"""Replay the reported guest conversation and inspect follow-up recommendations."""
import argparse
import json
from pathlib import Path
import re
import time
import urllib.request
from uuid import uuid4


def controls(text):
    match = re.search(r'\[SUGGESTIONS:\s*(.*?)\]', text, re.S)
    return json.loads('[' + match.group(1).replace(' | ', ',') + ']') if match else []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['before', 'after'], default='after')
    parser.add_argument('--url', default='http://localhost:5173/api/chat')
    args = parser.parse_args()
    deadline = time.monotonic() + 300
    while True:
        try:
            with urllib.request.urlopen('http://127.0.0.1:8080/api/health/ready', timeout=3) as response:
                if json.load(response).get('ready'):
                    break
        except OSError:
            pass
        if time.monotonic() > deadline:
            raise RuntimeError('Backend not ready')
        time.sleep(2)
    context_id, token, history, asked, checks = str(uuid4()), None, [], [], []

    def send(query, expected_choice=False):
        nonlocal token
        request = urllib.request.Request(args.url, headers={'Content-Type': 'application/json'}, data=json.dumps(dict(
            message=query, mode='guest', context_id=context_id, context_token=token,
            history=history[-8:], asked_questions=asked[-64:])).encode())
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
            request_id = response.headers.get('X-Request-ID')
        elapsed = round((time.perf_counter()-started)*1000, 2)
        assert data.get('saved') is False and data.get('conversation_id') is None
        suggestions = data.get('suggestions', controls(data['response']))
        if args.phase == 'after':
            assert isinstance(suggestions, list) and len(suggestions) <= 3
            assert suggestions == controls(data['response'])
            assert (data.get('suggestions_kind') == 'choice') == expected_choice
            if not expected_choice:
                assert not (set(s.casefold() for s in suggestions) & set(s.casefold() for s in (*asked, query)))
            assert data.get('sources') or expected_choice or data.get('action'), data['response']
        checks.append(dict(query=query, request_id=request_id, elapsed_ms=elapsed,
                           suggestions=suggestions, kind=data.get('suggestions_kind'),
                           source_titles=[source['title'] for source in data.get('sources', [])],
                           response=data['response']))
        print(json.dumps({key: checks[-1][key] for key in ('query', 'elapsed_ms', 'suggestions', 'kind')}, ensure_ascii=True), flush=True)
        token = data.get('context_token')
        history.extend([dict(role='user', content=query), dict(role='assistant', content=data['response'])])
        asked.append(query)
        return suggestions

    for query, choice in (
            ('Tell me about SPUS?', False), ('why should i choose SPUS?', False),
            ('What programs are offered at SPUS?', False), ('How do I enroll at SPUS?', True),
            ('Transferee student', False)):
        choices = send(query, choice)
    if args.phase == 'after':
        assert len({tuple(row['suggestions']) for row in checks if row['kind'] == 'related'}) > 1
        assert not any('college courses' in question.lower() for question in checks[2]['suggestions'])
        # Follow one advertised question to verify that this isn't merely a
        # carousel of labels. The current catalog can offer another audience's
        # procedure, so allow a legitimate enrollment clarification if requested.
        if choices:
            send(choices[0])
    Path(f'PAULA_SUGGESTIONS_{args.phase.upper()}.json').write_text(
        json.dumps(dict(url=args.url, phase=args.phase, checks=checks), ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
