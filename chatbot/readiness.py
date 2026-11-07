"""Per-boot worker readiness; markers contain operational metadata only."""
import json
import os
from pathlib import Path
import time
from uuid import UUID

from django.conf import settings
from .embedding_runtime import runtime, DIMENSIONS
from .performance import emit


def boot_directory():
    boot = os.environ.get('PAULA_BOOT_ID')
    if not boot:
        return None
    try:
        UUID(boot)
    except ValueError:
        return None
    return Path(getattr(settings, 'PAULA_RUNTIME_DIR', '/tmp/paula-runtime'))/boot


def initialize_worker(worker):
    start = time.perf_counter()
    from .views import bot
    from .rag import RAGSearcher
    runtime.web_worker = True
    emit({'event': 'worker_initializing', 'worker': os.getpid()})
    worker.notify()
    social_ready = False
    try:
        model = runtime.initialize()
        if bot.rag is None:
            bot.rag = RAGSearcher()
        bot.rag.model = model  # Same process singleton; no second model.
        from .dialogue import social_router
        social_router.prepare(model)
        social_ready = True
    except Exception:
        pass  # Failed workers remain explicitly unready; no request-time retry.
    worker.notify()
    directory = boot_directory()
    record = {'worker': os.getpid(), 'ready': runtime.status == 'ready' and social_ready,
              'social_router_ready': social_ready,
              'dimensions': DIMENSIONS, 'startup_ms': round((time.perf_counter()-start)*1000, 2)}
    if directory is not None:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = directory/f'{os.getpid()}.json'
        temporary = directory/f'{os.getpid()}.tmp'
        temporary.write_text(json.dumps(record), encoding='utf-8')
        temporary.replace(path)
    emit({'event': 'worker_startup', **record})


def readiness_state():
    expected = int(os.environ.get('PAULA_WORKER_COUNT', '1'))
    directory = boot_directory()
    workers = []
    if directory is not None and directory.exists():
        for path in directory.glob('*.json'):
            try:
                record = json.loads(path.read_text(encoding='utf-8'))
                os.kill(int(record['worker']), 0)
                if record.get('ready') and record.get('dimensions') == DIMENSIONS:
                    workers.append(record)
            except (ValueError, KeyError, OSError):
                continue
    elif runtime.status == 'ready':
        workers = [{'worker': os.getpid(), 'ready': True, 'dimensions': DIMENSIONS, 'startup_ms': runtime.startup_ms}]
    workers = list({record['worker']: record for record in workers}.values())
    return {'ready': runtime.status == 'ready' and len(workers) >= expected,
            'expected_workers': expected, 'ready_workers': len(workers), 'workers': workers}
