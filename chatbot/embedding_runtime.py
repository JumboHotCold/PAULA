"""One compatible, offline MiniLM instance per process, prepared before traffic."""
from pathlib import Path
from threading import Lock
import os
import math
import re
import time

from django.conf import settings
from .performance import capture_trace, emit, stage

MODEL_ID = 'sentence-transformers/all-MiniLM-L6-v2'
DIMENSIONS = 384


class ModelNotReady(RuntimeError):
    pass


class EmbeddingRuntime:
    def __init__(self):
        self.model = None
        self.lock = Lock()
        self.status = 'cold'
        self.startup_ms = None
        self.web_worker = False

    @staticmethod
    def cached_path():
        explicit = getattr(settings, 'PAULA_EMBEDDING_MODEL_PATH', '')
        if explicit:
            path = Path(explicit)
        else:
            if not re.fullmatch(r'[a-fA-F0-9]{40}', settings.PAULA_EMBEDDING_REVISION):
                raise ModelNotReady('Invalid pinned embedding revision')
            root = Path(os.environ.get('HF_HUB_CACHE') or
                        Path(os.environ.get('HF_HOME', str(Path.home()/'.cache/huggingface')))/'hub')
            path = root/'models--sentence-transformers--all-MiniLM-L6-v2'/'snapshots'/settings.PAULA_EMBEDDING_REVISION
        if not path.is_dir() or not (path/'config.json').is_file():
            raise ModelNotReady('Cached embedding model is unavailable')
        return path

    def initialize(self):
        with self.lock:
            if self.status == 'ready':
                return self.model
            start = time.perf_counter()
            self.status = 'loading'
            try:
                path = self.cached_path()
                with capture_trace('embedding_startup') as trace:
                    with stage('model_import'):
                        from sentence_transformers import SentenceTransformer
                    with stage('model_load'):
                        model = SentenceTransformer(str(path), local_files_only=True, device='cpu')
                    if model.get_sentence_embedding_dimension() != DIMENSIONS:
                        raise ModelNotReady('Incompatible embedding dimensions')
                    with stage('model_warmup'):
                        vector = model.encode('PAULA readiness check').tolist()
                    if len(vector) != DIMENSIONS or not all(math.isfinite(value) for value in vector):
                        raise ModelNotReady('Incompatible embedding result')
                    self.model = model
                    self.status = 'ready'
                    self.startup_ms = round((time.perf_counter()-start)*1000, 2)
                    record = trace.summary()
                    record.update(event='embedding_ready', startup_ms=self.startup_ms, dimensions=DIMENSIONS)
                    emit(record)
                return self.model
            except Exception as exc:
                self.status = 'failed'
                self.startup_ms = round((time.perf_counter()-start)*1000, 2)
                emit({'event': 'embedding_unavailable', 'worker': os.getpid(),
                      'error_type': type(exc).__name__, 'startup_ms': self.startup_ms})
                raise ModelNotReady('Embedding worker is not ready') from exc

    def get_model(self):
        if self.status == 'ready':
            return self.model
        if self.web_worker:
            raise ModelNotReady('Semantic retrieval is not ready')
        # Offline ingestion/evaluation can explicitly initialize its own
        # process. An HTTP request never performs this cold initialization.
        return self.initialize()


runtime = EmbeddingRuntime()
