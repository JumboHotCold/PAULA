"""Threshold grid on DEV only. TEST/private questions are never opened."""
import json,time
from pathlib import Path
from unittest.mock import patch
from chatbot.embedding_runtime import runtime
from chatbot.dialogue import social_router,route_turn
from chatbot.spelling import prepare_vocabulary


def main():
    root=Path('artifacts/stage3')
    cases=json.loads((root/'sets/dev.json').read_text(encoding='utf-8'))
    social_router.prepare(runtime.initialize());prepare_vocabulary()
    cache={}
    grid=[]
    for minimum in (.55,.60,.65,.70,.75):
        for margin in (.05,.08,.12):
            def classify(text):
                if text not in cache:cache[text]=social_router.rank(text)
                ranked=cache[text]
                if not ranked or ranked[0][1]=='knowledge' or ranked[0][0]<minimum or ranked[0][0]-ranked[1][0]<margin:return None
                return ranked[0][1],round(ranked[0][0],4)
            correct=social_correct=negatives=false_positive=0
            with patch.object(social_router,'classify',side_effect=classify):
                for row in cases:
                    predicted=route_turn(row['query']).kind
                    correct+=predicted==row['intent']
                    if row['group']=='social':social_correct+=predicted==row['intent']
                    else:
                        negatives+=1;false_positive+=predicted!='knowledge'
            grid.append(dict(minimum=minimum,margin=margin,correct=correct,social_correct=social_correct,institutional_n=negatives,false_positive=false_positive))
    # The existing threshold is preferred unless an equally safe grid point
    # gains at least one percentage point of the development cases.
    current=next(row for row in grid if (row['minimum'],row['margin'])==(.65,.08))
    safe=[row for row in grid if row['false_positive']==0]
    best=max(safe,key=lambda row:row['correct']) if safe else current
    selected=best if best['correct']-current['correct']>=len(cases)*.01 else current
    result=dict(split='dev',n=len(cases),grid=grid,selected=selected,policy='zero institutional false positives; retain existing thresholds unless >=1pp development gain',test_used=False)
    (root/'calibration.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
