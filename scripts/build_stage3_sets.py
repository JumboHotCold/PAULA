"""Freeze public synthetic sets. Never opens any private student-question file."""
import hashlib,json,random,re
from pathlib import Path
from chatbot.models import FAQ,StaffMember,Location

SOCIAL={
 'greeting':['Hey there assistant','Good day PAULA','Hello again friend','Maayong gabii','Magandang hapon po','Kumusta po muli'],
 'identity':['Please explain who you are','I would like to know your name','Could you say your full name','Ano ang ibig sabihin ng pangalan mo','Unsay ngalan nimo','Kinsa man ka','Please describe your role to me'],
 'capabilities':['How can you assist me today','What kinds of help can you give','What are your abilities','Ano ang maitutulong mo sa akin','Unsa imong ikatabang nako','Pwede ba ta magstorya','Can u help me understand a question'],
 'thanks':['Much appreciated PAULA','Thank you for explaining that','That helped me a lot','Salamat sa imong tabang','Dako akong pasalamat','Maraming salamat sa iyo','Thank u very much','Salamat po talaga'],
 'farewell':['I have to go now','Bye for now PAULA','Talk to you another time','Paalam at ingat','Sige una sa ko','Babalik ako mamaya'],
 'wellbeing':['How are you feeling today','Is everything okay with you','How have you been','Okay ka lang ba','Kumusta imong adlaw','Maayo ra ka'],
 'joke':['Could you share something funny','Please cheer me up with a joke','I would like to hear a joke','Patawa ka naman ng konti','Pwede ko nimo pakataw on','Naa kay joke para nako'],
 'support':['I feel exhausted after today','I am worried and need encouragement','I had a difficult day','Nalulungkot ako ngayon','Gikapoy ko karon','Medyo kabado ako'],
 'celebration':['I finished my project today','I am proud of what I accomplished','I finally understand it','Nagawa ko na sa wakas','Nahuman na nako akong trabaho','Masaya ako sa natapos ko'],
 'preference':['What food do you enjoy most','What do you like doing for fun','Do you enjoy listening to music','Ano ang hilig mong gawin','Unsa imong ganahan nga pagkaon','May paborito ka bang kanta'],
 'affirmation':['Yes please','Oo po','Sure po','Opo paula'],
 'negation':['No please','Hindi po','Dili paula','No thank you po'],
 'acknowledgement':['Okay po','Noted paula','Sige naman','Gets ko na po'],
}
TOPICS=['enrollment requirements','scholarship eligibility','undergraduate programs','library policies','tuition fees',
        'Registrar documents','Finance office hours','CEIT faculty','PBMO publication procedure','clinic services']
FRAMES=['Please explain {}','Can you help me with {}','Where can I find information about {}','I need verified details about {}',
        'What should I know about {}','Hi, tell me about {}','Thanks, explain {}','What are the rules for {}',
        'Paki explain ang {}','Unsay impormasyon bahin sa {}','May impormasyon ba tungkol sa {}','Help me understand {}']


def variants(text):
    from scripts.evaluate_spelling import perturb,OPS
    return [(op,perturb(text,op,8675309+i)) for i,op in enumerate(OPS)]


def main():
    root=Path('artifacts/stage3/sets')
    root.mkdir(parents=True,exist_ok=True)
    assert not (root/'manifest.json').exists(),'Frozen sets already exist'
    bases=[]
    for intent,texts in SOCIAL.items():
        bases.extend(dict(group='social',intent=intent,query=text,source_id=f'social:{intent}:{i}') for i,text in enumerate(texts))
    for i,topic in enumerate(TOPICS):
        for j,frame in enumerate(FRAMES):bases.append(dict(group='institutional',intent='knowledge',query=frame.format(topic),source_id=f'institutional:{i}:{j}'))
    buckets={}
    for group in ('social','institutional'):
        values=[b for b in bases if b['group']==group]
        random.Random(314159).shuffle(values)
        boundary=int(len(values)*.7)
        for i,row in enumerate(values):buckets[row['source_id']]='dev' if i<boundary else 'test'
    splits={'dev':[],'test':[]}
    for base in bases:
        for op,query in variants(base['query']):
            splits[buckets[base['source_id']]].append(dict(base,query=query,operation=op,canonical=base['query']))
    golden=[]
    for obj in FAQ.objects.order_by('pk'):
        for op,query in variants(obj.question):
            golden.append(dict(group='faq',source_id=f'faq:{obj.pk}',query=query,canonical=obj.question,gold=[['faq',obj.pk]],operation=op))
        if obj.question.startswith('What is '):
            golden.append(dict(group='faq',source_id=f'faq:{obj.pk}',query='Please explain '+obj.question[8:],gold=[['faq',obj.pk]],operation='paraphrase'))
    for model,kind in ((StaffMember,'staff'),(Location,'location')):
        for obj in model.objects.order_by('pk'):
            text=f'Who is {obj.name}?' if kind=='staff' else f'Where is {obj.name}?'
            for op,query in variants(text):
                golden.append(dict(group=kind,source_id=f'{kind}:{obj.pk}',query=query,canonical=text,
                                   gold_name=obj.name if kind=='staff' else None,gold=[[model._meta.model_name,obj.pk]],operation=op))
    # These are source labels, not invented answers; mapping is explicit and
    # includes alternatives when the KB has duplicate attributable records.
    mappings=[('What programs are offered at SPUS?',[
        'What college courses are available at SPUS?','Anong mga kurso ang inaalok sa SPUS?',
        'Unsa nga mga kurso ang gitanyag sa SPUS?']),
        ('Why choose SPUS?',['Why should I study at SPUS?','Bakit ko pipiliin ang SPUS?','Ngano mopili ko sa SPUS?']),
        ('What is SPUS?',['Please describe SPUS','Ano ang SPUS?','Unsa ang SPUS?'])]
    from chatbot.query_normalization import faq_question_key
    for source,paraphrases in mappings:
        ids=[['faq',row.pk] for row in FAQ.objects.all() if faq_question_key(row.question)==faq_question_key(source)]
        for query in paraphrases:
            golden.append(dict(group='faq',source_id='manual:'+source,query=query,gold=ids,operation='multilingual',label_review='source-question mapping'))
    for query in ('What is the exact tuition fee for 2037?','Who is the dean of Zephyr College?',
                  'Give me the private password of the president','When is the final exam in 2099?',
                  'What is my student account balance?','What is the approved quantum teleportation program?',
                  'Where is that office?','Who is the director?'):
        golden.append(dict(group='refusal',source_id='refusal:'+query,query=query,expect_refusal=True,operation='unsupported_or_ambiguous'))
    golden.extend([
        dict(group='compound',source_id='compound:roles',query='Who is the ICT Director and CEIT Dean?',expect_parts=2),
        dict(group='compound',source_id='compound:partial',query='Who is the ICT Director and who is the dean of Zephyr College?',expect_partial=True),
        dict(group='followup',source_id='followup:enrollment',query='How about for transferees?',prior=['What are the enrollment requirements?','Old/continuing college student'],expect_evidence=True),
        dict(group='followup',source_id='followup:switch',query='What programs are offered at SPUS?',prior=['Who is the CEIT dean?'],expect_evidence=True),
    ])
    files={**splits,'golden':golden}
    manifest={'seed':314159,'split_unit':'source phrase; all perturbations stay in the same split',
              'status':'agent-authored synthetic split; not the private real-student held-out set','groups':{},'files':{}}
    for name,rows in files.items():
        path=root/f'{name}.json'
        path.write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
        manifest['files'][name]=dict(rows=len(rows),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    manifest['groups']={group:{split:len({r['source_id'] for r in rows if r['group']==group}) for split,rows in splits.items()} for group in ('social','institutional')}
    assert not ({r['source_id'] for r in splits['dev']}&{r['source_id'] for r in splits['test']})
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest))


if __name__=='__main__':main()
