// Read-only real admin login checks and isolated component permission fixtures.
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
import { connect } from './mobile_browser.mjs';

const ui = await connect(), checks = [];
let complete = false;
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function check(name, expression) {
  assert.ok(await ui.evaluate(expression), name);
  checks.push({ name, passed: true }); console.log(name);
}
try {
  await ui.emulate(1280, 900, false);
  await ui.command('Page.navigate', { url: 'http://localhost:8080/admin/login/' });
  await ui.waitFor(`document.querySelector('input[name="username"]')`);
  await ui.waitFor(`[...document.querySelectorAll('link[rel="stylesheet"]')].every(link=>!!link.sheet)`);
  await ui.evaluate('document.fonts.ready');
  await check('real Unfold stylesheets load', `document.styleSheets.length>=4&&[...document.querySelectorAll('link[rel="stylesheet"]')].every(link=>!!link.sheet)`);
  await check('real logo is visible with absolute static URL', `[...document.images].some(img=>img.src.includes('/static/chatbot/images/SPUS-Logo1.')&&img.naturalWidth>0)`);
  await check('icon font loads instead of showing words', `document.fonts.check('16px "Material Symbols Outlined"')`);
  await check('PAULA branding and return link', `document.title.includes('PAULA Administration')&&[...document.querySelectorAll('a')].some(a=>a.href==='http://localhost:5173/')`);
  await check('Unfold JavaScript initializes', `!!window.Alpine`);
  await ui.screenshot('PAULA_ADMIN_LOGIN_DESKTOP.png');
  await ui.emulate(375, 812);
  await check('admin login fits mobile', `document.documentElement.scrollWidth<=375&&document.querySelector('input[name="username"]').getBoundingClientRect().right<=375`);
  await ui.evaluate(`document.documentElement.classList.add('dark')`);
  await pause(100);
  await check('Unfold dark styling is applied', `getComputedStyle(document.body).backgroundColor!=='rgb(255, 255, 255)'`);
  await ui.screenshot('PAULA_ADMIN_LOGIN_MOBILE.png');

  // Load a normal Vite HTML document, replacing only its application entry.
  await ui.command('Fetch.enable', { patterns: [{ urlPattern: '*localhost:5173/src/main.jsx*', requestStage: 'Request' }] });
  ui.on('Fetch.requestPaused', event => ui.command('Fetch.fulfillRequest', {
    requestId: event.requestId, responseCode: 200,
    responseHeaders: [{ name: 'Content-Type', value: 'application/javascript' }],
    body: Buffer.from('// isolated role fixtures').toString('base64'),
  }).catch(() => {}));
  await ui.command('Page.navigate', { url: 'http://localhost:5173' });
  await ui.waitFor(`document.readyState==='complete'&&document.querySelector('#root')`);
  await ui.command('Fetch.disable');
  await ui.evaluate(`(async()=>{
    const runtime=await import('/@react-refresh');runtime.default.injectIntoGlobalHook(window);
    window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
    await import('/@vite/client');await import('/src/index.css?import');await import('/src/App.css?import');await import('/src/responsive.css?import');
    const reactModule=await import('/node_modules/.vite/deps/react.js');window.__React=reactModule.default||reactModule;
    const dom=await import('/node_modules/.vite/deps/react-dom_client.js');window.__root=(dom.default||dom).createRoot(document.getElementById('root'));
    window.__Map=(await import('/src/components/MapModule.jsx')).default;
    window.__realFetch=window.fetch.bind(window);
    window.__renderMap=(user,session)=>{
      window.__calls=0;window.__pending=null;
      window.fetch=(url,options)=>{
        if(String(url)==='/api/session'){
          window.__calls++;
          if(session==='pending')return new Promise(resolve=>window.__pending=resolve);
          if(session==='failed')return Promise.reject(new Error('Synthetic unavailable session'));
          return Promise.resolve(new Response(JSON.stringify(session),{headers:{'Content-Type':'application/json'}}));
        }
        return window.__realFetch(url,options);
      };
      window.__root.render(window.__React.createElement(window.__Map,{user}));
    };
  })()`);
  const admin = { type: 'ADMIN', id: 'role-fixture', is_superuser: true };
  const verified = { authenticated: true, id: 'role-fixture', is_superuser: true };
  const mapTools = `[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Map tools')`;
  await ui.evaluate(`window.__renderMap({type:'GUEST'},${JSON.stringify(verified)})`);
  await ui.waitFor(`document.querySelector('.campus-nav-map-img')?.naturalWidth>0`);
  await check('guest has navigation without Map Tools or session lookup', `!(${mapTools})&&window.__calls===0&&!!document.querySelector('.campus-nav-origin-panel')`);
  await ui.evaluate(`window.__renderMap({type:'STUDENT',id:'student',is_superuser:true},${JSON.stringify(verified)})`);
  await pause(100);
  await check('student cannot enable tools using a local superuser flag', `!(${mapTools})&&window.__calls===0`);
  await ui.evaluate(`window.__renderMap(${JSON.stringify(admin)},'pending')`);
  await ui.waitFor(`!!window.__pending`);
  await check('admin tools stay hidden before backend verification', `!(${mapTools})`);
  await ui.evaluate(`window.__pending(new Response(${JSON.stringify(JSON.stringify(verified))},{headers:{'Content-Type':'application/json'}}))`);
  await ui.waitFor(mapTools);
  await check('matching backend administrator can open tools', `window.__calls===1&&!!(${mapTools})`);
  await ui.evaluate(`(${mapTools}).click()`);
  await ui.waitFor(`document.querySelector('.campus-nav-mapper-panel')`);
  await check('admin mapper retains export and explains persistence', `document.querySelector('.campus-nav-mapper-copy-btn')&&document.querySelector('.campus-nav-mapper-panel').textContent.includes('not saved automatically')`);
  await ui.screenshot('PAULA_ADMIN_MAP_TOOLS.png');
  await ui.evaluate(`window.__renderMap({type:'GUEST'},${JSON.stringify(verified)})`);
  await ui.waitFor(`!document.querySelector('.campus-nav-mapper-panel')`);
  await check('switching admin to guest removes tools and restores navigation', `!(${mapTools})&&!!document.querySelector('.campus-nav-origin-panel')`);
  await ui.evaluate(`window.__renderMap(${JSON.stringify(admin)},{authenticated:true,id:'another-account',is_superuser:true})`);
  await pause(150);
  await check('mismatched backend identity fails closed', `!(${mapTools})`);
  await ui.evaluate(`window.__renderMap({type:'GUEST'},null)`); await pause(50);
  await ui.evaluate(`window.__renderMap(${JSON.stringify(admin)},'failed')`); await pause(150);
  await check('session error fails closed without hiding public navigation', `!(${mapTools})&&!!document.querySelector('.campus-nav-origin-panel')`);
  await ui.evaluate(`window.__renderMap({type:'GUEST'},null)`); await pause(50);
  await ui.evaluate(`window.__renderMap(${JSON.stringify(admin)},'pending')`);
  await ui.waitFor(`!!window.__pending`);
  await ui.evaluate(`window.__oldPending=window.__pending;window.__renderMap({type:'GUEST'},null)`); await pause(50);
  await ui.evaluate(`window.__oldPending(new Response(${JSON.stringify(JSON.stringify(verified))},{headers:{'Content-Type':'application/json'}}))`); await pause(100);
  await check('late admin verification cannot re-enable guest tools', `!(${mapTools})&&!document.querySelector('.campus-nav-mapper-panel')`);

  // Remount the actual App to exercise refresh/role restoration with no DB login.
  await ui.evaluate(`(async()=>{
    window.__App=(await import('/src/App.jsx')).default;
    window.__restoreApp=(path,stored,session)=>{
      window.__root.render(null);
      localStorage.clear();sessionStorage.clear();
      localStorage.setItem('paulibot_user',JSON.stringify(stored));
      history.replaceState(null,'',path);
      window.fetch=async url=>{
        const path=String(url);let data=[];
        if(path==='/api/session')data=session;
        else if(path.includes('/metrics/'))data={};
        else if(path.includes('/student-needs/'))data={results:[],count:0,num_pages:1,current_page:1};
        return new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
      };
      setTimeout(()=>window.__root.render(window.__React.createElement(window.__App,{key:crypto.randomUUID()})),0);
    };
  })()`);
  for (const path of ['/admin','/admin/']) {
    await ui.evaluate(`window.__restoreApp(${JSON.stringify(path)},${JSON.stringify(admin)},${JSON.stringify(verified)})`);
    await ui.waitFor(`document.querySelector('.admin-title')?.textContent==='Institutional Analytics'`);
    await check(`analytics restores at ${path}`, `document.querySelector('.admin-action-btn').href==='http://localhost:8080/admin/'`);
  }
  await ui.evaluate(`window.__restoreApp('/admin/',${JSON.stringify(admin)},{authenticated:true,id:'role-fixture',is_superuser:false})`);
  await ui.waitFor(`document.querySelector('.chat-layout')`);
  await check('stale local admin role is removed using backend session', `!document.querySelector('.admin-title')&&JSON.parse(localStorage.getItem('paulibot_user')).type==='STUDENT'&&JSON.parse(localStorage.getItem('paulibot_user')).is_superuser===false`);
  await ui.evaluate(`window.__restoreApp('/',{type:'GUEST',is_superuser:true},${JSON.stringify(verified)})`);
  await ui.waitFor(`document.querySelector('.chat-layout')`);
  await check('guest cannot restore analytics from a stale local admin flag', `!document.querySelector('.admin-title')&&JSON.parse(localStorage.getItem('paulibot_user')).is_superuser===false`);
  complete = true;
} finally {
  await writeFile('PAULA_ADMIN_MAP_UI_VERIFICATION.json', JSON.stringify({ complete, passed: checks.length, checks,
    notes: 'Actual Docker admin login assets and responsive layout; isolated synthetic identity/session fixtures for MapModule. No real login, account creation, map writes, or historical-data changes.' }, null, 2));
  ui.close();
}
