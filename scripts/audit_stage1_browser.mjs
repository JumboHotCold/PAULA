// Isolated guest browser audit. Requires the existing Vite/Docker services.
// Does not change application code or reuse a personal browser profile.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, mkdir, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { connect } from './mobile_browser.mjs';

let occupied = false;
try { await fetch('http://127.0.0.1:9340/json/version'); occupied = true; } catch { /* No existing debugger. */ }
assert.equal(occupied, false, 'Port 9340 is occupied; refusing to attach to an existing browser.');
const profile = await mkdtemp(join(tmpdir(), 'paula-stage1-browser-'));
const browser = spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', [
  '--headless=new', '--remote-debugging-port=9340', `--user-data-dir=${profile}`,
  '--no-first-run', '--no-default-browser-check', 'http://localhost:5173/',
], { windowsHide: true, stdio: 'ignore' });
const result = { singleSubmit: null, sameFrameStarterClicks: null, separateDoubleClick: null,
  limitation: 'Synthetic guest UI reproduction; the same-frame stress case does not prove what caused past user-visible duplicates.' };
let page;
try {
  page = await connect();
  await page.command('Network.enable');
  const requests = [];
  page.on('Network.requestWillBeSent', event => {
    if (event.request.method === 'POST' && new URL(event.request.url).pathname === '/api/chat')
      requests.push({ requestId: event.requestId, timestamp: event.timestamp });
  });
  await page.waitFor('document.querySelector(".btn-guest")');
  await page.evaluate('document.querySelector(".btn-guest").click()');
  await page.waitFor('document.querySelector(".chat-input")');
  await page.evaluate(`(() => {
    const form = document.querySelector('form.input-wrapper');
    form.elements.message.value = 'ty'; form.requestSubmit();
  })()`);
  await page.waitFor('document.querySelectorAll(".message-wrapper.user").length === 1 && document.querySelectorAll(".message-wrapper.bot").length === 1 && !document.querySelector(".typing-indicator")');
  result.singleSubmit = { requests: requests.length, ...(await page.evaluate(`({users: document.querySelectorAll('.message-wrapper.user').length, answers: document.querySelectorAll('.message-wrapper.bot').length})`)) };

  const reset = async () => {
    await page.command('Page.navigate', {url: 'http://localhost:5173/'});
    await new Promise(resolve => setTimeout(resolve, 350));
    await page.waitFor('document.querySelector(".chat-input") && document.querySelectorAll(".message-wrapper.user").length === 0');
    requests.length = 0;
  };
  await reset();
  const starter = await page.evaluate(`(() => {
    const buttons = [...document.querySelectorAll('button')];
    const button = buttons.find(el => /What programs are offered/i.test(el.textContent));
    if (!button) throw new Error('Program starter missing');
    window.__stage1Starter = button;
    button.click(); button.click(); return button.textContent.trim();
  })()`);
  await page.waitFor('document.querySelectorAll(".message-wrapper.bot").length >= 1 && !document.querySelector(".typing-indicator")');
  await new Promise(resolve => setTimeout(resolve, 800));
  result.sameFrameStarterClicks = { starter, requests: requests.length,
    ...(await page.evaluate(`({users: document.querySelectorAll('.message-wrapper.user').length, answers: document.querySelectorAll('.message-wrapper.bot').length})`)) };

  await reset();
  const rect = await page.evaluate(`(() => {
    const button = [...document.querySelectorAll('button')].find(el => /What programs are offered/i.test(el.textContent));
    const r = button.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2};
  })()`);
  for (let i = 1; i <= 2; i++) {
    await page.command('Input.dispatchMouseEvent', {type:'mousePressed', ...rect, button:'left', clickCount:i});
    await page.command('Input.dispatchMouseEvent', {type:'mouseReleased', ...rect, button:'left', clickCount:i});
  }
  await page.waitFor('document.querySelectorAll(".message-wrapper.bot").length >= 1 && !document.querySelector(".typing-indicator")');
  await new Promise(resolve => setTimeout(resolve, 500));
  result.separateDoubleClick = { requests: requests.length,
    ...(await page.evaluate(`({users: document.querySelectorAll('.message-wrapper.user').length, answers: document.querySelectorAll('.message-wrapper.bot').length})`)) };
  assert.equal(result.singleSubmit.requests, 1);
  assert.equal(result.singleSubmit.answers, 1);
  assert.equal(result.separateDoubleClick.requests, 1);
  assert.equal(result.sameFrameStarterClicks.requests, 1, 'Same-frame starter activation must not submit the same turn twice');
} finally {
  await mkdir('artifacts/stage1', {recursive:true});
  await writeFile('artifacts/stage1/browser.json', JSON.stringify(result, null, 2));
  if (page) {
    await Promise.race([page.command('Browser.close').catch(() => {}), new Promise(resolve => setTimeout(resolve, 2000))]);
    page.close();
  }
  browser.kill();
  console.log(JSON.stringify(result));
}
