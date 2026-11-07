"""Explicit live selector probe. Synthetic fixture evidence, no DB/account writes."""
import json
from pathlib import Path
import time
from django.conf import settings
from chatbot.logic import PauliBotLogic
from chatbot.performance import capture_trace


def main():
    bot = PauliBotLogic()
    evidence = [dict(question='Orion fixture beacon', document_title='Synthetic Orion fixture', answer='The Orion fixture beacon is blue.'),
                dict(question='Vega fixture beacon', document_title='Synthetic Vega fixture', answer='The Vega fixture beacon is red.')]
    with capture_trace('synthetic_provider_smoke') as trace:
        started = time.perf_counter()
        chosen = bot._select('What color is the Orion fixture beacon?', evidence)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    result = dict(model=settings.GROQ_MODEL, elapsed_ms=elapsed_ms, providers=trace.providers,
                  selected_expected=chosen == evidence[:1],
                  external_call_succeeded=any(event['outcome'] == 'ok' for event in trace.providers),
                  limitation='One synthetic provider call verifies connectivity/selection only; not a language or institutional-answer benchmark.')
    Path('PAULA_MVP_PROVIDER_SMOKE.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ in ('__main__', '<run_path>'):
    main()
