"""Read-only targeted multi-part retrieval/response benchmark; no providers.

Run via Docker Django shell with HF_HUB_OFFLINE=1. The same fixed checks are
used before and after the implementation. This is not a general accuracy score.
"""
import argparse
import json
import statistics
import time
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction

from chatbot.logic import PauliBotLogic
from chatbot.rag import RAGSearcher


CASES = (
    ('two_roles', 'Who is the ICT Director and CEIT Dean?',
     ('Arnold A. Magalona', 'Karen T. Plaza')),
    ('shared_role', 'Who are the deans of CEIT and CHS?',
     ('Karen T. Plaza', 'Kristal Liza Besario')),
    ('two_audiences', 'What are the requirements for freshmen and transferees?',
     ('Freshmen', 'Transferee')),
    ('two_offices', 'Where are the Registrar and Finance offices?',
     ('Registrar Office', 'Finance Office')),
    ('filipino', 'Sino ang ICT director at CEIT dean?',
     ('Arnold A. Magalona', 'Karen T. Plaza')),
    ('partial_missing', 'Who is the ICT Director, and who is the director of Mars?',
     ('Arnold A. Magalona',)),
    ('partial_conflict', 'Who is the ICT Director, and who is the PBMO director?',
     ('Arnold A. Magalona', 'conflicting')),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    assert connection.vendor == 'postgresql'
    bot = PauliBotLogic.__new__(PauliBotLogic)
    bot.client = bot.openai_client = bot.gemini_model = None
    bot.model_name = 'fixture-model'
    bot.rag = RAGSearcher()
    bot.rag.ensure_embeddings = lambda: None
    checks = []
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        for label, query, expected in CASES:
            samples = []
            result = None
            for _ in range(4):
                start = time.perf_counter()
                result = bot.process_query(query)
                samples.append((time.perf_counter() - start) * 1000)
            text, sources, action, action_data = result
            found = [fragment.casefold() in text.casefold() for fragment in expected]
            row = {
                'case': label, 'query': query, 'passed': all(found),
                'expected_fragments': expected, 'matched_fragments': found,
                'p50_ms': round(statistics.median(samples[1:]), 2),
                'first_ms': round(samples[0], 2), 'warm_max_ms': round(max(samples[1:]), 2),
                'response': text, 'sources': sources, 'action': action, 'action_data': action_data,
                'parts': getattr(result, 'answer_parts', []),
            }
            checks.append(row)
            print(json.dumps({key: row[key] for key in ('case', 'passed', 'p50_ms')}), flush=True)
    report = {
        'checks': checks, 'passed': sum(row['passed'] for row in checks), 'total': len(checks),
        'cutoff': settings.RAG_MAX_COSINE_DISTANCE,
        'notes': 'Seven fixed response smoke checks; three warm samples after one initial sample. '
                 'No LLM calls or embedding writes. Vector model startup may affect first samples. '
                 'Expected fragments test targeted coverage, not full factual precision.',
    }
    (Path(settings.BASE_DIR) / args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'total': report['total']}))


if __name__ == '__main__':
    main()
