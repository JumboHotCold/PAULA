"""Public synthetic evaluation only. The real-student held-out file stays private."""
import argparse,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage3_engine import Engine
from chatbot.query_normalization import person_key


def identifiers(row):
    values={(row.get('record_type'),row.get('record_id'))}
    values|={(r.get('record_type'),r.get('record_id')) for r in row.get('supporting_sources') or ()}
    return values


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',required=True)
    parser.add_argument('--split',choices=('dev','test','golden'),default='dev');parser.add_argument('--no-spacing',action='store_true')
    parser.add_argument('--only-spacing',action='store_true')
    parser.add_argument('--root',default='/app/artifacts/stage3');args=parser.parse_args()
    root=Path(args.root)
    path=root/'sets'/f'{args.split}.json';cases=json.loads(path.read_text(encoding='utf-8'))
    manifest=json.loads((root/'sets/manifest.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==manifest['files'][args.split]['sha256']
    if args.only_spacing:cases=[row for row in cases if row.get('operation')=='spacing']
    engine=Engine(spacing=not args.no_spacing)
    report=dict(label=args.label,split=args.split,startup_ms=engine.startup_ms,providers_enabled=False,rows=[],set_sha256=manifest['files'][args.split]['sha256'])
    for i,case in enumerate(cases):
        thread=case.get('source_id')+':'+str(i)
        for prior in case.get('prior',[]):engine.run(prior,thread=thread)
        row=engine.run(case['query'],thread=thread)
        row.update({key:value for key,value in case.items() if key not in row})
        if 'intent' in case:row['expected_intent']=case['intent']
        evidence=row['retrieval']
        gold={tuple(value) for value in case.get('gold',[])}
        def match(item):
            return bool(gold&identifiers(item)) or bool(case.get('gold_name') and person_key(item.get('personnel_name',''))==person_key(case['gold_name']))
        row['top1']=bool(evidence and match(evidence[0]));row['top3']=any(match(item) for item in evidence)
        row['wrong_person']=bool(case.get('gold_name') and any(item.get('personnel_name') and person_key(item['personnel_name'])!=person_key(case['gold_name']) for item in evidence))
        answered=bool(row['sources'] or row['action'])
        if 'intent' in case:row['passed']=row['intent']==case['intent']
        elif case.get('expect_refusal'):row['passed']=not answered and row['http_status']==200
        elif case.get('expect_parts'):row['passed']=len(row['parts'])==case['expect_parts'] and row['status']=='ok'
        elif case.get('expect_partial'):row['passed']=bool(row['sources']) and row['status']=='partial'
        elif case.get('expect_evidence'):row['passed']=answered
        else:row['passed']=row['top3']
        row['avoidable_clarification']=row['status']=='clarification' and bool(case.get('gold') or case.get('gold_name'))
        row['failure_cause']=None if row['passed'] else ('ERROR' if row['http_status']>=500 or row['status']=='unavailable' else
            'WRONG_INTENT' if 'intent' in case else 'BAD_CONTEXT' if case['group']=='followup' else
            'GENERATION_REJECTED' if row['status']=='selection_rejected' else 'NO_KNOWLEDGE' if not gold and not case.get('gold_name') else 'BAD_RETRIEVAL')
        report['rows'].append(row)
        if i%100==0:print(f'{args.label}/{args.split}: {i}/{len(cases)}',flush=True)
    directory=root/'measurements';directory.mkdir(exist_ok=True)
    (directory/f'{args.label}-{args.split}.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    print(json.dumps(dict(label=args.label,split=args.split,n=len(cases),passed=sum(r['passed'] for r in report['rows']))))


if __name__=='__main__':main()
