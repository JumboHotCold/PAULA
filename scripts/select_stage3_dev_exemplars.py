"""Select a small canonical-only prototype expansion from DEV; never TEST."""
import json
from pathlib import Path


def locale(text):
    words=set(text.lower().split())
    if words&set('unsa unsay kinsa maayong imong nimo akong gikapoy nahuman ganahan dako tabang nako ko nimo'.split()):return 'ceb'
    if words&set('ano maraming nalulungkot patawa nagawa masaya paborito babalik maaari akin hilig'.split()):return 'fil'
    return 'en'


def main():
    root=Path('artifacts/stage3')
    rows=json.loads((root/'sets/dev.json').read_text(encoding='utf-8'))
    path=Path('chatbot/config/conversation.json');config=json.loads(path.read_text(encoding='utf-8'))
    selected={}
    for row in rows:
        if row['group']!='social' or row['operation']!='clean':continue
        key=(row['intent'],locale(row['query']))
        if key not in selected:selected[key]=row
    additions=[]
    for row in selected.values():
        examples=config['semantic']['exemplars'].setdefault(row['intent'],[])
        if row['query'] not in examples:
            examples.append(row['query']);additions.append(dict(source_id=row['source_id'],intent=row['intent'],locale=locale(row['query']),query=row['query']))
    path.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (root/'dev_prototype_additions.json').write_text(json.dumps(additions,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Added {len(additions)} canonical DEV prototypes; no typo variants or TEST file used.')


if __name__=='__main__':main()
