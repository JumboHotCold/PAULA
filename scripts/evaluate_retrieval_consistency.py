"""Read-only, provider-free retrieval consistency baseline/after evaluation."""
import argparse
import json
import statistics
import time
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction
from chatbot.rag import RAGSearcher
from chatbot.intents import normalize_query
from chatbot.conversation_context import resolve_conversation
from chatbot.query_normalization import roles_in

CASES = [
    ('president', 'Who is the University President?', 'president'),
    ('current', 'Who is the current university president?', 'president'),
    ('currently', 'Who is currently the University President?', 'president'),
    ('now', 'Who is the university president now?', 'president'),
    ('today', 'Who is the university president today?', 'president'),
    ('filipino', 'Sino ang presidente ng SPUS?', 'president'),
    ('vp_short', 'Who is the VP for Academics?', 'vp'),
    ('vp_expanded', 'Who is the Vice President for Academic Services?', 'vp'),
    ('dean', 'Who is the CEIT dean?', 'dean'),
    ('moderator', 'Who is the JSIT moderator?', 'moderator'),
    ('historical', 'Who is the university president in 2099?', None),
    ('foreign', 'Who is the president of Mars?', None),
]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    assert connection.vendor=='postgresql'
    rag=RAGSearcher();rag.ensure_embeddings=lambda:None
    results=[]
    with transaction.atomic():
        with connection.cursor() as cursor:cursor.execute('SET TRANSACTION READ ONLY')
        for label,query,expected in CASES:
            samples=[];rows=None
            # Historical/foreign controls bypass vector work here: exact
            # exclusion is checked separately in regression tests.
            if expected is None:
                from chatbot.personnel import exact_personnel_lookup
                records=exact_personnel_lookup(normalize_query(query))
                results.append({'case':label,'query':query,'expected':'no exact match','passed':not records})
                continue
            for _ in range(6):
                start=time.perf_counter();rows=rag.retrieve(normalize_query(query));samples.append((time.perf_counter()-start)*1000)
            records=rows.evidence
            passed=any(expected in roles_in(row.get('personnel_role') or row.get('document_title','')) for row in records)
            result={'case':label,'query':query,'passed':passed,'status':rows.status,'count':len(records),
                    'p50_ms':round(statistics.median(samples[1:]),2),'warm_max_ms':round(max(samples[1:]),2),
                    'titles':[r['document_title'] for r in records]}
            results.append(result);print(json.dumps(result),flush=True)
        for label,prior,current in [('followup','Who is the University President?','Who is currently holding that role?'),
                                    ('role_switch','Who is the University President?','How about the VP for Academics?')]:
            plan=resolve_conversation(current,[{'role':'user','content':prior},{'role':'assistant','content':'Previously displayed evidence.'}])
            records=rag.retrieve(plan.queries[0]).evidence if plan.queries else []
            wanted='president' if label=='followup' else 'vp'
            results.append({'case':label,'query':current,'effective_queries':plan.queries,
                            'passed':any(wanted in roles_in(row.get('personnel_role') or row.get('document_title','')) for row in records)})
    report={'cutoff':settings.RAG_MAX_COSINE_DISTANCE,'checks':results,'passed':sum(r['passed'] for r in results),
            'total':len(results),'notes':'Small regression corpus; warm retrieval only, no LLM, no embeddings or institutional data writes. Negative controls test exact exclusion only.'}
    target=Path(settings.BASE_DIR)/args.output
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'total':report['total'],'output':str(target)}))


if __name__=='__main__':main()
