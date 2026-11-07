import test from 'node:test';
import assert from 'node:assert/strict';
import { sendMessage, logoutSession } from './chatApi.js';

test('guest transport omits cookies, authenticated transport carries a stable session, and logout uses POST', async () => {
  const requests = [];
  globalThis.document = { cookie: 'csrftoken=test-token' };
  globalThis.fetch = async (url, options = {}) => {
    requests.push({url, ...options});
    return { ok: true, json: async () => ({ response: 'Fixture response.', saved: false }) };
  };
  await sendMessage('hello', 99, [], null, 'guest', 'chat-key', null, ['What is SPUS?', null, 'x'.repeat(501)]);
  assert.equal(requests[0].credentials, 'omit');
  assert.equal(JSON.parse(requests[0].body).mode, 'guest');
  assert.deepEqual(JSON.parse(requests[0].body).asked_questions, ['What is SPUS?']);
  await sendMessage('hello', null, [], null, 'authenticated', 'chat-key');
  await sendMessage('follow up', null, [], null, 'authenticated', 'chat-key');
  assert.equal(requests[1].credentials, 'include');
  assert.equal(JSON.parse(requests[1].body).chat_session_id, JSON.parse(requests[2].body).chat_session_id);
  await logoutSession();
  assert.equal(requests.at(-1).url, '/api/logout');
  assert.equal(requests.at(-1).method, 'POST');
});
