"""Live guest conversational checks through the same Vite proxy as React."""
import json
from pathlib import Path
import time
import urllib.request
from uuid import uuid4


def main():
    checks = []
    thread, token, history = str(uuid4()), None, []

    def ask(query, expected=(), mode=None, context_id=None, use_history=True):
        nonlocal token
        request = urllib.request.Request('http://localhost:5173/api/chat',
            headers={'Content-Type': 'application/json'}, data=json.dumps(dict(
                message=query, mode='guest', context_id=context_id or thread, context_token=token,
                history=history[-8:] if use_history else [])).encode())
        start = time.perf_counter()
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
            worker = response.headers.get('X-PAULA-Worker')
        assert data['saved'] is False and data['conversation_id'] is None
        assert all(text.casefold() in data['response'].casefold() for text in expected), (query, data['response'])
        if mode:
            assert data['response_mode'] == mode, (query, data['response_mode'])
        checks.append(dict(query=query, passed=True, mode=data['response_mode'],
                           elapsed_ms=round((time.perf_counter()-start)*1000, 2), worker=worker,
                           response=data['response'], sources=data['sources'], action=data.get('action')))
        print(json.dumps({key: checks[-1][key] for key in ('query', 'passed', 'mode', 'elapsed_ms')}), flush=True)
        token = data.get('context_token')
        history.extend([dict(role='user', content=query), dict(role='assistant', content=data['response'])])
        return data

    ask('Hello, PAULA!', ('PAULA',), 'greeting')
    ask('Okay', ('Got it',), 'acknowledgement')
    ask('How are you doing today?', mode='wellbeing')
    ask('How do I enroll at SPUS?', ('Are you enrolling',))
    ask('Thank you', mode='thanks')
    ask('I feel nervous today', mode='support')
    ask('Taglish please', ('Taglish',), 'language')
    ask('Okay', ('Sige',), 'acknowledgement')
    # The first clarification pair is now outside the bounded history window.
    result = ask('I am a transferee', ('URO-PR-017',))
    assert result['sources']
    ask('How about old students?', ('URO-PR-016',))
    ask('English please', ('English',), 'language')
    ask('Hi! Who is the ICT Director and CEIT Dean?', ('Arnold A. Magalona', 'Karen T. Plaza'), 'mixed')
    ask('Thank you', mode='thanks')
    ask('How about CHS?', ('Kristal Liza Besario',))
    result = ask('Where is the Registrar office?')
    assert result['action'] == 'navigate_map'
    # Start a separate thread, dropping history and attempting to replay token.
    result = ask('How about CHS?', context_id=str(uuid4()), use_history=False)
    assert not result['sources']
    history.clear()
    token = None
    ask('Could you make me laugh?', mode='joke')
    ask('What kind of music do you enjoy?', mode='preference')
    ask('Maraming salamat po!', mode='thanks')
    ask('Bye po!', mode='farewell')
    Path('PAULA_DIALOGUE_LIVE_CHECKS.json').write_text(json.dumps(dict(passed=len(checks), checks=checks), ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
