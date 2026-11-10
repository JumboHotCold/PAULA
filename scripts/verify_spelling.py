"""Isolated in-process guest API checks against the existing PostgreSQL data.

Never reloads/deploys the shared workers. External provider execution is trapped.
Saved chat history and public source records must keep identical fingerprints.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import time
from unittest.mock import patch
from uuid import uuid4
from rest_framework.test import APIRequestFactory
from chatbot import views
from chatbot.embedding_runtime import runtime
from chatbot.dialogue import social_router
from chatbot.performance import capture_trace
from chatbot.rag import RAGSearcher
from chatbot.spelling import prepare_vocabulary
from chatbot.build_info import build_info

CASES=(('tell me abuot yourself','identity'), ('hi, tell me about yourself?','identity'),
       ('who r u','identity'), ('wat can u do','capabilities'), ('thnx','thanks'), ('thankyouuu','thanks'),
       ('who r u, wat can u do, thnx, thankyouuu','social_bundle'),
       ('hi, what are the programs ofered','evidence'), ('What progrmas are offered at SPUS?','evidence'),
       ('Who is the ICT Director and CEIT Dean?','compound'),
       ('TELL ME ABOUT SPUS AND WHY SHOULD I ENROL','compound'),
       ('Where is the registar office?','clarification'),
       ('Where is the registrra office?','navigate_map'),
       ('What is the exact tuition fee in 2037?','unsupported'),
       ('Who is Dr. Antonio Talaera?','clarification'), ('What is the preseidnt?','clarification'),
       ('Anong mga kursong inaalok sa SPUS?','evidence'))


def main():
    directory=Path('artifacts/spelling')
    fingerprints=runpy.run_path('scripts/audit_stage1.py',run_name='audit_module')['fingerprints']
    before=fingerprints()
    started=time.perf_counter()
    model=runtime.initialize()
    social_router.prepare(model)
    vocabulary_started=time.perf_counter()
    lexicon=prepare_vocabulary()
    vocabulary_ms=(time.perf_counter()-vocabulary_started)*1000
    rag=RAGSearcher()
    rag.model=model
    views.bot.rag=rag
    result=dict(measured_at=datetime.now(timezone.utc).isoformat(),build=build_info(),
                scope='In-process DRF guest API, not HTTP/Vite/browser rendering; no shared worker reload.',
                startup_ms=(time.perf_counter()-started)*1000,vocabulary_prepare_ms=vocabulary_ms,
                lexicon=dict(lexicon.source_counts),words=len(lexicon.words),name_tokens=len(lexicon.names),rows=[])
    with patch('chatbot.providers.ProviderPolicy.call',side_effect=AssertionError('External provider execution forbidden')) as external:
        for iteration in range(3):
            for query,expected in CASES:
                request=APIRequestFactory().post('/api/chat',dict(message=query,mode='guest',context_id=str(uuid4())),format='json')
                started=time.perf_counter()
                with capture_trace('spelling_guest_api') as trace:
                    response=views.chat_api(request)
                data=response.data
                passed=response.status_code==200 and data['saved'] is False and data['conversation_id'] is None
                if expected in ('identity','capabilities','thanks','social_bundle'):
                    passed &= data['response_mode']==expected and not data['sources']
                elif expected=='evidence':passed &= bool(data['sources'])
                elif expected=='compound':passed &= len(data['answer_parts'])==2 and data['answer_status']=='ok'
                elif expected=='navigate_map':passed &= data['action']=='navigate_map'
                elif expected=='clarification':passed &= data['answer_status']=='clarification' and not data['sources']
                else:passed &= not data['sources'] and data['answer_status']=='no_match'
                result['rows'].append(dict(query=query,expected=expected,iteration=iteration,passed=bool(passed),
                    elapsed_ms=(time.perf_counter()-started)*1000,response=data['response'],sources=data['sources'],
                    suggestions=data['suggestions'],suggestions_kind=data['suggestions_kind'],
                    mode=data['response_mode'],status=data['answer_status'],trace=trace.summary(response.status_code)))
        thread=str(uuid4())
        token=None
        for query,expected in (('How do I enorll?','clarification'),('Old/continuing college student','evidence'),
                               ('thnx','thanks'),('How about transferee?','evidence')):
            request=APIRequestFactory().post('/api/chat',dict(message=query,mode='guest',context_id=thread,context_token=token),format='json')
            started=time.perf_counter()
            with capture_trace('spelling_guest_followup') as trace:
                response=views.chat_api(request)
            data=response.data
            passed=response.status_code==200 and data['saved'] is False and data['conversation_id'] is None
            passed &= (bool(data['sources']) if expected=='evidence' else data['response_mode']=='thanks' if expected=='thanks' else data['answer_status']=='clarification')
            result['rows'].append(dict(query=query,expected=expected,flow='enrollment_social_followup',passed=bool(passed),
                elapsed_ms=(time.perf_counter()-started)*1000,response=data['response'],sources=data['sources'],
                mode=data['response_mode'],status=data['answer_status'],trace=trace.summary(response.status_code)))
            token=data.get('context_token')
        result['external_calls']=external.call_count
    after=fingerprints()
    result['passed']=sum(row['passed'] for row in result['rows'])
    result['integrity']=dict(before=before,after=after,unchanged=before==after)
    (directory/'api.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    integrity_path=directory/'integrity.json'
    integrity=json.loads(integrity_path.read_text(encoding='utf-8'))
    integrity.update(after=after,unchanged=integrity['before']==after)
    integrity_path.write_text(json.dumps(integrity,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'],samples=len(result['rows']),external_calls=external.call_count,data_unchanged=result['integrity']['unchanged'])))


if __name__=='__main__':
    main()
