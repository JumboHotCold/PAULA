import test from 'node:test';
import assert from 'node:assert/strict';
import { createSendGuard } from './sendGuard.js';

test('two same-frame activations submit once until the request settles', async () => {
  const guard = createSendGuard();
  let finish, submitted = 0;
  const network = new Promise(resolve => { finish = resolve; });
  const send = async () => {
    const ticket = guard.acquire(1);
    if (!ticket) return;
    submitted++;
    try { await network; } finally { guard.release(ticket); }
  };
  const first = send();
  await send();
  assert.equal(submitted, 1);
  finish(); await first;
  await send();
  assert.equal(submitted, 2);
});

test('an old account/thread completion cannot release a newer request', () => {
  const guard = createSendGuard();
  const old = guard.acquire(1);
  const current = guard.acquire(2);
  assert.ok(current);
  guard.release(old);
  assert.equal(guard.acquire(2), null);
  guard.release(current);
  assert.ok(guard.acquire(2));
});

test('failure releases the request without an automatic retry', async () => {
  const guard = createSendGuard();
  let attempts = 0;
  const ticket = guard.acquire(1);
  try { attempts++; await Promise.reject(new Error('Synthetic failure')); }
  catch { /* Normal caller displays the failure. */ }
  finally { guard.release(ticket); }
  assert.equal(attempts, 1);
  assert.ok(guard.acquire(1));
});
