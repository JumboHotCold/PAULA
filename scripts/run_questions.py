"""Run your private questions yourself; uses stdlib and the Docker web service.

python scripts/run_questions.py <questions.txt|csv|json|jsonl> [--csv output.csv]
JSON(L) objects may specify query/question and an optional thread identifier.
Plain-text questions run independently. The file is never copied into the repo
or container; content is sent over stdin. Output CSV stays with the input by
default. This tool deliberately prints the private inputs/reply previews to
your terminal and CSV; it does not enable application query logging.
"""
import argparse,csv,json,subprocess,sys
from pathlib import Path


def load_questions(path):
    text=path.read_text(encoding='utf-8-sig')
    if path.suffix.lower()=='.csv':rows=list(csv.DictReader(text.splitlines()))
    elif path.suffix.lower()=='.json':rows=json.loads(text)
    elif path.suffix.lower()=='.jsonl':rows=[json.loads(line) for line in text.splitlines() if line.strip()]
    else:rows=[line.strip() for line in text.splitlines() if line.strip()]
    result=[]
    for row in rows:
        value={'query':row} if isinstance(row,str) else dict(row)
        query=value.get('query',value.get('question'))
        if not isinstance(query,str) or not query.strip():raise ValueError('Each row must contain query/question text')
        item={'query':query}
        if isinstance(value.get('thread'),str):item['thread']=value['thread'][:100]
        result.append(item)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file',type=Path);parser.add_argument('--csv',type=Path)
    parser.add_argument('--container',default='paulibot_web')
    parser.add_argument('--no-providers',action='store_true',help='Use local grounded fallback only, without external model calls')
    args=parser.parse_args()
    questions=load_questions(args.file)
    target=args.csv or args.file.with_name(args.file.stem+'.paula-results.csv')
    if target.resolve()==args.file.resolve():parser.error('CSV output must differ from the input file')
    command=['docker','exec','-i','-e','HF_HUB_DISABLE_PROGRESS_BARS=1','-e','TQDM_DISABLE=1',args.container,
        'python','-B','manage.py','shell','-c',"import runpy; runpy.run_path('/app/scripts/question_worker.py',run_name='__main__')"]
    payload=dict(questions=questions,providers=not args.no_providers,preview_chars=240)
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8')
    process.stdin.write(json.dumps(payload,ensure_ascii=False));process.stdin.close()
    fields=['index','query','normalized','intent','method','reason_code','reply_preview','top_source','latency_ms','trace']
    count=0
    with target.open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for line in process.stdout:
            if line.startswith('PAULA_META\t'):print('Readiness: '+line.split('\t',1)[1].strip())
            if not line.startswith('PAULA_RESULT\t'):continue
            row=json.loads(line.split('\t',1)[1]);count+=1
            print(f"{row['index']}. {row['query']}\n   normalized={row['normalized']}\n   intent={row['intent']} reason={row['reason_code']} latency={row['latency_ms']:.2f} ms\n   source={row['top_source'].get('title','none')}\n   {row['reply_preview']}\n",flush=True)
            row['top_source']=json.dumps(row['top_source'],ensure_ascii=False)
            row['trace']=json.dumps(row['trace'],ensure_ascii=False)
            writer.writerow(row);stream.flush()
    code=process.wait()
    if code or count!=len(questions):raise SystemExit(f'Runner incomplete: {count}/{len(questions)} results. Check Docker backend readiness. Partial CSV: {target}')
    print(f'{count} results written to {target}')


if __name__=='__main__':main()
