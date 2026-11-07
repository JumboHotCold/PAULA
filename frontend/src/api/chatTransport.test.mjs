import test from 'node:test';
import assert from 'node:assert/strict';
import { postChat, chatErrorMessage } from './chatTransport.js';

test('deadline aborts the fetch and never automatically retries', async () => {
  let calls = 0;
  globalThis.fetch = async (_, {signal}) => {
    calls++;
    return new Promise((_, reject) => signal.addEventListener('abort', () => reject(new Error('aborted'))));
  };
  await assert.rejects(postChat({}, {timeoutMs: 10}), error => error.code === 'timeout');
  assert.equal(calls, 1);
  assert.match(chatErrorMessage({code: 'timeout'}), /check your conversation/);
});

test('invalid responses and unavailable services have distinct safe messages', async () => {
  globalThis.fetch = async () => ({ ok: true, json: async () => ({saved: true}) });
  await assert.rejects(postChat({}), error => error.code === 'invalid_response');
  globalThis.fetch = async () => ({ ok: false, status: 503, json: async () => ({error: 'PRIVATE SQL', error_code: 'storage_unavailable', request_id: 'fixture'}) });
  await assert.rejects(postChat({}), error => {
    assert.equal(error.requestId, 'fixture');
    assert.match(chatErrorMessage(error), /temporarily unavailable/);
    assert.doesNotMatch(error.message, /PRIVATE/);
    return error.status === 503;
  });
  assert.match(chatErrorMessage(new TypeError('fetch failed')), /connection/);
});

test('deadline includes reading the body', async () => {
  globalThis.fetch = async (_, {signal}) => ({ ok: true,
    json: () => new Promise((_, reject) => signal.addEventListener('abort', () => reject(new Error('aborted')))) });
  await assert.rejects(postChat({}, {timeoutMs: 10}), error => error.code === 'timeout');
});
