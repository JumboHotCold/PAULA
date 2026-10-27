"""Live guest-mode compound checks via Vite; never creates chat records."""
import json
from pathlib import Path
import time
import urllib.request
import uuid


def main():
    checks = []
    tab = str(uuid.uuid4())

    def ask(label, query, expected=(), prior=None, context_id=None):
        payload = {'message': query, 'mode': 'guest', 'context_id': context_id or tab}
        if prior:
            payload['context_token'] = prior.get('context_token')
        request = urllib.request.Request('http://localhost:5173/api/chat', data=json.dumps(payload).encode(),
                                         headers={'Content-Type': 'application/json'})
        start = time.perf_counter()
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.load(response)
        assert data['saved'] is False and data['conversation_id'] is None
        for fragment in expected:
            assert fragment.casefold() in data['response'].casefold(), (label, data)
        parts = data.get('answer_parts', [])
        sources = data['sources']
        for number, source in enumerate(sources, 1):
            if parts:
                assert source['citation_index'] == number
                assert source['query'] == parts[source['part'] - 1]['query']
        row = {'case': label, 'query': query, 'passed': True,
               'elapsed_ms': round((time.perf_counter()-start)*1000, 2),
               'response': data['response'], 'parts': parts, 'sources': sources,
               'saved': data['saved'], 'action': data.get('action')}
        checks.append(row)
        print(json.dumps({key: row[key] for key in ('case', 'elapsed_ms', 'passed')}), flush=True)
        return data

    first = ask('two_roles', 'Who is the ICT Director and CEIT Dean?', ('Arnold A. Magalona', 'Karen T. Plaza'))
    assert [part['status'] for part in first['answer_parts']] == ['ok', 'ok']
    deans = ask('shared_role', 'Who are the deans of CEIT and CHS?', ('Karen T. Plaza', 'Kristal Liza Besario'))
    assert len(deans['answer_parts']) == 2
    docs = ask('audiences', 'What are the requirements for freshmen and transferees?', ('Freshmen', 'Transferee'))
    assert [part['status'] for part in docs['answer_parts']] == ['ok', 'ok']
    assert all(source['source_office'] == 'Registrar' for source in docs['sources'])
    maps = ask('map_choices', 'Where are the Registrar and Finance offices?', ('Directions to Registrar Office', 'Directions to Finance Office'))
    assert maps['action'] is None and len(maps['answer_parts']) == 2
    scholarships = ask('scholarship_application', 'What scholarships are available, and how do I apply?')
    assert len(scholarships['answer_parts']) == 2 and 'scholarship' in scholarships['answer_parts'][1]['query']
    mixed = ask('mixed_topics', 'Who is the University President, and what office handles enrollment?', ('Marie Rosanne Mallillin',))
    assert len(mixed['answer_parts']) == 2
    ask('filipino', 'Sino ang ICT director at CEIT dean?', ('Arnold A. Magalona', 'Karen T. Plaza'))
    missing = ask('partial_missing', 'Who is the ICT Director, and who is the director of Mars?', ('Arnold A. Magalona',))
    assert [part['status'] for part in missing['answer_parts']] == ['ok', 'no_match']
    conflict = ask('partial_conflict', 'Who is the ICT Director, and who is the PBMO director?', ('Arnold A. Magalona', 'conflicting'))
    assert [part['status'] for part in conflict['answer_parts']] == ['ok', 'conflict']
    ask('focused_followup', 'How about CHS?', ('Kristal Liza Besario',), first)
    ambiguous = ask('ambiguous_pronoun', 'Where is it?', prior=first)
    assert ambiguous['sources'] == [] and ambiguous.get('action') is None
    isolated = ask('isolated_guest_tab', 'How about CHS?', prior=first, context_id=str(uuid.uuid4()))
    assert isolated['sources'] == []
    output = Path(__file__).resolve().parent.parent / 'PAULA_COMPOUND_LIVE_CHECKS.json'
    output.write_text(json.dumps({'passed': len(checks), 'checks': checks}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(checks)} live compound checks passed.')


if __name__ == '__main__':
    main()
