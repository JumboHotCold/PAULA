"""Read-only, deterministic development benchmark; run through Docker Django shell.

No provider requests, writes to application data, or stored-vector changes.
This is a synthetic development set, not a held-out accuracy evaluation.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import time

from django.db import connection, transaction
from chatbot.conversation_config import conversation_config
from chatbot.dialogue import route_turn, social_router
from chatbot.embedding_runtime import runtime
from chatbot.grounding import eligible_evidence, terms
from chatbot.intents import normalize_query, _distance
from chatbot.models import FAQ, StaffMember, Location
from chatbot.query_normalization import normalize_input
from chatbot.rag import RAGSearcher

OPS = ('clean', 'transposition', 'deletion', 'insertion', 'substitution', 'doubled', 'spacing', 'case')


def perturb(text, operation, seed):
    rng = random.Random(seed)
    tokens = [m for m in re.finditer(r'\b[a-zA-Z]{4,}\b', text) if not m.group().isupper()]
    if operation == 'clean':
        return text
    if operation == 'case':
        return ''.join(c.upper() if i % 2 else c.lower() for i, c in enumerate(text))
    if not tokens:
        tokens = list(re.finditer(r'\b[a-zA-Z]{2,}\b', text))
    if not tokens:
        return text
    match = rng.choice(tokens)
    word = match.group()
    index = rng.randrange(len(word) - 1)
    if operation == 'transposition':
        choices = [i for i in range(len(word)-1) if word[i].lower() != word[i+1].lower()]
        if not choices:
            return text
        index = rng.choice(choices)
        changed = word[:index] + word[index+1] + word[index] + word[index+2:]
    elif operation == 'deletion':
        changed = word[:index] + word[index+1:]
    elif operation == 'insertion':
        changed = word[:index] + rng.choice('abcdefghijklmnopqrstuvwxyz') + word[index:]
    elif operation == 'substitution':
        changed = word[:index] + rng.choice([c for c in 'abcdefghijklmnopqrstuvwxyz' if c != word[index].lower()]) + word[index+1:]
    elif operation == 'doubled':
        changed = word[:index] + word[index] + word[index:]
    else:
        changed = word[:index+1] + ' ' + word[index+1:]
    return text[:match.start()] + changed + text[match.end():]


def corpus():
    records = []
    for obj in FAQ.objects.order_by('pk'):
        records.append(dict(group='faq', gold=str(obj.pk), query=obj.question))
    for obj in StaffMember.objects.order_by('pk'):
        records.append(dict(group='staff', gold=obj.name.casefold(), query=f'Who is {obj.name}?'))
    for obj in Location.objects.order_by('pk'):
        records.append(dict(group='location', gold=str(obj.pk), query=f'Where is {obj.name}?'))
    config = conversation_config()
    examples = [(kind, text) for kind, texts in config['semantic']['exemplars'].items() for text in texts]
    examples += [(kind, text) for kind, texts in config['social']['forms'].items() for text in texts]
    examples += [(kind, text) for text, kind in config['social']['abbreviations'].items()]
    # Literal canonical identity/capability commands are already config-backed patterns.
    examples += [('identity', 'Tell me about yourself'), ('identity', 'Who are you?'),
                 ('capabilities', 'What can you do?')]
    for i, (kind, text) in enumerate(examples):
        records.append(dict(group='intent', gold=kind, query=text, key=i))
    rows = []
    for i, record in enumerate(records):
        for operation in OPS:
            query = perturb(record['query'], operation, 314159 + i * 17 + OPS.index(operation))
            rows.append(dict(record, original=record['query'], query=query, operation=operation))
    # Valid near-miss nouns, constraints and institutions must not become social shortcuts.
    for text in ('Who is the ICT Director?', 'What is your office policy?', 'What are the tanks on campus?',
                 'What is the thinks scholarship?', 'Thanks, what programs are offered at SPUS?',
                 'Can you help me enroll without credentials in 2037?', 'Who is the dean of CEIT?',
                 'Tell me about Yourself University', 'What is the Thank You scholarship?',
                 'Are there SHANKS policies?', 'What is your name in the staff directory?'):
        rows.append(dict(group='negative', gold='knowledge', query=text, original=text, operation='clean'))
    return rows


def ids(row):
    result = {(str(row.get('record_type')), str(row.get('record_id')))}
    for child in row.get('supporting_sources', ()):
        result |= ids(child)
    return result


def hit(case, row):
    if case['group'] == 'staff':
        return row.get('personnel_name', '').casefold() == case['gold']
    return (case['group'], case['gold']) in ids(row)


def trace_report(rag):
    import numpy as np
    from chatbot.dialogue import SOCIAL_EXAMPLES, FAST_PATTERNS, FACTUAL, REQUEST, SELF_SOCIAL
    from chatbot.social_normalization import match_social
    from chatbot.intents import VOCABULARY
    CORRECTION_VOCABULARY = VOCABULARY | {word+'s' for word in VOCABULARY if not word.endswith('s')}
    queries = ('tell me abuot yourself', 'hi, tell me about yourself?', 'who r u', 'wat can u do',
               'thnx', 'thankyouuu', 'who r u, wat can u do, thnx, thankyouuu',
               'hi, what are the programs ofered', 'hi, what are the programs offered')
    results = []
    for query in queries:
        text = normalize_query(query)
        route = route_turn(query)
        vector = np.asarray(rag.model.encode(text, normalize_embeddings=True, show_progress_bar=False))
        scores = social_router.matrix @ vector
        ranked = sorted(((max(float(scores[i]) for i, label in enumerate(social_router.labels) if label == kind), kind)
                         for kind in SOCIAL_EXAMPLES), reverse=True)
        item = dict(query=query, normalized=text, route=vars(route),
                    social=vars(match_social(text)) if match_social(text) else None,
                    exact_intents=[kind for kind, pattern in FAST_PATTERNS.items() if pattern.fullmatch(text)],
                    semantic_ranked=ranked[:3], margin=ranked[0][0]-ranked[1][0],
                    semantic_affordance=not (FACTUAL.search(text) or REQUEST.search(text)) or bool(SELF_SOCIAL.search(text)))
        if hasattr(route,'segments'):
            from dataclasses import asdict
            item['route']=asdict(route)
        if hasattr(route,'segments'):
            from chatbot.spelling import matching_plan
            item['spelling']=asdict(matching_plan(query))
        if route.kind == 'knowledge':
            effective = route.query
            outcome = rag.retrieve(effective, limit=3)
            item['retrieval'] = dict(status=outcome.status, results=[dict(question=r.get('question'), distance=r.get('distance'),
                eligible=eligible_evidence(effective, r)) for r in outcome.evidence])
            # Source candidate diagnostic independent of the retrieval cutoff.
            nearest = []
            from pgvector.django import CosineDistance
            for obj in FAQ.objects.exclude(embedding__isnull=True).annotate(distance=CosineDistance('embedding', rag._generate_embedding(effective))).order_by('distance')[:3]:
                evidence = dict(question=obj.question, answer=obj.answer, record_type='faq', source_type=obj.source_type,
                                source_office=obj.source_office)
                nearest.append(dict(id=obj.pk, question=obj.question, distance=float(obj.distance),
                                    grounding=eligible_evidence(effective, evidence), terms=sorted(terms(effective)),
                                    overlap=sorted(terms(effective) & terms(obj.question + ' ' + obj.answer))))
            item['nearest_faq'] = nearest
        item['old_token_candidates'] = {word: sorted(((_distance(word, target), target) for target in CORRECTION_VOCABULARY), key=lambda x:x[0])[:3]
                                        for word in normalize_input(query).spaced.split() if word not in CORRECTION_VOCABULARY and len(word)>=4}
        results.append(item)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--trace-only', action='store_true')
    args = parser.parse_args()
    directory = Path('artifacts/spelling')
    directory.mkdir(exist_ok=True, parents=True)
    started = time.perf_counter()
    model = runtime.initialize()
    rag = RAGSearcher()
    rag.model = model
    social_router.prepare(model)
    if args.label != 'before':
        from chatbot.spelling import prepare_vocabulary
        lexicon = prepare_vocabulary()
    prepare_ms = (time.perf_counter() - started)*1000
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION READ ONLY')
        if args.label == 'before' and not (directory/'corpus.json').exists():
            (directory/'corpus.json').write_text(json.dumps(corpus(), indent=2, ensure_ascii=False), encoding='utf-8')
        report = dict(label=args.label, measured_at=datetime.now(timezone.utc).isoformat(), prepare_ms=prepare_ms,
                      traces=trace_report(rag), rows=[])
        if args.label != 'before':
            report['lexicon'] = dict(words=len(lexicon.words), names=len(lexicon.names), acronyms=len(lexicon.acronyms), sources=dict(lexicon.source_counts))
        if not args.trace_only:
            cases = json.loads((directory/'corpus.json').read_text(encoding='utf-8'))
            report['corpus_sha256'] = hashlib.sha256((directory/'corpus.json').read_bytes()).hexdigest()
            for i, case in enumerate(cases):
                start = time.perf_counter()
                route = route_turn(case['query'])
                result = dict(case, route=route.kind, effective=route.query, method=route.method)
                if case['group'] in ('intent', 'negative'):
                    result['correct'] = route.kind == case['gold']
                else:
                    can_retrieve = route.kind=='knowledge' and route.method not in ('spelling_confirmation','protected_name')
                    outcome = rag.retrieve(route.query or normalize_query(case['query']), limit=3) if can_retrieve else None
                    evidence = outcome.evidence if outcome else []
                    result.update(status=outcome.status if outcome else route.method if route.kind=='knowledge' else route.kind,
                                  top1=bool(evidence and hit(case, evidence[0])), top3=any(hit(case, r) for r in evidence[:3]),
                                  wrong_person=case['group']=='staff' and any(r.get('personnel_name') and not hit(case,r) for r in evidence),
                                  evidence=[{key:r.get(key) for key in ('record_type','record_id','personnel_name','question','distance')} for r in evidence])
                result['elapsed_ms'] = (time.perf_counter()-start)*1000
                report['rows'].append(result)
                if i % 100 == 0:
                    print(f'{args.label}: {i}/{len(cases)}', flush=True)
    (directory/f'{args.label}.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    print(json.dumps(dict(label=args.label, rows=len(report['rows']), prepare_ms=prepare_ms)), flush=True)


if __name__ == '__main__':
    main()
