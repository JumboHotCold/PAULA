"""Compare identical Stage 1/2 cases using privacy-safe matched request traces only."""
import json
import math
from pathlib import Path
import subprocess


def percentile(values, fraction):
    return sorted(values)[math.ceil(len(values) * fraction) - 1] if values else None


before = json.loads(Path('artifacts/stage1/audit.json').read_text(encoding='utf-8'))
after = json.loads(Path('artifacts/stage2/live/audit.json').read_text(encoding='utf-8'))
old_metrics = json.loads(Path('artifacts/stage1/metrics.json').read_text(encoding='utf-8'))
ids = {row['request_id'] for row in after['rows']}
logs = subprocess.run(['docker', 'logs', '--since', '2h', 'paulibot_web'], check=True, capture_output=True)
traces, outcomes, startup = {}, [], []
for line in (logs.stdout + logs.stderr).decode('utf-8', errors='replace').splitlines():
    try:
        record = json.loads(line)
    except ValueError:
        continue
    if record.get('request_id') in ids:
        assert 'query_text' not in record, 'Normal-mode diagnostics exposed query text'
        if record.get('event') == 'request_timing': traces[record['request_id']] = record
        if record.get('event') == 'pipeline_outcome': outcomes.append({key:record.get(key) for key in ('request_id','stage','reason_code')})
    if record.get('event') == 'worker_startup':
        startup.append({key:record.get(key) for key in ('worker','build_commit','build_source_digest','ready')})
comparisons = {}
for query in dict.fromkeys(row['query'] for row in before['rows']):
    rows = [row for row in after['rows'] if row['query'] == query]
    matched = [traces[row['request_id']] for row in rows if row['request_id'] in traces]
    comparisons[query] = dict(before=old_metrics['per_query'][query], after=dict(
        samples=len(rows), passed=sum(row['passed'] for row in rows),
        p50_ms=percentile([row['ms'] for row in rows], .5), p95_ms=percentile([row['ms'] for row in rows], .95),
        sql_counts=[row['sql_count'] for row in matched], provider_calls=sum(len(row['providers']) for row in matched),
        query_embeddings=sum('query_embedding' in row['stages'] for row in matched)))
assert len(traces) == len(ids), 'Missing timing traces for live audit requests'
result = dict(original_before=before['summary'], original_after=dict(samples=len(before['rows']),
    passed=sum(row['passed'] for row in after['rows'] if row['query'] in comparisons)),
    expanded_after=after['summary'], timings_captured=len(traces), comparisons=comparisons,
    no_match_reason_codes=outcomes, normal_mode_query_text_logged=False, worker_startup_records=startup[-3:],
    limitations='Three sequential samples per query; correctness and path-use regression evidence, not general intent accuracy, load capacity or calibrated retrieval recall.')
Path('artifacts/stage2/comparison.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({key:value for key,value in result.items() if key not in ('comparisons','no_match_reason_codes','worker_startup_records')}))
