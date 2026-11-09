"""Read-only Stage 1 reproduction and provider audit; invoke via Docker Django shell.

No imports, backfills, application settings changes or provider discovery calls.
Public synthetic HTTP requests may use the existing configured RAG provider.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import time
from urllib.request import Request, urlopen
from uuid import uuid4

from django.conf import settings
from django.db import connection, transaction
from chatbot import views
from chatbot.dialogue import route_turn
from chatbot.conversation_context import resolve_turn
from chatbot.knowledge_audit import audit
from chatbot.models import FAQ, Location, StaffMember, WebResource, Conversation, ChatHistory
from chatbot.performance import capture_trace
from chatbot.providers import ProviderPolicy

OUTPUT = Path('artifacts/stage1')
CASES = (
    ('ty', 'thanks'), ('thankyoui', 'thanks'), ('thank you', 'thanks'),
    ('hi', 'greeting'), ('tell me about yourself', 'identity'),
    ('hi, tell me about yourself', 'identity'), ('hi, tell me about yourself?', 'identity'),
    ('tell me about SPUS and why should i enroll in this institution', 'two_supported_parts'),
    ('tell me about SPUS and why should i enroll at SPUS', 'two_supported_parts'),
    ('What programs are offered?', 'evidence'), ('why spus?', 'evidence'),
    ('Who is the ICT Director and CEIT Dean?', 'two_supported_parts'),
    ('How do I enroll?', 'clarification'), ('Where is the Registrar office?', 'navigation'),
    ('What is the exact enrollment fee for transferees in 2037?', 'unsupported'),
)


def fingerprints():
    def encode(value):
        return value.tolist() if hasattr(value, 'tolist') else str(value)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        return {model.__name__: dict(count=model.objects.count(), sha256=hashlib.sha256(
            json.dumps(list(model.objects.order_by('pk').values()), sort_keys=True, default=encode).encode()).hexdigest())
                for model in (FAQ, Location, StaffMember, WebResource, Conversation, ChatHistory)}


class SyntheticProviderError(Exception):
    def __init__(self, status=None, code=None):
        super().__init__('Synthetic failure; no real API request.')
        self.status_code = status
        self.body = {'error': {'code': code}}
        self.response = SimpleNamespace(headers={'retry-after': '2'})


def provider_failures():
    """Isolated policies/fake SDK clients; no boot markers or active cooldown writes."""
    from unittest.mock import Mock
    from chatbot.logic import PauliBotLogic
    rows = []
    modes = (
        ('unauthorized', SyntheticProviderError(401)), ('forbidden', SyntheticProviderError(403)),
        ('missing_model', SyntheticProviderError(404)),
        ('model_permission', SyntheticProviderError(403, 'model_permission_blocked_project')),
        ('quota', SyntheticProviderError(429, 'insufficient_quota')),
        ('rate_limit', SyntheticProviderError(429)), ('timeout', TimeoutError('Synthetic timeout')),
        ('api_error', SyntheticProviderError(500)),
    )
    evidence = [dict(question='Synthetic fixture policy', document_title='Reviewed synthetic fixture',
                     answer='Approved fixture text for the audit.')]
    for name, error in modes:
        bot = PauliBotLogic.__new__(PauliBotLogic)
        bot.client = Mock()
        bot.client.chat.completions.create.side_effect = error
        bot.openai_client = bot.gemini_model = None
        bot.model_name = 'synthetic-fixture'
        bot._provider_policy = ProviderPolicy()
        with capture_trace('stage1_provider_fault') as trace:
            chosen = bot._select('Synthetic fixture question', evidence)
        rows.append(dict(mode=name, events=trace.providers, selected_stored_evidence=chosen == evidence,
                         displayed_text=chosen[0]['answer'] if chosen else '',
                         policy_state=bot._provider_policy.states.get(('groq', bot.model_name))))
    return rows


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    before = fingerprints()
    def key_status(value):
        value = (value or '').strip()
        return 'missing' if not value else 'placeholder' if value.startswith('your_') else 'configured_unverified'
    report = dict(measured_at=datetime.now(timezone.utc).isoformat(), database=audit(),
                  runtime=dict(engine=settings.DATABASES['default']['ENGINE'], groq_model=settings.GROQ_MODEL,
                    groq_enabled=settings.PAULA_GROQ_ENABLED, openai_enabled=settings.PAULA_OPENAI_ENABLED,
                    groq_key_configured=bool(settings.GROQ_API_KEY), openai_key_configured=bool(settings.OPENAI_API_KEY),
                    gemini_key_configured=bool(settings.GEMINI_API_KEY),
                    key_status={name: key_status(getattr(settings, name)) for name in ('GROQ_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY')},
                    groq_client_constructed=views.bot.client is not None,
                    openai_client_constructed=views.bot.openai_client is not None,
                    gemini_client_constructed=views.bot.gemini_model is not None,
                    call_timeout_seconds=settings.PAULA_PROVIDER_CALL_TIMEOUT_SECONDS,
                    generation_deadline_seconds=settings.PAULA_GENERATION_DEADLINE_SECONDS), rows=[])
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        report['faq_catalog'] = list(FAQ.objects.order_by('pk').values('id', 'question', 'category', 'source_type', 'source_office'))
        report['reason_sources'] = list(FAQ.objects.filter(question__icontains='why').values('id', 'question', 'answer'))
    for iteration in range(3):
        for query, expected in CASES:
            row = dict(query=query, iteration=iteration, expected=expected,
                       route=vars(route_turn(query, semantic=False)), resolution=vars(resolve_turn(query)))
            started = time.perf_counter()
            request = Request('http://127.0.0.1:8000/api/chat', data=json.dumps(dict(message=query, mode='guest', context_id=str(uuid4()))).encode(),
                              headers={'Content-Type': 'application/json'})
            with urlopen(request, timeout=25) as response:
                data = json.load(response)
                row.update(request_id=response.headers.get('X-Request-ID'), worker=response.headers.get('X-PAULA-Worker'),
                           server_timing=response.headers.get('Server-Timing'))
            row.update(ms=round((time.perf_counter() - started) * 1000, 2), response=data['response'],
                       sources=data.get('sources', []), parts=data.get('answer_parts', []),
                       answer_status=data.get('answer_status'), actual_mode=data.get('response_mode'))
            assert data['saved'] is False and data.get('conversation_id') is None, 'Guest persistence detected'
            if expected in ('thanks', 'identity', 'greeting'):
                row['passed'] = data.get('response_mode') == expected and not data.get('sources')
            elif expected == 'two_supported_parts':
                row['passed'] = len(data.get('sources', [])) >= 2 and data.get('answer_status') == 'ok'
            elif expected == 'evidence':
                row['passed'] = bool(data.get('sources'))
            elif expected == 'navigation':
                row['passed'] = data.get('action') == 'navigate_map'
            elif expected == 'clarification':
                row['passed'] = data.get('answer_status') == 'clarification'
            else:
                row['passed'] = not data.get('sources')
            report['rows'].append(row)
        print(f'Stage 1 synthetic guest round {iteration+1}/3 complete', flush=True)
    report['provider_faults'] = provider_failures()
    after = fingerprints()
    report['integrity'] = dict(before=before, after=after, unchanged=before == after)
    report['summary'] = dict(samples=len(report['rows']), passed=sum(row['passed'] for row in report['rows']),
                             failed_queries=sorted({row['query'] for row in report['rows'] if not row['passed']}))
    (OUTPUT / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(summary=report['summary'], runtime=report['runtime'], data_unchanged=before == after)))


if __name__ in ('__main__', '<run_path>'):
    main()
