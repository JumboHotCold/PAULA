"""Re-run the original live cases plus bounded Stage 2 coverage; guest-only and no imports."""
import json
import os
from pathlib import Path
from urllib.request import urlopen
from django.conf import settings
from scripts import audit_stage1


def main():
    output = Path('artifacts/stage2/live')
    output.mkdir(parents=True, exist_ok=True)
    with urlopen('http://127.0.0.1:8000/api/health/ready', timeout=5) as response:
        state = json.load(response)
    expected = os.environ.get('PAULA_EXPECTED_BUILD')
    assert state['ready'] and state['index_complete'] and state['build_consistent'], state
    assert expected and state['build_commit'] == expected, 'Running build does not match the requested test revision'
    assert all(row['build_commit'] == expected for row in state['workers'])
    assert not settings.PAULA_LOG_UNANSWERED_QUERIES, 'Normal-mode live verification requires rehearsal text logging off'
    (output / 'readiness.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
    audit_stage1.OUTPUT = output
    audit_stage1.CASES += tuple(
        (f'tell me about SPUS and why should i enroll in this {noun}', 'two_supported_parts')
        for noun in ('school', 'university', 'campus')) + (
            ('Hello, what can you do?', 'capabilities'), ('Kumusta; tell me about yourself?', 'identity'))
    audit_stage1.main()
    report = json.loads((output / 'audit.json').read_text(encoding='utf-8'))
    assert report['summary']['passed'] == report['summary']['samples'], report['summary']
    assert report['integrity']['unchanged'], 'Database fingerprint changed during guest checks'
    print(json.dumps({'passed':report['summary']['passed'], 'build_commit':expected, 'rehearsal_text_logging':False}))


if __name__ in ('__main__', '<run_path>'):
    main()
