"""Join public benchmark request IDs to payload-free Docker timing events."""
import json
from pathlib import Path
import subprocess


def main():
    before = json.loads(Path('PAULA_DIALOGUE_BEFORE.json').read_text(encoding='utf-8'))
    after = json.loads(Path('PAULA_DIALOGUE_AFTER.json').read_text(encoding='utf-8'))
    ids = {row['headers']['X-Request-ID']: row['category'] for row in after['results']}
    logs = subprocess.run(['docker', 'logs', '--since', '30m', 'paulibot_web'], capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
    traces = []
    for line in (logs.stdout + '\n' + logs.stderr).splitlines():
        offset = line.find('{')
        if offset < 0:
            continue
        try:
            record = json.loads(line[offset:])
        except ValueError:
            continue
        if record.get('request_id') in ids and record.get('event') == 'request_timing':
            traces.append({**record, 'category': ids[record['request_id']]})
    assert len(traces) == len(ids), 'Some benchmark traces could not be correlated'
    socials = [trace for trace in traces if trace['category'] == 'social']
    assert not any(trace['providers'] or trace['sql_count'] for trace in socials), 'Social routing touched an external provider or database'
    report = dict(before=before['groups'], after=after['groups'], social_provider_calls=0, social_sql_queries=0,
                  correlated_traces=len(traces), traces=traces,
                  limitations='36 sequential local HTTP requests per phase; n=3 per query; no concurrency capacity, universal accuracy or general RAG speedup claim')
    Path('PAULA_DIALOGUE_PERFORMANCE.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'traces'}))


if __name__ == '__main__':
    main()
