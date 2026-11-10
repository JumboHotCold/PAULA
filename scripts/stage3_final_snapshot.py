"""Read-only final integrity, index and personnel-review snapshot."""
from io import StringIO
import json,runpy
from pathlib import Path
from django.core.management import call_command
from chatbot.models import StaffMember,WebResource,FAQ
from chatbot.personnel import structured_person
from chatbot.query_normalization import person_key
from chatbot.embedding_runtime import runtime
from chatbot.dialogue import social_router
from chatbot.spelling import prepare_vocabulary
from chatbot.rag import RAGSearcher


def main():
    root=Path('artifacts/stage3')
    fingerprints=runpy.run_path('scripts/audit_stage1.py',run_name='audit_module')['fingerprints']
    baseline=json.loads((root/'baseline.json').read_text(encoding='utf-8'))
    final=fingerprints()
    (root/'integrity.json').write_text(json.dumps(dict(before=baseline['integrity'],after=final,unchanged=baseline['integrity']==final),indent=2),encoding='utf-8')
    output=StringIO();call_command('audit_knowledge',strict=True,stdout=output)
    (root/'knowledge_audit.json').write_text(output.getvalue(),encoding='utf-8')
    model=runtime.initialize();social_router.prepare(model);prepare_vocabulary()
    rag=RAGSearcher();rag.model=model
    official=[dict(person,url=obj.url,last_scraped=obj.last_scraped.isoformat()) for obj in WebResource.objects.filter(category='Website personnel')
              for person in [structured_person(obj)] if person]
    review=[]
    for staff in StaffMember.objects.order_by('pk'):
        query=f'Who is {staff.name}?';outcome=rag.retrieve(query,limit=3)
        words=person_key(staff.name).split()
        related=[row for row in official if person_key(row['name']).split() and (person_key(row['name']).split()[0],person_key(row['name']).split()[-1])==(words[0],words[-1])]
        review.append(dict(local_name=staff.name,local_position=staff.position,query=query,status=outcome.status,
                          top1_identity_match=bool(outcome.evidence and person_key(outcome.evidence[0].get('personnel_name',''))==person_key(staff.name)),
                          possible_website_variants=related,evidence=outcome.evidence))
    pbmo=list(FAQ.objects.filter(question__icontains='Director').filter(question__icontains='PBMO').values('id','question','answer','source_type','source_office'))
    (root/'personnel_review.json').write_text(json.dumps(dict(staff=review,pbmo_faq=pbmo,pbmo_website=[row for row in official if 'Publication' in row['role']]),indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(data_unchanged=baseline['integrity']==final,staff_top1=sum(r['top1_identity_match'] for r in review),staff_count=len(review))))


if __name__=='__main__':main()
