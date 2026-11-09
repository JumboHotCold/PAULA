"""Summarize frozen public measurements; export every failure for review."""
from collections import Counter
import csv,json,math
from pathlib import Path


def quantile(values,fraction):
    values=sorted(values)
    return round(values[max(0,math.ceil(len(values)*fraction)-1)],3) if values else None


def metrics(rows):
    n=len(rows)
    result=dict(n=n,passed=sum(row['passed'] for row in rows),
        accuracy=round(sum(row['passed'] for row in rows)/n,6) if n else None,
        top1=sum(row['top1'] for row in rows),top3=sum(row['top3'] for row in rows),
        clarifications=sum(row['status']=='clarification' for row in rows),
        source_present_clarifications=sum(row.get('avoidable_clarification',False) for row in rows),
        confirmed_avoidable_clean_faq=sum(row['group']=='faq' and row.get('operation')=='clean' and row['status']=='clarification' for row in rows),
        errors=sum(row['http_status']>=500 or row['status'] in ('error','unavailable') for row in rows),
        wrong_person=sum(row['wrong_person'] for row in rows),outcomes=dict(Counter(row['status'] for row in rows)),
        p50_api_ms=quantile([row['trace']['total_ms'] for row in rows],.5),p95_api_ms=quantile([row['trace']['total_ms'] for row in rows],.95),
        p50_observer_ms=quantile([row['latency_ms'] for row in rows],.5),p95_observer_ms=quantile([row['latency_ms'] for row in rows],.95))
    if rows and rows[0]['group']=='institutional':result['social_false_positives']=sum(row['intent']!='knowledge' for row in rows)
    stages={name for row in rows for name in row['trace']['stages']}
    result['stages']={name:dict(n=sum(name in row['trace']['stages'] for row in rows),
        p50_ms=quantile([row['trace']['stages'][name]['inclusive_ms'] for row in rows if name in row['trace']['stages']],.5),
        p95_ms=quantile([row['trace']['stages'][name]['inclusive_ms'] for row in rows if name in row['trace']['stages']],.95)) for name in sorted(stages)}
    return result


def main():
    root=Path('artifacts/stage3');result={};failures=[];gaps=[]
    for label in ('before','after'):
        result[label]={}
        for split in ('dev','test','golden'):
            report=json.loads((root/'measurements'/f'{label}-{split}.json').read_text(encoding='utf-8'))
            rows=report['rows']
            result[label][split]=dict(startup_ms=report['startup_ms'],all=metrics(rows),
                groups={group:metrics([row for row in rows if row['group']==group]) for group in sorted({row['group'] for row in rows})})
            if split=='golden':
                result[label][split]['faq_clean']=metrics([row for row in rows if row['group']=='faq' and row.get('operation')=='clean'])
                result[label][split]['staff_clean']=metrics([row for row in rows if row['group']=='staff' and row.get('operation')=='clean'])
                result[label][split]['spacing']=metrics([row for row in rows if row.get('operation')=='spacing'])
                refusals=[row for row in rows if row.get('expect_refusal')]
                result[label][split]['correct_refusal']=dict(n=len(refusals),correct=sum(not(row['sources'] or row['action']) and row['status'] in ('no_match','clarification','conflict','ambiguous','selection_rejected') for row in refusals))
            for row in rows:
                if not row['passed']:
                    cause=row['failure_cause']
                    if row.get('expect_refusal') and (row['sources'] or row['action']):cause='BAD_RETRIEVAL'
                    if row['group']=='faq' and row['mode'] in ('identity','social_bundle') and 'PAULA' in row['query']:
                        cause='BAD_RETRIEVAL' # scoring mismatch retained and explicitly explained
                    failures.append(dict(label=label,split=split,group=row['group'],query=row['query'],expected=row.get('expected_intent') or row.get('gold') or row.get('gold_name'),
                        actual=row['intent'],status=row['status'],cause=cause,reason_code=row['reason_code'],top_source=row['top_source'].get('title',''),
                        preview=row['reply'][:200]))
                if label=='after' and split=='golden' and not row['sources'] and not row['action']:
                    gaps.append(dict(query=row['query'],expected_source=row.get('gold'),status=row['status'],
                        classification='RETRIEVAL_OR_GROUNDING_GAP' if row.get('gold') or row.get('gold_name') else 'UNSUPPORTED_OR_AMBIGUOUS_LABEL_REVIEW'))
    ablation=json.loads((root/'measurements/no-spacing-golden.json').read_text(encoding='utf-8'))
    result['spacing_disabled']=metrics(ablation['rows'])
    result['protocol']=dict(test_tuning=False,private_student_file_accessed=False,provider_calls='disabled in synthetic measurements; opt-in live smoke not run',
        source_present_clarification='upper bound requiring manual review; not proof of avoidability',latency='API trace excludes transport/browser; observer includes introspection/navigation score probes')
    (root/'comparison.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    (root/'knowledge_gaps.json').write_text(json.dumps(gaps,indent=2,ensure_ascii=False),encoding='utf-8')
    with (root/'failures.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(failures[0]) if failures else ['query']);writer.writeheader();writer.writerows(failures)
    for label in ('before','after'):
        for split in ('dev','test','golden'):
            print(label,split,json.dumps({group:{key:value for key,value in data.items() if key in ('n','passed','accuracy','top1','top3','wrong_person','social_false_positives','clarifications','errors','p50_api_ms','p95_api_ms')} for group,data in result[label][split]['groups'].items()}))
    print('spacing',json.dumps({name:{key:data[key] for key in ('n','top1','top3')} for name,data in [('enabled',result['after']['golden']['spacing']),('disabled',result['spacing_disabled'])]}))


if __name__=='__main__':main()
