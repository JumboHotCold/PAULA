"""Read-only pre-change Stage 3 traces and integrity snapshot; Docker shell only."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import numpy as np
from chatbot import views
from chatbot.dialogue import route_turn, social_router, SOCIAL_EXAMPLES
from chatbot.embedding_runtime import runtime
from chatbot.rag import RAGSearcher
from chatbot.spelling import prepare_vocabulary, matching_plan, nearest
from chatbot.models import StaffMember, WebResource
from chatbot.personnel import lookup_kind
from chatbot.query_normalization import person_key

QUERIES=('tel me abt urself','wat r the programs offerd','where is the registrr',
         'thank u po','salamat gyud','salamat kaayo','maraming salamat po','daghang salamat','thanks a lot')


def main():
    output=Path('artifacts/stage3')
    output.mkdir(parents=True,exist_ok=True)
    assert not (output/'baseline.json').exists(),'Baseline already frozen'
    fingerprints=runpy.run_path('scripts/audit_stage1.py',run_name='audit_module')['fingerprints']
    result=dict(measured_at=datetime.now(timezone.utc).isoformat(),integrity=fingerprints(),rows=[],staff=[])
    (output/'conversation_before.json').write_bytes(Path('chatbot/config/conversation.json').read_bytes())
    model=runtime.initialize()
    social_router.prepare(model)
    lexicon=prepare_vocabulary()
    rag=RAGSearcher()
    rag.model=model
    views.bot.rag=rag
    for query in QUERIES:
        plan=matching_plan(query)
        route=route_turn(query)
        scores=social_router.matrix @ np.asarray(model.encode(plan.matching,normalize_embeddings=True))
        ranked=sorted([(max(float(scores[i]) for i,label in enumerate(social_router.labels) if label==kind),kind)
                       for kind in SOCIAL_EXAMPLES],reverse=True)
        result['rows'].append(dict(query=query,plan=asdict(plan),route=asdict(route),
            candidates={word:nearest(word,lexicon) for word in query.split() if word not in lexicon.words},
            nearest_name={word:sorted(name for name in lexicon.names if abs(len(word)-len(name))<=1 and
                __import__('chatbot.spelling',fromlist=['edit_distance']).edit_distance(word,name)<=1) for word in query.split() if word not in lexicon.words},
            semantic=ranked[:3],margin=ranked[0][0]-ranked[1][0]))
    for staff in StaffMember.objects.order_by('pk'):
        query=f'Who is {staff.name}?'
        route=route_turn(query)
        outcome=rag.retrieve(query,limit=3)
        result['staff'].append(dict(id=staff.pk,name=staff.name,position=staff.position,query=query,
            kind=lookup_kind(query),route=asdict(route),status=outcome.status,
            exact_identity_hit=bool(outcome.evidence and person_key(outcome.evidence[0].get('personnel_name',''))==person_key(staff.name)),
            evidence=outcome.evidence))
    result['personnel_review']=list(WebResource.objects.filter(category='Website personnel',title__icontains='Dean').values('title','content','url','last_scraped'))
    (output/'baseline.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps(dict(rows=len(result['rows']),staff_failures=[r['name'] for r in result['staff'] if not r['exact_identity_hit']])))


if __name__=='__main__':main()
