"""Run inside the web container: verify one graceful worker replacement."""
import json
import os
from pathlib import Path
import signal
import time
import urllib.error
import urllib.request


def state():
    with urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=2) as response:
        return json.load(response)


def main():
    before = state()
    assert before['ready'] and before['ready_workers'] == 3
    victim = before['workers'][0]['worker']
    start = time.perf_counter()
    os.kill(victim, signal.SIGTERM)
    unavailable_seen = False
    after = None
    for _ in range(180):
        time.sleep(.5)
        try:
            after = state()
            if after['ready'] and victim not in {row['worker'] for row in after['workers']}:
                break
        except (urllib.error.URLError, TimeoutError):
            unavailable_seen = True
    else:
        raise RuntimeError('Replacement worker did not reach readiness')
    assert unavailable_seen, 'Aggregate readiness did not reflect replacement warmup'
    assert after['ready_workers'] == before['ready_workers']
    result = {'ready_before': before, 'ready_after': after, 'unready_during_replacement': unavailable_seen,
              'replacement_ready_ms': round((time.perf_counter()-start)*1000, 2),
              'notes': 'One idle Gunicorn worker gracefully replaced; database/container/volumes unchanged.'}
    Path('/app/PAULA_WORKER_RECYCLE.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
