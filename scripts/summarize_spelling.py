"""Summarize frozen development measurements; no model/API/DB calls."""
from collections import Counter
import json
import math
from pathlib import Path
from chatbot.query_normalization import person_key


def percentile(values, p):
    values=sorted(values)
    return round(values[max(0,math.ceil(len(values)*p)-1)],3) if values else None


def metrics(rows):
    result=dict(n=len(rows),p50_ms=percentile([r['elapsed_ms'] for r in rows],.5),
                p95_ms=percentile([r['elapsed_ms'] for r in rows],.95),
                outcomes=dict(Counter(r.get('status',r['route']) for r in rows)))
    if rows and 'correct' in rows[0]:
        result.update(correct=sum(r['correct'] for r in rows),accuracy=round(sum(r['correct'] for r in rows)/len(rows),6))
    else:
        for k in ('top1','top3'):
            result[k]=sum(r[k] for r in rows)
            result[k+'_recall']=round(result[k]/len(rows),6) if rows else None
        if rows and rows[0]['group']=='staff':
            # Credential suffix differences are retained separately. A fully
            # different literal name is the wrong-person safety measure.
            result['wrong_person']=sum(any(e.get('personnel_name') and person_key(e['personnel_name'])!=person_key(r['gold'])
                                            for e in r['evidence']) for r in rows)
            result['raw_name_variant_rows']=sum(r['wrong_person'] for r in rows)
            for k in ('top1','top3'):
                count=sum(any(person_key(e.get('personnel_name',''))==person_key(r['gold']) for e in r['evidence'][:1 if k=='top1' else 3]) for r in rows)
                result[k+'_identity_key']=count
                result[k+'_identity_recall']=round(count/len(rows),6)
    return result


def main():
    directory=Path('artifacts/spelling')
    reports={name:json.loads((directory/f'{name}.json').read_text(encoding='utf-8')) for name in ('before','after')}
    assert reports['before']['corpus_sha256']==reports['after']['corpus_sha256']
    result=dict(corpus_sha256=reports['after']['corpus_sha256'],samples=len(reports['after']['rows']),groups={},operations={})
    for name,report in reports.items():
        result['groups'][name]={group:metrics([r for r in report['rows'] if r['group']==group])
                               for group in ('faq','staff','location','intent','negative')}
        result['operations'][name]={group:{operation:metrics([r for r in report['rows'] if r['group']==group and r['operation']==operation])
                                          for operation in ('clean','transposition','deletion','insertion','substitution','doubled','spacing','case')}
                                   for group in ('faq','staff','location','intent')}
        result.setdefault('institutional_social_intercepts',{})[name]=[
            dict(query=r['query'],group=r['group'],route=r['route']) for r in report['rows']
            if r['group'] in ('faq','staff','location','negative') and r['route']!='knowledge']
    (directory/'comparison.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result['groups'],indent=2))


if __name__=='__main__':
    main()
