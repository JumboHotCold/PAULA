"""Prepare each existing Gunicorn worker before accepting its first request."""
import os
from pathlib import Path
from uuid import uuid4


def on_starting(server):
    os.environ['PAULA_BOOT_ID'] = str(uuid4())
    os.environ['PAULA_WORKER_COUNT'] = str(server.cfg.workers)


def post_worker_init(worker):
    from chatbot.readiness import initialize_worker
    initialize_worker(worker)


def child_exit(server, worker):
    # This hook runs in the master, where Django/ML need not be initialized.
    # Delete only this boot's named worker marker; never load Torch before fork.
    boot = os.environ.get('PAULA_BOOT_ID')
    if boot:
        root = Path(os.environ.get('PAULA_RUNTIME_DIR', '/tmp/paula-runtime'))
        (root/boot/f'{int(worker.pid)}.json').unlink(missing_ok=True)
