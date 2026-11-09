"""Recheck public Log #9 cases against current PostgreSQL; guest only."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage3_engine import Engine


def main():
    engine=Engine()
    cases=[('tel me abt urself','identity'),('wat r the programs offerd','evidence'),('where is the registrr','navigation'),
           ('thank u po','thanks'),('salamat gyud','thanks'),('salamat kaayo','thanks'),('maraming salamat po','thanks'),
           ('daghang salamat','thanks'),('thanks a lot','thanks'),('who is the dean of ceit','evidence')]
    rows=[]
    for query,expected in cases:
        row=engine.run(query)
        row['expected']=expected
        row['passed']=(row['mode']==expected if expected in ('identity','thanks') else bool(row['sources']) if expected=='evidence' else row['action']=='navigate_map')
        rows.append(row)
    for thread,flow in [('smalltalk',[('hi','greeting'),('YES','affirmation')]),
                        ('enrollment',[('what are the requirements for enrollment','clarification'),('how about for transferees','evidence')])]:
        for query,expected in flow:
            row=engine.run(query,thread=thread)
            row['expected']=expected
            row['passed']=bool(row['sources']) if expected=='evidence' else row['status']=='clarification' if expected=='clarification' else row['mode']==expected
            rows.append(row)
    report=dict(rows=rows,n=len(rows),passed=sum(row['passed'] for row in rows),providers_enabled=False)
    Path('artifacts/stage3/manual_after.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(n=len(rows),passed=report['passed'])))


if __name__=='__main__':main()
