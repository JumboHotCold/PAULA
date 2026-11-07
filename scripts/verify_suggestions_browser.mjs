// Native Chrome DevTools smoke test; no browser packages or real student account.
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';

const port = process.argv[2] || '9339';
const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const page = pages.find(item => item.type === 'page');
assert.ok(page, 'A dedicated browser page is required');
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let sequence = 0;
const pending = new Map();
socket.onmessage = event => {
  const message = JSON.parse(event.data);
  if (!message.id) return;
  const entry = pending.get(message.id);
  if (!entry) return;
  pending.delete(message.id);
  message.error ? entry.reject(new Error(JSON.stringify(message.error))) : entry.resolve(message.result);
};
function command(method, params = {}) {
  const id = ++sequence;
  return new Promise((resolve, reject) => { pending.set(id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params })); });
}
async function evaluate(expression) {
  const response = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  assert.ok(!response.exceptionDetails, JSON.stringify(response.exceptionDetails));
  return response.result?.value;
}
async function waitFor(expression) {
  const deadline = Date.now() + 45000;
  while (Date.now() < deadline) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 150));
  }
  throw new Error(`Browser wait timed out: ${expression}`);
}

try {
  await command('Page.enable');
  await command('Runtime.enable');
  await command('Emulation.setDeviceMetricsOverride', { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
  await command('Page.navigate', { url: 'http://localhost:5173' });
  await waitFor(`[...document.querySelectorAll('button')].some(button => button.textContent.trim() === 'Continue as Guest')`);
  await evaluate(`[...document.querySelectorAll('button')].find(button => button.textContent.trim() === 'Continue as Guest').click()`);
  await waitFor(`Boolean(document.querySelector('.chat-input:not(:disabled)'))`);
  await evaluate(`document.querySelector('.chat-input').value = 'Tell me about SPUS?'; document.querySelector('.input-wrapper').requestSubmit()`);
  await waitFor(`document.querySelectorAll('.message-wrapper.bot').length === 1 && Boolean(document.querySelector('.chat-input:not(:disabled)'))`);
  const first = await evaluate(`[...document.querySelectorAll('.follow-up-chip')].map(button => button.textContent.trim())`);
  assert.ok(first.length > 0 && first.length <= 3);
  const chosen = first.find(label => /program|course/i.test(label)) || first[0];
  await evaluate(`[...document.querySelectorAll('.follow-up-chip')].find(button => button.textContent.trim() === ${JSON.stringify(chosen)}).click()`);
  await waitFor(`document.querySelectorAll('.message-wrapper.bot').length === 2 && Boolean(document.querySelector('.chat-input:not(:disabled)'))`);
  const after = await evaluate(`({
    groups: document.querySelectorAll('.follow-up-chips').length,
    firstReplyGroups: document.querySelectorAll('.message-wrapper.bot')[0].querySelectorAll('.follow-up-chips').length,
    latestReplyGroups: document.querySelectorAll('.message-wrapper.bot')[1].querySelectorAll('.follow-up-chips').length,
    labels: [...document.querySelectorAll('.follow-up-chip')].map(button => button.textContent.trim()),
    lastUser: [...document.querySelectorAll('.message-wrapper.user .message-content')].at(-1).textContent.trim()
  })`);
  assert.equal(after.firstReplyGroups, 0);
  assert.equal(after.groups, 1);
  assert.equal(after.latestReplyGroups, 1);
  assert.equal(after.lastUser, chosen);
  assert.ok(!after.labels.includes(chosen));
  // Wait out the existing staggered chip/message animations before capture.
  await new Promise(resolve => setTimeout(resolve, 800));
  await evaluate(`document.querySelector('.follow-up-chips').scrollIntoView({ block: 'nearest' })`);
  const screenshot = await command('Page.captureScreenshot', { format: 'png' });
  await writeFile('PAULA_SUGGESTIONS_BROWSER.png', Buffer.from(screenshot.data, 'base64'));
  await writeFile('PAULA_SUGGESTIONS_BROWSER.json', JSON.stringify({ passed: true, mode: 'guest', first, clicked: chosen, after }, null, 2));
  console.log(JSON.stringify({ passed: true, first, clicked: chosen, after }));
} finally {
  await command('Browser.close').catch(() => {});
  socket.close();
}
