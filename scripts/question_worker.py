"""Docker-side worker for an explicitly invoked, user-owned question file."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage3_engine import Engine


def main():
    request=json.load(sys.stdin)
    engine=Engine(providers=bool(request.get('providers',True)))
    print('PAULA_META\t'+json.dumps(dict(startup_ms=engine.startup_ms,scope='isolated guest API process; excludes HTTP/browser transport')),flush=True)
    for index,case in enumerate(request['questions']):
        row=engine.run(case['query'],thread=case.get('thread'))
        row['index']=index+1
        row['reply_preview']=row['reply'][:request.get('preview_chars',240)]
        # The caller explicitly requests these private-file outputs. No context
        # token, cookie, account identity or hidden provider detail is returned.
        output={key:row[key] for key in ('index','query','normalized','intent','method','reason_code','reply_preview','top_source','latency_ms','trace')}
        print('PAULA_RESULT\t'+json.dumps(output,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
