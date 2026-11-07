"""Public synthetic guest checks through Vite, including every offered click."""
import json
from pathlib import Path
import time
import urllib.request
from uuid import uuid4


PBMO = 'How are announcements and promotional materials broadcast across the SPUS campus?'
STARTERS = ['What programs are offered at SPUS?', 'How do I enroll at SPUS?', 'Where is the Registrar office?']


def main():
    checks = []

    def ask(query, state=None):
        state = state if state is not None else dict(thread=str(uuid4()), token=None, history=[], asked=[])
        request = urllib.request.Request('http://localhost:5173/api/chat', headers={'Content-Type': 'application/json'},
            data=json.dumps(dict(message=query, mode='guest', context_id=state['thread'], context_token=state['token'],
                                 history=state['history'][-8:], asked_questions=state['asked'][-64:])).encode())
        start = time.perf_counter()
        with urllib.request.urlopen(request, timeout=25) as response:
            data = json.load(response)
        assert data['saved'] is False and data['conversation_id'] is None
        questions = data.get('suggestions', [])
        assert len(questions) <= 3
        if data.get('suggestions_kind') != 'choice':
            assert all(len(question) <= 110 for question in questions)
        checks.append(dict(query=query, elapsed_ms=round((time.perf_counter()-start)*1000, 2),
            response=data['response'], sources=data['sources'], suggestions=questions,
            kind=data.get('suggestions_kind'), mode=data.get('response_mode'), action=data.get('action'), passed=True))
        state['token'] = data.get('context_token')
        state['history'].extend([dict(role='user', content=query), dict(role='assistant', content=data['response'])])
        state['asked'].append(query)
        print(json.dumps({key: checks[-1][key] for key in ('query', 'elapsed_ms', 'suggestions', 'mode')}), flush=True)
        return data

    for query in ('who you?', 'tell me about yourself?', 'Hi! Who you?', 'What is your purpose?', 'Pakilala ka naman'):
        data = ask(query)
        assert data['response_mode'] == 'identity'
        assert 'Paulinian Artificial User Support and Learning Assistant' in data['response']
        assert not data['sources']
        assert data['suggestions'] == STARTERS

    thread = dict(thread=str(uuid4()), token=None, history=[], asked=[])
    intro = ask('Who are you?', thread)
    for query in intro['suggestions']:
        data = ask(query, thread)
        assert data['sources'] or data.get('action') or data.get('suggestions_kind') == 'choice', data
    data = ask('Old/continuing college student', thread)
    assert 'URO-PR-016' in data['response']
    again = ask('Tell me about yourself', thread)
    assert again['suggestions'] == [], 'Used entry points were repeated'

    related_count = 0
    for query in (PBMO, 'What programs are offered at SPUS?', 'Tell me about SPUS', 'How do I enroll as a transferee?'):
        data = ask(query)
        assert data['sources'], (query, data)
        if query == PBMO:
            assert 'Unified Multimedia Communication Network' in data['response']
            assert all(source.get('source_office') == 'PBMO' for source in data['sources'])
            assert not any(question in STARTERS for question in data['suggestions'])
        for suggested in data['suggestions']:
            target = ask(suggested)
            assert target['sources'] or target.get('action') or target.get('suggestions_kind') == 'choice', (suggested, target)
            related_count += 1

    unknown = ask('What is quantum entanglement?')
    assert not unknown['sources'] and not unknown['suggestions']
    Path('PAULA_IDENTITY_FAQ_AFTER.json').write_text(json.dumps(dict(passed=len(checks),
        related_clicks=related_count, checks=checks), ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(passed=len(checks), related_clicks=related_count)))


if __name__ == '__main__':
    main()
