"""Guest multi-turn smoke checks through the actual Vite proxy; standard library."""
import json
from pathlib import Path
import time
import urllib.request

BASE_URL = 'http://localhost:5173/api/chat'


def main():
    checks = []

    def ask(text, history, expected=None, action=None, destination=None, no_sources=False):
        token = history[-1].get('context_token') if history else None
        request = urllib.request.Request(BASE_URL, data=json.dumps({'message':text,'history':history[-8:],
                                         'context_id':'live-test-tab', 'context_token':token}).encode(),
                                         headers={'Content-Type':'application/json'})
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.load(response)
        assert data['saved'] is False, 'Guest chat must not be persisted'
        if expected:
            assert expected in data['response'], (text, data)
        if action:
            assert data['action'] == action, (text,data)
        if destination:
            assert data['action_data']['destination'] == destination, (text,data)
        if no_sources:
            assert not data['sources'], (text,data)
        checks.append({'message':text,'passed':True,'elapsed_ms':round((time.perf_counter()-started)*1000,1),
                       'response':data['response'],'sources':data['sources'],'action':data['action']})
        history += [{'role':'user','content':text,'timestamp':time.time()},
                    {'role':'assistant','content':data['response'],'timestamp':time.time(),'context_token':data.get('context_token')}]
        history[:] = history[-8:]
        print(json.dumps({key:checks[-1][key] for key in ('message','passed','elapsed_ms')}), flush=True)
        return data

    history = []
    ask('How do I enroll at SPUS?',history,'Are you enrolling')
    ask('Old/continuing college student',history,'URO-PR-016')
    ask('How about transferee?',history,'URO-PR-017')
    ask('And freshmen?',history,'URO-PR-005')
    ask('Ipaliwanag ang step 3',history,'3. Finance Office')
    ask('Who are the CEIT faculty?',history,'Karen T. Plaza')
    ask('How about CHS?',history,'College of Health Sciences')
    ask('Sa CBMA naman?',history,'College of Business Management and Accountancy')
    result = ask('Compare it with CHS',history,'College of Health Sciences')
    assert len(result['sources']) == 2
    ask('Where is it?',history,'specify',no_sources=True)
    ask('Where is the Registrar office?',history,action='navigate_map',destination='registrar_office')
    ask('How about Finance?',history,action='navigate_map',destination='finance_office')
    ask('Where is it?',history,action='navigate_map',destination='finance_office')
    history = []
    ask('What documents do incoming freshmen need to enroll at SPUS?',history,'requirements for Incoming College Freshmen')
    ask('What about transferees?',history,'Requirements for Transferee')
    ask('How about CHS?',[],'specify',no_sources=True)
    ask('What documents do old students need to enroll at SPUS?',[],"don't have enough verified information",no_sources=True)
    rolling = []
    ask('Who are the CEIT faculty?',rolling,'College of Engineering')
    for index in range(10):
        ask('How about CHS?' if index % 2 == 0 else 'Sa CBMA naman?',rolling,
            'College of Health Sciences' if index % 2 == 0 else 'College of Business')
    request = urllib.request.Request(BASE_URL, data=json.dumps({'message':'How about CHS?', 'context_id':'different-tab',
                                     'context_token':rolling[-1]['context_token']}).encode(), headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request, timeout=60) as response:
        isolated = json.load(response)
    assert not isolated['sources'] and 'specify' in isolated['response']
    checks.append({'message':'cross-tab context rejection','passed':True,'response':isolated['response'],'sources':[]})
    target = Path(__file__).resolve().parent.parent / 'PAULA_CONVERSATION_LIVE_CHECKS.json'
    target.write_text(json.dumps({'endpoint':BASE_URL,'passed':len(checks),'checks':checks}, ensure_ascii=False,indent=2), encoding='utf-8')
    print(f'{len(checks)} live guest checks passed; {target}')


if __name__ == '__main__':
    main()
