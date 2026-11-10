"""Correlate only this audit's synthetic request IDs with privacy-safe Docker timings."""
from collections import Counter
import json
import math
from pathlib import Path
import subprocess


def percentile(values, fraction):
    return sorted(values)[math.ceil(len(values) * fraction) - 1] if values else None


report = json.loads(Path('artifacts/stage1/audit.json').read_text(encoding='utf-8'))
wanted = {row['request_id'] for row in report['rows']}
logs = subprocess.run(['docker', 'logs', '--since', '2h', 'paulibot_web'], capture_output=True, check=True)
traces = {}
for line in (logs.stdout + logs.stderr).decode('utf-8', errors='replace').splitlines():
    try:
        record = json.loads(line)
    except ValueError:
        continue
    if record.get('event') == 'request_timing' and record.get('request_id') in wanted:
        traces[record['request_id']] = record
queries = {}
for query in dict.fromkeys(row['query'] for row in report['rows']):
    rows = [row for row in report['rows'] if row['query'] == query]
    matched = [traces[row['request_id']] for row in rows if row['request_id'] in traces]
    queries[query] = dict(samples=len(rows), passed=sum(row['passed'] for row in rows),
                         p50_ms=percentile([row['ms'] for row in rows], .5), p95_ms=percentile([row['ms'] for row in rows], .95),
                         sql_counts=[row['sql_count'] for row in matched],
                         provider_calls=sum(len(row['providers']) for row in matched),
                         query_embeddings=sum('query_embedding' in row['stages'] for row in matched))
stages = {}
for name in sorted({name for row in traces.values() for name in row['stages']}):
    values = [row['stages'][name]['inclusive_ms'] for row in traces.values() if name in row['stages']]
    stages[name] = dict(samples=len(values), p50_inclusive_ms=percentile(values, .5), p95_inclusive_ms=percentile(values, .95))
result = dict(captured=len(traces), expected=len(wanted), per_query=queries, stages=stages,
              provider_outcomes=dict(Counter(event['provider'] + ':' + event['outcome'] for row in traces.values() for event in row['providers'])),
              limitation='Stage 1 baseline only; three sequential warm samples per query, not an improvement, load test or independent accuracy estimate.')
Path('artifacts/stage1/metrics.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
