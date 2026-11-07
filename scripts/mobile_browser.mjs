// Native Chrome DevTools helpers for a dedicated, synthetic mobile UI session.
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';

export async function connect() {
  let pages;
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    try { pages = await (await fetch('http://127.0.0.1:9340/json/list')).json(); break; }
    catch { await new Promise(resolve => setTimeout(resolve, 200)); }
  }
  const page = pages?.find(item => item.type === 'page');
  assert.ok(page, 'Dedicated Chrome page not ready');
  const socket = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let serial = 0;
  const pending = new Map();
  const events = new Map();
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (!message.id) { for (const handler of events.get(message.method) || []) handler(message.params); return; }
    const entry = pending.get(message.id);
    pending.delete(message.id);
    if (entry) message.error ? entry.reject(new Error(JSON.stringify(message.error))) : entry.resolve(message.result);
  };
  const command = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++serial;
    pending.set(id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async expression => {
    const response = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    assert.ok(!response.exceptionDetails, JSON.stringify(response.exceptionDetails));
    return response.result?.value;
  };
  const waitFor = async (expression, timeout = 30000) => {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      if (await evaluate(`Boolean(${expression})`)) return;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error(`UI wait timed out: ${expression}`);
  };
  const emulate = async (width, height, mobile = true) => {
    await command('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile });
    await command('Emulation.setTouchEmulationEnabled', { enabled: mobile, maxTouchPoints: 5 });
  };
  const screenshot = async path => {
    const result = await command('Page.captureScreenshot', { format: 'png' });
    await writeFile(path, Buffer.from(result.data, 'base64'));
  };
  await command('Page.enable'); await command('Runtime.enable');
  return { command, evaluate, waitFor, emulate, screenshot, on: (name, handler) => events.set(name, [...(events.get(name)||[]), handler]), close: () => socket.close() };
}

export const metrics = `(() => {
  const rect = selector => { const el = document.querySelector(selector); if (!el) return null;
    const r = el.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,right:r.right}; };
  return { width:innerWidth,height:innerHeight,documentWidth:document.documentElement.scrollWidth,
    header:rect('.chat-header'), composer:rect('.input-area'), module:rect('.module-panel'),
    close:rect('.module-close-btn'), map:rect('.campus-nav-map-area'), image:rect('.campus-nav-map-img'),
    picker:rect('.campus-nav-origin-panel'), mapHeader:rect('.campus-nav-header'),
    tinyButtons:[...document.querySelectorAll('button')].filter(el => {
      const r=el.getBoundingClientRect();return r.width>0&&r.height>0&&r.right>0&&r.left<innerWidth&&r.bottom>0&&r.top<innerHeight&&(r.width<40||r.height<40);
    }).map(el=>({label:el.getAttribute('aria-label')||el.textContent.trim().slice(0,70),width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height})) };
})()`;
