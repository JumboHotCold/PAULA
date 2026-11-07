"""Read synthetic request IDs from benchmark artifacts; consume Docker JSON logs on stdin."""
from collections import Counter
import json
import math
from pathlib import Path
import sys
import subprocess


def percentile(values, fraction):
    return sorted(values)[math.ceil(len(values) * fraction) - 1] if values else None


def main():
    reports = {phase: json.loads(Path(f'PAULA_MVP_HTTP_{phase.upper()}.json').read_text(encoding='utf-8'))
               for phase in ('before', 'after')}
    wanted = {row['request_id'] for report in reports.values() for row in report['rows'] if row.get('request_id')}
    traces = {}
    if '--docker' in sys.argv:
        logs = subprocess.run(['docker', 'logs', '--since', '2h', 'paulibot_web'], check=True, capture_output=True)
        lines = (logs.stdout + logs.stderr).decode('utf-8', errors='replace').splitlines()
        stats = subprocess.run(['docker', 'stats', 'paulibot_web', '--no-stream', '--format', '{{json .}}'],
                               check=True, capture_output=True)
        Path('PAULA_MVP_RESOURCES.json').write_text(json.dumps(json.loads(stats.stdout), indent=2), encoding='utf-8')
    else:
        lines = sys.stdin
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get('event') == 'request_timing' and record.get('request_id') in wanted:
            traces[record['request_id']] = {key: record.get(key) for key in
                ('request_id', 'worker', 'status', 'total_ms', 'sql_count', 'sql_ms', 'stages', 'providers')}
    result = {}
    for phase, report in reports.items():
        records = [traces[row['request_id']] for row in report['rows'] if row.get('request_id') in traces]
        stages = {}
        for name in sorted({name for row in records for name in row['stages']}):
            observations = [row['stages'][name]['inclusive_ms'] for row in records if name in row['stages']]
            stages[name] = dict(samples=len(observations), p50_inclusive_ms=percentile(observations, .5),
                                p95_inclusive_ms=percentile(observations, .95))
        hybrid = [row for row in records if 'hybrid_retrieval' in row['stages']]
        providers = Counter(event['provider'] + ':' + event['outcome'] for row in records for event in row['providers'])
        result[phase] = dict(captured=len(records), expected=report['samples'],
                            server_p50_ms=percentile([row['total_ms'] for row in records], .5),
                            server_p95_ms=percentile([row['total_ms'] for row in records], .95),
                            hybrid_sql_count_p50=percentile([row['sql_count'] for row in hybrid], .5),
                            hybrid_sql_ms_p95=percentile([row['sql_ms'] for row in hybrid], .95),
                            provider_outcomes=dict(providers), stages=stages)
    Path('PAULA_MVP_STAGE_TIMINGS.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
