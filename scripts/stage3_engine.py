"""Reusable in-process guest API observer. No private files are opened here."""
from contextlib import nullcontext
from dataclasses import asdict
import time
from unittest.mock import patch
from uuid import uuid4
from django.conf import settings
from django.db import connection
from django.test import override_settings
from rest_framework.test import APIRequestFactory
from chatbot import views
from chatbot.dialogue import route_turn,social_router
from chatbot.embedding_runtime import runtime
from chatbot.performance import capture_trace
from chatbot.rag import RAGSearcher
from chatbot.spelling import prepare_vocabulary,matching_plan


class Engine:
    def __init__(self,*,providers=False,spacing=True):
        started=time.perf_counter()
        self.model=runtime.initialize();social_router.prepare(self.model)
        prepare_vocabulary()
        self.rag=RAGSearcher();self.rag.model=self.model
        views.bot.rag=self.rag
        if not providers:views.bot.client=views.bot.openai_client=views.bot.gemini_model=None
        self.providers=providers
        self.spacing=spacing
        self.startup_ms=(time.perf_counter()-started)*1000
        self.threads={}

    def run(self,query,*,thread=None):
        thread=thread or str(uuid4())
        if thread not in self.threads and len(self.threads)>=100:self.threads.pop(next(iter(self.threads)))
        state=self.threads.setdefault(thread,dict(id=str(uuid4()),token=None,history=[]))
        outcomes=[];answers=[]
        original_retrieve=views.bot._retrieve
        original_process=views.bot.process_query
        def retrieve(*args,**kwargs):
            outcome=original_retrieve(*args,**kwargs);outcomes.append((args[0],outcome));return outcome
        def process(*args,**kwargs):
            answer=original_process(*args,**kwargs);answers.append(answer);return answer
        started=time.perf_counter()
        spacing_context=nullcontext()
        import chatbot.spelling as spelling
        if not self.spacing and hasattr(spelling,'spacing_policy'):spacing_context=spelling.spacing_policy(False)
        with spacing_context,override_settings(PAULA_LOG_UNANSWERED_QUERIES=False):
            plan=matching_plan(query);route=route_turn(query)
            request=APIRequestFactory().post('/api/chat',dict(message=query,mode='guest',context_id=state['id'],
                context_token=state['token'],history=state['history']),format='json')
            with patch.object(views.bot,'_retrieve',side_effect=retrieve),patch.object(views.bot,'process_query',side_effect=process),capture_trace('stage3_guest') as trace:
                def sql(execute,statement,params,many,context):
                    start=time.perf_counter()
                    try:return execute(statement,params,many,context)
                    finally:trace.sql_count+=1;trace.sql_ms+=(time.perf_counter()-start)*1000
                with connection.execute_wrapper(sql):response=views.chat_api(request)
        data=response.data
        actual=answers[-1] if answers else None
        effective=getattr(actual,'context_query','') if data.get('sources') or data.get('action') else plan.matching
        rows=[row for _,outcome in outcomes for row in outcome.evidence]
        if data.get('action') and not rows:
            # Separate retrieval score for navigation; the map action itself
            # is assessed independently, not claimed to be a vector hit.
            rows=self.rag.retrieve(effective or plan.matching,limit=3).evidence
        status=data.get('answer_status','error')
        reason={'no_match':'NO_MATCH','clarification':'CLARIFICATION','conflict':'SOURCE_CONFLICT','ambiguous':'AMBIGUOUS_EVIDENCE',
                'selection_rejected':'GENERATION_REJECTED','unavailable':'ERROR','partial':'PARTIAL_ANSWER'}.get(status,status.upper())
        state['token']=data.get('context_token')
        state['history']=(state['history']+[{'role':'user','content':query},{'role':'assistant','content':data.get('response','')}])[-8:]
        assert not data.get('saved') and data.get('conversation_id') is None,'Guest persistence violation'
        return dict(query=query,normalized=effective or plan.matching,intent=route.kind,method=route.method,reason_code=reason,
            http_status=response.status_code,status=status,reply=data.get('response',''),mode=data.get('response_mode'),
            sources=data.get('sources',[]),top_source=(data.get('sources') or [{}])[0],action=data.get('action'),
            action_data=data.get('action_data'),parts=data.get('answer_parts',[]),suggestions=data.get('suggestions',[]),
            retrieval=[{key:row.get(key) for key in ('record_type','record_id','personnel_name','question','distance','supporting_sources','review_notes')} for row in rows[:3]],
            latency_ms=(time.perf_counter()-started)*1000,trace=trace.summary(response.status_code))
