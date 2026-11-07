import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
const deadline = Date.now() + 240000;
let ready = false;
while (Date.now() < deadline) {
  try {
    const response = await fetch('http://localhost:5173/api/health/ready', { signal: AbortSignal.timeout(2000) });
    const state = await response.json();
    if (response.ok && state.ready && state.ready_workers === state.expected_workers) { ready = true; break; }
  } catch { /* Worker startup is measured separately from request latency. */ }
  await new Promise(resolve => setTimeout(resolve, 1000));
}
assert.ok(ready, 'All workers must be ready before checking the user request');
const query = 'TELL ME ABOUT SPUS AND WHY SHOULD I ENROL';
const start = performance.now();
const response = await fetch('http://localhost:5173/api/chat', {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: query, mode: 'guest', context_id: crypto.randomUUID() }),
});
const data = await response.json();
assert.ok(response.ok);
assert.ok(data.response.includes('Sisters of St. Paul of Chartres'));
assert.ok(data.response.includes('Faith-Based Education'));
assert.equal(data.sources.length, 2);
assert.deepEqual(data.sources.map(source => source.part), [1, 2]);
assert.equal(data.saved, false);
assert.ok(!data.response.includes("don't have enough verified"));
const result = { query, passed: true, status: response.status, ms: Math.round((performance.now() - start) * 100) / 100,
  response: data.response, sources: data.sources, saved: data.saved };
await writeFile('PAULA_COMPOUND_REASON_FRONTEND.json', JSON.stringify(result, null, 2));
console.log(JSON.stringify({ passed: true, status: result.status, ms: result.ms, sources: data.sources.length, saved: false }));
