// Isolated admin/guest fixtures; writes never reach the real application database.
import assert from 'node:assert/strict';
import { connect } from './mobile_browser.mjs';

const ui = await connect();
ui.on('Runtime.exceptionThrown', event => console.error(event.exceptionDetails.exception?.description || event.exceptionDetails.text));
ui.on('Runtime.consoleAPICalled', event => {
  if (event.type === 'error') console.error(...event.args.map(arg => arg.value || arg.description));
});
const button = text => `[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(text)})`;
const click = async text => { await ui.evaluate(`${button(text)}.click()`); };
try {
  await ui.emulate(1440, 1000, false);
  await ui.command('Fetch.enable', { patterns: [{ urlPattern: '*127.0.0.1:5173/src/main.jsx*', requestStage: 'Request' }] });
  ui.on('Fetch.requestPaused', event => ui.command('Fetch.fulfillRequest', {
    requestId: event.requestId, responseCode: 200,
    responseHeaders: [{ name: 'Content-Type', value: 'application/javascript' }],
    body: Buffer.from('// isolated map fixtures').toString('base64'),
  }));
  await ui.command('Page.navigate', { url: 'http://127.0.0.1:5173' });
  await ui.waitFor(`document.readyState==='complete'&&document.querySelector('#root')`);
  await ui.command('Fetch.disable');
  await ui.evaluate(`(async()=>{
    const runtime=await import('/@react-refresh');runtime.default.injectIntoGlobalHook(window);
    window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
    await import('/@vite/client');await import('/src/index.css?import');await import('/src/App.css?import');await import('/src/responsive.css?import');
    const source=await (await fetch('/src/components/MapModule.jsx')).text();
    const reactPath=source.match(/from "([^"]*\\/react\\.js[^"]*)"/)[1];
    const react=await import(reactPath);const React=react.default||react;
    const dom=await import('/node_modules/.vite/deps/react-dom_client.js'+reactPath.slice(reactPath.indexOf('?')));
    const Map=(await import('/src/components/MapModule.jsx')).default;
    document.getElementById('root').style.height='100dvh';
    const root=(dom.default||dom).createRoot(document.getElementById('root'));
    window.__saved=[];window.__posts=0;window.__failSave=false;let serial=0;
    const response=(body,status=200)=>Promise.resolve(new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}}));
    window.fetch=(url,options={})=>{
      if(url==='/api/session') return response({authenticated:true,id:42,is_superuser:true});
      if(url==='/api/navigation/nodes/'&&options.method==='POST'){
        window.__posts++;if(window.__failSave)return response({error:'Synthetic save failure'},503);
        const node={...JSON.parse(options.body),id:'custom_fixture',type:'office',aliases:[]};window.__saved.push(node);return response(node,201);
      }
      if(url==='/api/navigation/nodes/')return response({nodes:window.__saved});
      throw new Error('Unexpected fixture request: '+url);
    };
    window.__render=admin=>root.render(React.createElement(Map,{key:++serial,user:admin?{type:'ADMIN',id:42,is_superuser:true}:{type:'GUEST'}}));
    window.__name=value=>{const input=document.querySelector('#campus-node-name');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,value);input.dispatchEvent(new Event('input',{bubbles:true}));};
    window.__render(false);
  })()`);
  await ui.waitFor(`document.querySelector('.campus-nav-map-img')?.naturalWidth>0`);
  const checkChoices = async () => {
    const choices = await ui.evaluate(`[...document.querySelectorAll('.campus-nav-location-item')].map(b=>({name:b.textContent.trim(),svg:!!b.querySelector('svg.campus-location-icon')}))`);
    const labels = choices.map(choice => choice.name);
    assert.ok(choices.every(choice => choice.svg));
    assert.deepEqual(labels, [...labels].sort((a,b)=>a.localeCompare(b,'en',{sensitivity:'base',numeric:true})));
    for (const hidden of ['Restroom (Left Wing)', 'Cathedral', 'Open Court', 'San Nicolas Building']) assert.ok(!labels.includes(hidden));
    assert.ok(labels.includes('PRISM (CFO)'));
  };
  await checkChoices();
  await click('Science Building');
  await ui.waitFor(`document.querySelector('.campus-nav-origin-dest-label')`);
  await checkChoices();
  await click('Change destination');
  assert.equal(await ui.evaluate(`!!(${button('Map tools')})`), false);
  await ui.evaluate(`window.__render(true)`);
  await ui.waitFor(button('Map tools'));
  await click('Map tools');
  await ui.waitFor(`document.querySelector('#campus-node-name')`);
  await ui.evaluate(`window.__name('New Office Fixture')`);
  await click('Add node');
  await ui.waitFor(button('Save node'));
  assert.ok(await ui.evaluate(`${button('Save node')}.disabled`));
  await ui.waitFor(`document.querySelector('.campus-nav-map-img')?.naturalWidth>0&&document.querySelector('.campus-nav-map-img').getBoundingClientRect().width>100`);
  const point = await ui.evaluate(`(()=>{const r=document.querySelector('.campus-nav-map-img').getBoundingClientRect();return {x:r.left+r.width*.3,y:r.top+r.height*.6};})()`);
  await ui.command('Input.dispatchMouseEvent', { type: 'mousePressed', ...point, button: 'left', clickCount: 1 });
  await ui.command('Input.dispatchMouseEvent', { type: 'mouseReleased', ...point, button: 'left', clickCount: 1 });
  await ui.waitFor(`document.querySelector('[data-map-draft]')`);
  const draft = await ui.evaluate(`(()=>{const p=document.querySelector('[data-map-draft]');return {x:+p.getAttribute('cx'),y:+p.getAttribute('cy')};})()`);
  assert.ok(Math.abs(draft.x - 30) < .1 && Math.abs(draft.y - 60) < .1);
  await ui.evaluate(`window.__failSave=true`);
  await click('Save node');
  await ui.waitFor(`document.querySelector('.campus-nav-add-node [role="alert"]')`);
  assert.ok(await ui.evaluate(`!!document.querySelector('[data-map-draft]')`));
  await ui.evaluate(`window.__failSave=false`);
  await click('Save node');
  await ui.waitFor(`document.querySelector('.campus-nav-add-node [role="status"]')`);
  assert.equal(await ui.evaluate(`window.__saved.length`), 1);
  assert.equal(await ui.evaluate(`!!document.querySelector('[data-map-draft]')`), false);
  await click('Back to map');
  await ui.waitFor(`document.querySelector('[data-map-node="custom_fixture"]')`);
  assert.ok(await ui.evaluate(`document.querySelector('.campus-nav-location-list').textContent.includes('New Office Fixture')`));
  await ui.evaluate(`window.__render(false)`);
  await ui.waitFor(`document.querySelector('[data-map-node="custom_fixture"]')`);
  assert.equal(await ui.evaluate(`!!(${button('Map tools')})`), false);
  assert.ok(await ui.evaluate(`document.querySelector('.campus-nav-location-list').textContent.includes('New Office Fixture')`));
  await ui.emulate(390, 844, true);
  await ui.evaluate(`window.__render(true)`);
  await ui.waitFor(button('Map tools')); await click('Map tools');
  await ui.waitFor(`document.querySelector('#campus-node-name')`);
  assert.ok(await ui.evaluate(`document.documentElement.scrollWidth<=390`));
  console.log('PASS: alphabetical destination/origin choices, hidden locations, PRISM rename, SVG icons, admin name/place/save, save failure recovery, public reload, and mobile layout.');
} finally {
  await ui.command('Browser.close');
  ui.close();
}
