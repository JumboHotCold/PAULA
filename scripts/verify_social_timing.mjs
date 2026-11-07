// Correlate only benchmark request IDs with payload-free runtime timings.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFile, writeFile } from 'node:fs/promises';
const before = JSON.parse(await readFile('PAULA_SOCIAL_TOLERANCE_BEFORE_BENCHMARK.json', 'utf8'));
const after = JSON.parse(await readFile('PAULA_SOCIAL_TOLERANCE_AFTER_BENCHMARK.json', 'utf8'));
const process = spawnSync('docker', ['logs', '--since', '2h', 'paulibot_web'], { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024 });
assert.equal(process.status, 0, 'Cannot inspect timing records');
const traces = new Map();
for (const line of (process.stdout + '\n' + process.stderr).split('\n')) {
  try { const record = JSON.parse(line); if (record.event === 'request_timing') traces.set(record.request_id, record); } catch { /* Other startup logs are not exported. */ }
}
function summarize(report, requireAll = false) {
  const rows = report.rows.filter(row => row.expected !== 'knowledge');
  const records = rows.map(row => ({ row, trace: traces.get(row.request_id) })).filter(item => item.trace);
  if (requireAll) assert.equal(records.length, rows.length, 'Missing current benchmark timing records');
  const withStage = names => records.filter(({ trace }) => names.some(name => trace.stages?.[name]?.calls > 0)).length;
  const gratitude = records.filter(({ row }) => row.expected === 'thanks');
  return { samples: rows.length, correlated: records.length,
    social_embedding_requests: withStage(['social_query_embedding']),
    retrieval_requests: withStage(['retrieval', 'hybrid_retrieval', 'query_embedding']),
    provider_requests: records.filter(({ trace }) => trace.providers?.length > 0).length,
    gratitude_sql_queries: gratitude.reduce((sum, { trace }) => sum + trace.sql_count, 0),
    social_normalization_stage_requests: withStage(['social_normalization']) };
}
const result = { before: summarize(before), after: summarize(after, true),
  note: 'Only public benchmark request IDs were correlated. No message text, SQL, identities, cookies or provider credentials are exported.' };
assert.equal(result.after.social_embedding_requests, 0);
assert.equal(result.after.retrieval_requests, 0);
assert.equal(result.after.provider_requests, 0);
assert.equal(result.after.gratitude_sql_queries, 0);
await writeFile('PAULA_SOCIAL_TOLERANCE_TIMING.json', JSON.stringify(result, null, 2));
console.log(JSON.stringify(result));
