"""Live signed-context, language and data-integrity regression checks."""
import json
from pathlib import Path
import runpy
from urllib.request import Request, urlopen
from uuid import uuid4

rows = []


def thread(turns):
    history, token, context_id, results = [], None, str(uuid4()), []
    for query in turns:
        payload = dict(message=query, mode='guest', context_id=context_id, history=history[-8:], context_token=token)
        with urlopen(Request('http://127.0.0.1:8000/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}), timeout=25) as response:
            data = json.load(response)
        assert not data['saved'] and data.get('conversation_id') is None
        rows.append(dict(query=query, mode=data.get('response_mode'), response=data['response'], sources=data.get('sources'), action=data.get('action')))
        results.append(data)
        token = data.get('context_token')
        history.extend([dict(role='user', content=query), dict(role='assistant', content=data['response'])])
    return results


enrollment = thread(['How do I enroll?', 'thankyoui', 'yes', 'no', 'dili', 'Transferee student'])
assert enrollment[1]['response_mode'] == 'thanks'
for response in enrollment[2:5]:
    assert 'Are you enrolling' in response['response']
    assert response.get('action') is None and not response.get('sources')
assert 'URO-PR-017' in enrollment[-1]['response'] and enrollment[-1]['sources']

navigation = thread(['Show me the campus map', 'ty', 'sure', 'Registrar'])
assert navigation[1]['response_mode'] == 'thanks'
assert navigation[2].get('action') is None and 'Which campus office' in navigation[2]['response']
assert navigation[-1].get('action') == 'navigate_map'
assert navigation[-1]['action_data']['destination'] == 'registrar_office'

clarification = thread(['Who is the ICT Director?', 'ty', 'what do you mean?'])
assert clarification[0]['sources']
assert 'previous answer' in clarification[-1]['response'] and not clarification[-1]['sources']

explicit_english = thread(['English please', 'salamat kaayo'])
assert "You're welcome" in explicit_english[-1]['response']
cebuano = thread(['salamat kaayo'])
assert 'Walay sapayan' in cebuano[0]['response']
repeat = thread(['ty', 'ty'])
assert repeat[0]['response'] != repeat[1]['response']
assert thread(['ty'])[0]['response'] == repeat[0]['response']

proof_path = Path('PAULA_SOCIAL_TOLERANCE_INTEGRITY.json')
proof = json.loads(proof_path.read_text())
proof['after'] = runpy.run_path('scripts/verify_csv_reference_integrity.py')['fingerprints']()
proof['unchanged'] = proof['before'] == proof['after']
proof_path.write_text(json.dumps(proof, indent=2))
assert proof['unchanged'], 'Knowledge/history changed; inspect concurrent activity before attribution'
Path('PAULA_SOCIAL_TOLERANCE_CONTEXT.json').write_text(json.dumps(dict(passed=True, turns=len(rows), rows=rows,
    data_unchanged=True, notes='Live guest requests with signed thread context. No accounts or historical chat data changed.'), indent=2, ensure_ascii=False))
print(json.dumps(dict(context_sequences_passed=7, turns=len(rows), data_unchanged=True)))
