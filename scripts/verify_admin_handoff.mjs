// Actual React login flows against isolated API fixtures; no real credentials.
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
import { connect } from './mobile_browser.mjs';
const ui = await connect(), checks = [];
let complete = false;
const admin = { authenticated: true, id: 'admin-handoff-fixture', is_superuser: true };
const guest = { type: 'GUEST', id: null, name: 'Guest' };
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function check(name, expression) {
  assert.ok(await ui.evaluate(expression), name);
  checks.push({ name, passed: true }); console.log(name);
}
const button = label => `[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)})`;
async function fill(selector, value) {
  await ui.evaluate(`document.querySelector(${JSON.stringify(selector)}).focus()`);
  await ui.command('Input.insertText', { text: value });
}
async function openMap() {
  await ui.evaluate(`document.querySelector('[aria-label="Campus map"]').click()`);
  await ui.waitFor(`document.querySelector('.campus-nav-map-img')?.naturalWidth>0`);
}
try {
  await ui.emulate(1656, 850, false);
  await ui.command('Fetch.enable', { patterns: [{ urlPattern: '*localhost:5173/src/main.jsx*', requestStage: 'Request' }] });
  ui.on('Fetch.requestPaused', e => ui.command('Fetch.fulfillRequest', { requestId: e.requestId, responseCode: 200,
    responseHeaders: [{ name: 'Content-Type', value: 'application/javascript' }], body: Buffer.from('// isolated handoff tests').toString('base64') }).catch(() => {}));
  await ui.command('Page.navigate', { url: 'http://localhost:5173' });
  await ui.waitFor(`document.readyState==='complete'&&document.querySelector('#root')`);
  await ui.command('Fetch.disable');
  await ui.evaluate(`(async()=>{
    const runtime=await import('/@react-refresh');runtime.default.injectIntoGlobalHook(window);
    window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
    await import('/@vite/client');await import('/src/index.css?import');await import('/src/App.css?import');await import('/src/responsive.css?import');
    const react=await import('/node_modules/.vite/deps/react.js');window.__React=react.default||react;
    const dom=await import('/node_modules/.vite/deps/react-dom_client.js');window.__root=(dom.default||dom).createRoot(document.getElementById('root'));
    window.__App=(await import('/src/App.jsx')).default;
    window.__mount=(path,stored,session)=>{
      localStorage.clear();sessionStorage.clear();if(stored)localStorage.setItem('paulibot_user',JSON.stringify(stored));
      history.replaceState(null,'',path);window.__session=session;window.__logoutCalls=0;window.__loginCalls=0;window.__chat=null;
      window.fetch=async(url,options={})=>{
        let data=[];const path=String(url);
        if(path==='/api/session')data=window.__session;
        else if(path==='/api/login'){
          window.__loginCalls++;window.__session=${JSON.stringify(admin)};
          data={account_id:window.__session.id,is_superuser:true,name:'Admin UI fixture'};
        }
        else if(path==='/api/logout'){window.__logoutCalls++;window.__session={authenticated:false};data={};}
        else if(path==='/api/chat'){
          window.__chat={payload:JSON.parse(options.body),credentials:options.credentials};
          data={response:'Guest fixture reply',saved:false,sources:[],suggested_questions:[]};
        }
        else if(path.includes('/metrics/'))data={};
        else if(path.includes('/student-needs/'))data={results:[],count:0,num_pages:1,current_page:1};
        return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
      };
      window.__root.render(window.__React.createElement(window.__App,{key:crypto.randomUUID()}));
    };
  })()`);
  await ui.evaluate(`window.__mount('/admin',${JSON.stringify(guest)},{authenticated:false})`);
  await ui.waitFor(`document.querySelector('input[type="password"]')`);
  await check('saved guest does not bypass React admin login', `document.body.textContent.includes('Admin Access')&&!document.querySelector('.guest-warning-badge')&&window.__logoutCalls===0`);
  await fill('input[type="text"]', 'admin-ui-fixture'); await fill('input[type="password"]', 'synthetic-password');
  await ui.evaluate(`document.querySelector('form').requestSubmit()`);
  await ui.waitFor(`document.querySelector('.admin-title')`);
  await check('React admin form recognizes backend superuser', `window.__loginCalls===1&&JSON.parse(localStorage.getItem('paulibot_user')).type==='ADMIN'`);
  await ui.evaluate(`(${button('← Back to Chat')}).click()`);
  await ui.waitFor(`document.querySelector('.chat-layout')`); await openMap();
  await ui.waitFor(button('Map tools'));
  await check('React admin login → Back to Chat → Campus map retains tools', `!document.querySelector('.guest-warning-badge')&&window.__logoutCalls===0&&JSON.parse(localStorage.getItem('paulibot_user')).is_superuser===true`);
  await ui.screenshot('PAULA_ADMIN_HANDOFF_MAP.png');
  await ui.evaluate(`window.__mount('/',JSON.parse(localStorage.getItem('paulibot_user')),${JSON.stringify(admin)})`);
  await ui.waitFor(`document.querySelector('.chat-layout')`); await openMap(); await ui.waitFor(button('Map tools'));
  await check('admin identity and tools survive root page refresh', `window.__logoutCalls===0&&!document.querySelector('.guest-warning-badge')`);

  await ui.evaluate(`window.__mount('/',null,{authenticated:false})`);
  await ui.waitFor(`document.querySelector('#student_id')`);
  await fill('#student_id', 'admin-ui-fixture'); await fill('#password', 'synthetic-password');
  await ui.evaluate(`document.querySelector('form').requestSubmit()`); await ui.waitFor(`document.querySelector('.admin-title')`);
  await check('main React login also preserves superuser role', `JSON.parse(localStorage.getItem('paulibot_user')).type==='ADMIN'&&window.__loginCalls===1`);

  await ui.evaluate(`window.__mount('/',${JSON.stringify(guest)},${JSON.stringify(admin)})`);
  await ui.waitFor(`document.querySelector('.guest-warning-badge')`); await openMap();
  await check('guest plus existing admin cookie stays guest until explicit switch', `!!(${button('Switch to administrator')})&&!(${button('Map tools')})&&window.__logoutCalls===0`);
  await fill('.chat-input', 'Guest-only test message'); await ui.evaluate(`document.querySelector('.input-area form,form.input-container,form').requestSubmit()`);
  await ui.waitFor(`!!window.__chat`);
  await check('guest requests remain unsaved and omit authenticated cookies', `window.__chat.payload.mode==='guest'&&window.__chat.credentials==='omit'`);
  await ui.evaluate(`(${button('Switch to administrator')}).click()`); await ui.waitFor(`document.querySelector('.admin-title')`);
  await ui.evaluate(`(${button('← Back to Chat')}).click()`); await ui.waitFor(`document.querySelector('.chat-layout')`);
  await check('explicit admin switch clears guest messages and starts fresh context', `!document.body.textContent.includes('Guest-only test message')&&!document.body.textContent.includes('Guest fixture reply')&&!document.querySelector('.guest-warning-badge')`);
  await openMap(); await ui.waitFor(button('Map tools'));
  await check('tools available after explicit verified admin switch', `!!(${button('Map tools')})`);

  await ui.evaluate(`window.__mount('/',null,${JSON.stringify(admin)})`); await ui.waitFor(`document.querySelector('.btn-guest')`);
  await ui.evaluate(`document.querySelector('.btn-guest').click()`); await ui.waitFor(`document.querySelector('.guest-warning-badge')`);
  await openMap();
  await check('explicit Continue as Guest still ends previous authentication', `window.__logoutCalls===1&&!window.__session.authenticated&&!(${button('Map tools')})`);
  await ui.evaluate(`window.__mount('/admin/',${JSON.stringify(guest)},${JSON.stringify(admin)})`); await ui.waitFor(`document.querySelector('.admin-title')`);
  await check('explicit admin route restores existing verified session despite stale guest profile', `window.__logoutCalls===0&&JSON.parse(localStorage.getItem('paulibot_user')).type==='ADMIN'`);
  complete = true;
} finally {
  await writeFile('PAULA_ADMIN_HANDOFF_BROWSER.json', JSON.stringify({ complete, passed: checks.length, checks,
    notes: 'Actual App/forms/map against isolated API session fixtures. No real passwords, new accounts, historical writes, or production login claims.' }, null, 2));
  ui.close();
}
