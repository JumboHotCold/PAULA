"""Measure activation separately from first semantic requests after readiness."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--started-ms', required=True, type=int)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    attempts = 0
    deadline = time.monotonic()+300
    while time.monotonic() < deadline:
        attempts += 1
        try:
            with urllib.request.urlopen('http://127.0.0.1:8080/api/health/ready', timeout=2) as response:
                state = json.load(response)
            if state['ready'] and state['ready_workers'] == state['expected_workers']:
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        if attempts % 5 == 0:
            print(f'Waiting for all semantic workers; attempt {attempts}', flush=True)
        time.sleep(1)
    else:
        raise RuntimeError('All-worker semantic readiness was not reached')
    activation_ms = round(time.time()*1000-args.started_ms, 2)

    def ask(_):
        payload = {'message': 'What is the school calendar?', 'mode': 'guest', 'context_id': str(uuid.uuid4())}
        request = urllib.request.Request('http://127.0.0.1:8080/api/chat', data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        start = time.perf_counter()
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
            worker = response.headers.get('X-PAULA-Worker')
            request_id = response.headers.get('X-Request-ID')
        assert not data['saved'] and len(data['sources']) == 1
        return {'worker': worker, 'request_id': request_id, 'elapsed_ms': round((time.perf_counter()-start)*1000, 2)}
    samples = []
    expected = {str(record['worker']) for record in state['workers']}
    for _ in range(6):
        with ThreadPoolExecutor(max_workers=state['expected_workers']) as executor:
            samples.extend(executor.map(ask, range(state['expected_workers'])))
        if {sample['worker'] for sample in samples} >= expected:
            break
    assert {sample['worker'] for sample in samples} >= expected, 'Not all prepared workers were observed'
    report = {'activation_to_all_workers_ready_ms': activation_ms, 'readiness': state,
              'first_semantic_requests': samples, 'all_workers_observed': True,
              'notes': 'Activation includes Compose/startup. First semantic requests are made only after every worker reports readiness.'}
    Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
