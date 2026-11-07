"""Bounded provider work, shared outage cooldowns, and evidence-only schemas."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from contextvars import ContextVar
from functools import wraps
import hashlib
import json
import os
from threading import BoundedSemaphore, Lock
import time

from django.conf import settings
from .performance import provider_event, stage

_budget = ContextVar('paula_generation_budget', default=None)
_executor = None
_executor_lock = Lock()
_slots = BoundedSemaphore(2)


class GenerationBudget:
    def __init__(self, seconds=None):
        self.seconds = seconds if seconds is not None else settings.PAULA_GENERATION_DEADLINE_SECONDS
        self.started = None

    def remaining(self):
        if self.started is None:
            self.started = time.monotonic()
        return max(0, self.seconds-(time.monotonic()-self.started))


def generation_scope(function):
    @wraps(function)
    def scoped(*args, **kwargs):
        if _budget.get() is not None:
            return function(*args, **kwargs)
        token = _budget.set(GenerationBudget())
        try:
            return function(*args, **kwargs)
        finally:
            _budget.reset(token)
    return scoped


def completion_options(provider, model, kind='selection', count=5):
    options = {'temperature': 0, 'max_tokens': 128, 'response_format': {'type': 'json_object'}}
    if provider == 'groq' and model.startswith('openai/gpt-oss-'):
        properties = ({'evidence_ids': {'type': 'array', 'items': {'type': 'integer', 'enum': list(range(1, count+1))}}}
                      if kind == 'selection' else {'anchor': {'type': 'string'}, 'replacement': {'type': 'string'}})
        options = {'temperature': 0, 'max_completion_tokens': 512, 'reasoning_effort': 'low', 'include_reasoning': False,
                   'response_format': {'type': 'json_schema', 'json_schema': {
                       'name': 'evidence_selection' if kind == 'selection' else 'context_edit', 'strict': True,
                       'schema': {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}}}}
    return options


class ProviderPolicy:
    """Each instance isolates tests; web workers additionally share boot state."""
    def __init__(self):
        self.states = {}
        self.lock = Lock()

    def _path(self, provider, model):
        from .readiness import boot_directory
        directory = boot_directory()
        if directory is None:
            return None
        return directory/'providers'/(provider+'-'+hashlib.sha256(model.encode()).hexdigest()[:16]+'.json')

    def blocked(self, provider, model):
        with self.lock:
            state = self.states.get((provider, model), {})
            path = self._path(provider, model)
            if path is not None:
                try:
                    state = json.loads(path.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    pass
            return state.get('reason') if state.get('until', 0) > time.time() else None

    def fail(self, provider, model, exc):
        status = getattr(exc, 'status_code', None)
        body = getattr(exc, 'body', None)
        error = body.get('error', body) if isinstance(body, dict) else {}
        code = error.get('code') if isinstance(error, dict) else None
        if code in ('credit_balance_exhausted', 'insufficient_quota', 'billing_hard_limit_reached'):
            reason, seconds = 'credits_exhausted', 3600
        elif code in ('model_permission_blocked_project', 'model_permission_blocked_org'):
            reason, seconds = 'model_permission_blocked', 3600
        elif status in (401, 403):
            reason, seconds = 'credentials_unavailable', 3600
        elif status == 404 or code in ('model_not_found', 'model_decommissioned'):
            reason, seconds = 'model_unavailable', 3600
        elif status == 429:
            reason, seconds = 'rate_limited', 30
            headers = getattr(getattr(exc, 'response', None), 'headers', {})
            try:
                seconds = min(60, max(1, float(headers.get('retry-after', 30))))
            except (ValueError, TypeError):
                pass
        elif isinstance(exc, (TimeoutError, FutureTimeout)) or type(exc).__name__ in (
                'APITimeoutError', 'ReadTimeout', 'ConnectTimeout', 'WriteTimeout', 'PoolTimeout', 'TimeoutException'):
            reason, seconds = 'timeout', 15
        else:
            reason, seconds = 'api_error', 30
        state = {'until': time.time()+seconds, 'reason': reason}
        with self.lock:
            self.states[(provider, model)] = state
            path = self._path(provider, model)
            if path is not None:
                try:
                    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    temporary = path.with_name(path.name+f'.{os.getpid()}.tmp')
                    temporary.write_text(json.dumps(state), encoding='utf-8')
                    temporary.replace(path)
                except OSError:
                    pass  # Local cooldown still applies if temporary storage fails.
        return reason

    def call(self, provider, model, callback, attempts=None):
        reason = self.blocked(provider, model)
        if reason:
            provider_event(provider, 'skipped_'+reason, 0)
            return None
        deadline = _budget.get() or GenerationBudget()
        remaining = deadline.remaining()
        if remaining <= 0 or (attempts is not None and attempts[0] <= 0):
            provider_event(provider, 'deadline_or_call_limit', 0)
            return None
        if not _slots.acquire(blocking=False):
            provider_event(provider, 'busy', 0)
            return None
        global _executor
        with _executor_lock:
            if _executor is None:
                _executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='paula-provider')
        if attempts is not None:
            attempts[0] -= 1
        timeout = min(remaining, settings.PAULA_PROVIDER_CALL_TIMEOUT_SECONDS)
        start = time.perf_counter()
        future = _executor.submit(callback, timeout)
        future.add_done_callback(lambda completed: _slots.release())
        outcome = 'ok'
        error_type = None
        http_status = None
        try:
            with stage('llm'):
                return future.result(timeout=remaining)
        except Exception as exc:
            future.cancel()
            outcome = self.fail(provider, model, exc)
            error_type = type(exc).__name__
            http_status = getattr(exc, 'status_code', None)
            return None
        finally:
            provider_event(provider, outcome, (time.perf_counter()-start)*1000, error_type=error_type, http_status=http_status)
