// Native Chrome smoke test. Dedicated temporary profile, no real account.
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';

let pages;
const browserDeadline = Date.now() + 20000;
while (Date.now() < browserDeadline) {
  try {
    pages = await (await fetch('http://127.0.0.1:9339/json/list')).json();
    break;
  } catch {
    await new Promise(resolve => setTimeout(resolve, 200));
  }
}
assert.ok(pages, 'Chrome DevTools did not become ready');
const page = pages.find(item => item.type === 'page');
assert.ok(page);
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let sequence = 0;
const pending = new Map();
socket.onmessage = event => {
  const message = JSON.parse(event.data);
  if (!message.id) return;
  const entry = pending.get(message.id);
  pending.delete(message.id);
  if (entry) message.error ? entry.reject(new Error(JSON.stringify(message.error))) : entry.resolve(message.result);
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
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 150));
  }
  throw new Error(`Browser wait timed out: ${expression}`);
}

try {
  await command('Page.enable');
  await command('Runtime.enable');
  await command('Page.navigate', { url: 'http://localhost:5173' });
  await waitFor(`[...document.querySelectorAll('button')].some(button => button.textContent.trim() === 'Continue as Guest')`);
  await evaluate(`[...document.querySelectorAll('button')].find(button => button.textContent.trim() === 'Continue as Guest').click()`);
  await waitFor(`Boolean(document.querySelector('.chat-input:not(:disabled)'))`);
  const checks = [];
  let turns = 0;
  async function ask(query, expected, social = false) {
    turns += 1;
    await evaluate(`document.querySelector('.chat-input').value = ${JSON.stringify(query)}; document.querySelector('.input-wrapper').requestSubmit()`);
    await waitFor(`document.querySelectorAll('.message-wrapper.bot').length === ${turns} && Boolean(document.querySelector('.chat-input:not(:disabled)'))`);
    const latest = await evaluate(`({ text: [...document.querySelectorAll('.message-wrapper.bot')].at(-1).innerText,
      chips: [...document.querySelectorAll('.message-wrapper.bot')].at(-1).querySelectorAll('.follow-up-chip').length,
      sourceButtons: [...document.querySelectorAll('.message-wrapper.bot')].at(-1).querySelectorAll('.sources-toggle').length })`);
    assert.ok(latest.text.includes(expected), latest.text);
    if (social) assert.equal(latest.chips, 0);
    checks.push({ query, passed: true, text: latest.text, chips: latest.chips });
    return latest;
  }
  if (process.argv.includes('--identity-faq')) {
    await ask('who you?', 'Paulinian Artificial User Support and Learning Assistant');
    const first = await evaluate(`[...document.querySelectorAll('.follow-up-chip')].map(button => button.textContent.trim())`);
    assert.deepEqual(first, ['What programs are offered at SPUS?', 'How do I enroll at SPUS?', 'Where is the Registrar office?']);
    turns += 1;
    await evaluate(`[...document.querySelectorAll('.follow-up-chip')].find(button => button.textContent.trim() === 'What programs are offered at SPUS?').click()`);
    await waitFor(`document.querySelectorAll('.message-wrapper.bot').length === ${turns} && Boolean(document.querySelector('.chat-input:not(:disabled)'))`);
    const program = await evaluate(`[...document.querySelectorAll('.message-wrapper.bot')].at(-1).innerText`);
    assert.ok(program.includes('Information Technology'));
    checks.push({ query: first[0], passed: true, clicked: true });
    await ask('tell me about yourself?', 'Paulinian Artificial User Support and Learning Assistant');
    const remaining = await evaluate(`[...document.querySelectorAll('.follow-up-chip')].map(button => button.textContent.trim())`);
    assert.deepEqual(remaining, first.slice(1));
    await ask('How are announcements and promotional materials broadcast across the SPUS campus?', 'Unified Multimedia Communication Network');
    const related = await evaluate(`[...document.querySelectorAll('.follow-up-chip')].map(button => button.textContent.trim())`);
    assert.ok(related.length > 0 && related.every(question => !first.includes(question)));
    turns += 1;
    await evaluate(`document.querySelector('.follow-up-chip').click()`);
    await waitFor(`document.querySelectorAll('.message-wrapper.bot').length === ${turns} && Boolean(document.querySelector('.chat-input:not(:disabled)'))`);
    const posting = await evaluate(`[...document.querySelectorAll('.message-wrapper.bot')].at(-1).innerText`);
    assert.ok(posting.includes('PBMO') && !posting.includes("don't have enough verified information"));
    checks.push({ query: related[0], passed: true, clicked: true });
    await writeFile('PAULA_IDENTITY_FAQ_BROWSER.json', JSON.stringify({ passed: true, mode: 'guest', first, remaining, related, checks }, null, 2));
    console.log(JSON.stringify({ passed: true, checks: checks.length, first, remaining, related }));
  } else {
  await ask('How do I enroll?', 'Are you enrolling');
  await ask('Thank you', "You're welcome", true);
  await ask('Transferee student', 'URO-PR-017');
  await ask('How are you?', 'ready to help', true);
  await ask('How about old students?', 'URO-PR-016');
  await ask('Okay', 'Got it', true);
  await writeFile('PAULA_DIALOGUE_BROWSER.json', JSON.stringify({ passed: true, mode: 'guest', checks }, null, 2));
  console.log(JSON.stringify({ passed: true, checks: checks.length }));
  }
} finally {
  await command('Browser.close').catch(() => {});
  socket.close();
}
