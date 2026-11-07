"""Run using Docker Django shell; cached model only, no DB writes or LLM calls."""
import json
from pathlib import Path
import time

from chatbot.dialogue import route_turn, social_router, SOCIAL_EXAMPLES
from chatbot.dialogue_cases import CASES
from chatbot.embedding_runtime import runtime
from scripts.benchmark_dialogue_http import summary


def main():
    start = time.perf_counter()
    model = runtime.initialize()
    social_router.prepare(model)
    startup = round((time.perf_counter()-start)*1000, 2)
    results = []
    prototypes = {text.casefold() for values in SOCIAL_EXAMPLES.values() for text in values}
    assert not (prototypes & {text.casefold() for _, text in CASES}), 'Regression cases overlap prototypes'
    for expected, text in CASES:
        start = time.perf_counter()
        route = route_turn(text)
        results.append(dict(query=text, expected=expected, actual=route.kind, passed=route.kind == expected,
                            method=route.method, score=route.score, elapsed_ms=round((time.perf_counter()-start)*1000, 2)))
    report = dict(cases=len(results), passed=sum(row['passed'] for row in results),
        institutional_misroutes=[row for row in results if row['expected'] == 'knowledge' and row['actual'] != 'knowledge'],
        prototype_count=len(prototypes), startup_ms=startup, latency=summary([row['elapsed_ms'] for row in results]),
        method='Developer-annotated synthetic regression suite; punctuation fixes followed first evaluation; not an independent accuracy estimate', results=results)
    Path('PAULA_DIALOGUE_ROUTING.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'results'}))
    for row in results:
        if not row['passed']:
            print(json.dumps(row))


if __name__ == '__main__':
    main()
