"""Request-local, payload-free diagnostics. No prompts, identities or SQL text."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import json
import logging
import os
from threading import Lock
import time
from uuid import uuid4
from .build_info import build_info

logger = logging.getLogger('paula.performance')
_trace = ContextVar('paula_performance_trace', default=None)
_stack = ContextVar('paula_performance_stack', default=())


class Trace:
    def __init__(self, route='chat'):
        self.request_id = str(uuid4())
        self.worker = os.getpid()
        self.route = route
        self.build_commit = build_info()['build_commit']
        self.started = time.perf_counter()
        self.stages = {}
        self.providers = []
        self.sql_count = 0
        self.sql_ms = 0.0
        self.closed = False
        self.lock = Lock()

    def summary(self, status=200):
        return {'event': 'request_timing', 'request_id': self.request_id, 'worker': self.worker, 'build_commit': self.build_commit,
                'route': self.route, 'status': status,
                'total_ms': round((time.perf_counter()-self.started)*1000, 2),
                'sql_count': self.sql_count, 'sql_ms': round(self.sql_ms, 2),
                'stages': self.stages, 'providers': self.providers}


@contextmanager
def capture_trace(route='chat'):
    trace = Trace(route)
    token = _trace.set(trace)
    stack_token = _stack.set(())
    try:
        yield trace
    finally:
        trace.closed = True
        _stack.reset(stack_token)
        _trace.reset(token)


@contextmanager
def stage(name):
    trace = _trace.get()
    if trace is None or trace.closed:
        yield
        return
    frame = {'child_ms': 0.0}
    parents = _stack.get()
    token = _stack.set((*parents, frame))
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = (time.perf_counter()-start)*1000
        _stack.reset(token)
        if parents:
            parents[-1]['child_ms'] += elapsed
        with trace.lock:
            value = trace.stages.setdefault(name, {'calls': 0, 'inclusive_ms': 0.0, 'self_ms': 0.0})
            value['calls'] += 1
            value['inclusive_ms'] = round(value['inclusive_ms']+elapsed, 3)
            value['self_ms'] = round(value['self_ms']+max(0, elapsed-frame['child_ms']), 3)


def timed(name):
    def decorate(function):
        @wraps(function)
        def measured(*args, **kwargs):
            with stage(name):
                return function(*args, **kwargs)
        return measured
    return decorate


def provider_event(provider, outcome, elapsed_ms, error_type=None, http_status=None):
    trace = _trace.get()
    if trace is not None and not trace.closed:
        event = {'provider': provider, 'outcome': outcome, 'elapsed_ms': round(elapsed_ms, 2)}
        if error_type:
            event['error_type'] = error_type
        if type(http_status) is int:
            event['http_status'] = http_status
        trace.providers.append(event)


def emit(record):
    # Only internal callers construct these records; never pass request.data,
    # exceptions, HTTP headers, prompts, responses or query parameters here.
    logger.info(json.dumps(record, sort_keys=True, separators=(',', ':')))


def diagnostic_error(stage_name, code, exception=None):
    trace = _trace.get()
    request_id = trace.request_id if trace is not None else None
    record = {'event': 'request_error', 'request_id': request_id, 'worker': os.getpid(),
              'stage': stage_name, 'error_code': code}
    if exception is not None:
        record['error_type'] = type(exception).__name__
    emit(record)
    return request_id


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.rstrip('/') != '/api/chat':
            return self.get_response(request)
        from django.db import connection
        with capture_trace() as trace:
            def sql_timing(execute, sql, params, many, context):
                start = time.perf_counter()
                try:
                    return execute(sql, params, many, context)
                finally:
                    trace.sql_count += 1
                    trace.sql_ms += (time.perf_counter()-start)*1000
            status = 500
            try:
                with connection.execute_wrapper(sql_timing):
                    response = self.get_response(request)
                    if hasattr(response, 'render') and not getattr(response, 'is_rendered', True):
                        with stage('serialization'):
                            response.render()
                status = response.status_code
                summary = trace.summary(status)
                response['X-Request-ID'] = trace.request_id
                response['X-PAULA-Worker'] = str(trace.worker)
                response['Server-Timing'] = 'total;dur=' + str(summary['total_ms']) + ', sql;dur=' + str(summary['sql_ms'])
                return response
            finally:
                emit(trace.summary(status))
