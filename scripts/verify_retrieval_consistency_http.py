"""Provider-free supported query checks through the active Vite proxy."""
import json
from pathlib import Path
import time
import urllib.request


def main():
    checks=[]
    def ask(query, expected, prior=None):
        payload={'message':query,'mode':'guest','context_id':'retrieval-review'}
        if prior:
            payload['history']=[{'role':'user','content':prior['query']},{'role':'assistant','content':prior['response']}]
            payload['context_token']=prior.get('context_token')
        request=urllib.request.Request('http://localhost:5173/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        start=time.perf_counter()
        with urllib.request.urlopen(request,timeout=90) as response:data=json.load(response)
        assert expected in data['response'],(query,data)
        assert data['saved'] is False
        if expected in ('Marie Rosanne Mallillin','Nikko T. Ederio','Karen T. Plaza'):
            assert len(data['sources'])==1 and data['sources'][0]['url']=='https://spus.edu.ph/administrator/'
        record={'query':query,'passed':True,'elapsed_ms':round((time.perf_counter()-start)*1000,2),
                'response':data['response'],'sources':data['sources']}
        checks.append(record)
        print(json.dumps({k:record[k] for k in ('query','passed','elapsed_ms')}),flush=True)
        return {**record,'context_token':data.get('context_token')}
    first=ask('Who is the University President?','Marie Rosanne Mallillin')
    for q in ('Who is currently the University President?','Who is the university president now?',
              'Who is the university president today?','Sino ang pangulo ng SPUS?',
              'Who is Sr. Marie Rosanne Mallillin?'):
        ask(q,'Marie Rosanne Mallillin')
    ask('Who is the Vice President for Academic Services?','Nikko T. Ederio')
    ask('Who is the VP for Academics?','Nikko T. Ederio')
    ask('Who is currently holding that role?','Marie Rosanne Mallillin',first)
    ask('How about the VP for Academics?','Nikko T. Ederio',first)
    ask('Who is the JSIT moderator?','Khen Malaque')
    ask('Who is the CEIT dean?','Karen T. Plaza')
    ask('Who is the PBMO director?','I found conflicting information')
    output=Path(__file__).resolve().parent.parent/'PAULA_RETRIEVAL_LIVE_CHECKS.json'
    output.write_text(json.dumps({'passed':len(checks),'checks':checks},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{len(checks)} live guest checks passed.')


if __name__=='__main__':main()
