import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
import { connect, metrics } from './mobile_browser.mjs';

const ui = await connect(), checks = [];
const pause = ms => new Promise(resolve=>setTimeout(resolve,ms));
let dialogs=0;
let complete=false;
ui.on('Page.javascriptDialogOpening',()=>{dialogs++;ui.command('Page.handleJavaScriptDialog',{accept:false}).catch(()=>{});});
async function check(name, expression) {
  const value=await ui.evaluate(expression);
  if (!value) { console.log(await ui.evaluate(metrics)); console.log(await ui.evaluate(`({zoom:document.querySelector('.campus-nav-zoom-value')?.textContent,scale:visualViewport.scale,events:window.__gestureEvents?.slice(-25)})`));await ui.screenshot('PAULA_MOBILE_FAILED_CHECK.png'); }
  assert.ok(value, name);
  checks.push({name,passed:true});console.log(name);
}
async function tap(expression) {
  const point=await ui.evaluate(`(() => {const el=${expression};if(!el)throw new Error('Tap target missing');el.scrollIntoView({block:'nearest'});const r=el.getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()`);
  await ui.command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{...point,id:1}]});
  await pause(40);
  await ui.command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await pause(100);
}
async function type(selector,value) {
  await ui.evaluate(`(() => {const el=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,${JSON.stringify(value)});el.dispatchEvent(new Event('input',{bubbles:true}));})()`);
}
const byText=(selector,text)=>`[...document.querySelectorAll(${JSON.stringify(selector)})].find(el=>el.textContent.trim()===${JSON.stringify(text)})`;
const widths=[[320,568],[375,812],[390,844],[430,932],[768,1024],[1024,768],[1280,900]];
try {
  await ui.command('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  if (!process.argv.includes('--fixtures-only')) {
  await ui.command('Page.bringToFront');
  await ui.command('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  await ui.emulate(375,812);
  await ui.command('Page.navigate',{url:'http://localhost:5173'});
  await ui.waitFor(`document.querySelector('.chat-layout')||document.querySelector('.navbar')`);
  await ui.evaluate(`localStorage.clear();sessionStorage.clear();location.reload()`);
  await ui.waitFor(`document.querySelector('.navbar')`);
  for (const [width,height] of widths) {
    await ui.emulate(width,height,width<1100);await pause(100);
    await check(`entry contained ${width}x${height}`,`document.documentElement.scrollWidth<=innerWidth+1`);
  }
  await ui.emulate(375,812);await ui.screenshot('PAULA_MOBILE_ENTRY_FINAL.png');
  await tap(byText('button','Continue as Guest'));await ui.waitFor(`document.querySelector('.chat-input')`);
  const startingTheme=await ui.evaluate(`document.documentElement.getAttribute('data-theme')`);
  await tap(`document.querySelector('.chat-header .theme-toggle')`);
  await check('theme toggles without mobile overflow',`document.documentElement.getAttribute('data-theme')!==${JSON.stringify(startingTheme)}&&document.documentElement.scrollWidth<=375`);
  await tap(`document.querySelector('.chat-header .theme-toggle')`);
  for (const [width,height] of widths) {
    await ui.emulate(width,height,width<1100);await pause(100);
    await check(`chat usable ${width}x${height}`,`(() => {const r=document.querySelector('.input-area').getBoundingClientRect();return document.documentElement.scrollWidth<=innerWidth+1&&r.bottom<=innerHeight+1&&r.top>=0})()`);
  }
  await ui.emulate(375,420);await pause(100);
  await check('composer survives reduced viewport',`document.querySelector('.input-area').getBoundingClientRect().bottom<=420`);
  await ui.emulate(375,812);
  await tap(`document.querySelector('[aria-label="Campus map"]')`);
  await ui.waitFor(`document.querySelector('.campus-nav-map-img')?.naturalWidth>0`);
  for (const [width,height] of [...widths,[812,375],[375,420]]) {
    await ui.emulate(width,height,width<1100);await pause(100);
    const value=await ui.evaluate(metrics);
    assert.ok(value.documentWidth<=width+1,`map overflow ${width}`);
    assert.ok(value.close.bottom<=value.mapHeader.y+1,`close covers header ${width}`);
    assert.ok(value.picker.bottom<=height+1,`picker clipped ${width}x${height}`);
    assert.ok(value.image.bottom<=value.picker.y+1||value.image.right<=value.picker.x+1,`picker covers image ${width}`);
    checks.push({name:`map layout ${width}x${height}`,passed:true,metrics:value});
  }
  await ui.emulate(375,812);await pause(100);
  await ui.evaluate(`window.__gestureEvents=[];['pointerdown','pointerup','pointercancel','touchstart','touchend','click'].forEach(type=>document.addEventListener(type,e=>window.__gestureEvents.push({type,id:e.pointerId,target:e.target.closest('button')?.getAttribute('aria-label')||e.target.tagName}),true))`);
  await type('[aria-label="Search destinations"]','no-such-building');
  await check('location search empty state',`document.querySelector('.campus-nav-location-list').textContent.includes('No locations found')`);
  await type('[aria-label="Search destinations"]','Registrar');
  await tap(byText('.campus-nav-location-item','Registrar Office'));
  await ui.waitFor(`document.querySelector('[aria-label="Search starting locations"]')`);
  await tap(`document.querySelector('[aria-label="Zoom in"]')`);
  await check('zoom control works',`document.querySelector('.campus-nav-zoom-value').textContent==='150%'`);
  const frame=await ui.evaluate(`(() => {const r=document.querySelector('.campus-nav-viewport').getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()`);
  await ui.command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{id:1,x:frame.x-30,y:frame.y},{id:2,x:frame.x+30,y:frame.y}]});
  for(let step=1;step<=4;step++) {await pause(40);await ui.command('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{id:1,x:frame.x-30-step*10,y:frame.y},{id:2,x:frame.x+30+step*10,y:frame.y}]});}
  await pause(100);
  await ui.command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await pause(100);
  await check('two-finger pinch zoom works',`parseInt(document.querySelector('.campus-nav-zoom-value').textContent)>150`);
  const panStart=await ui.evaluate(`document.querySelector('.campus-nav-viewport').scrollLeft`);
  await ui.command('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{id:1,x:frame.x,y:frame.y}]});
  for(let step=1;step<=5;step++) {await pause(40);await ui.command('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{id:1,x:frame.x-step*12,y:frame.y-step*5}]});}
  await pause(100);
  await ui.command('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await pause(100);
  await check('drag pans without choosing a new location',`document.querySelector('.campus-nav-viewport').scrollLeft>${panStart}&&document.querySelector('.campus-nav-origin-dest-label').textContent.includes('Registrar')`);
  // Chromium suppresses compatibility clicks immediately after a scroll
  // gesture. Allow the gesture to finish before moving to a separate control.
  await pause(400);
  await tap(`document.querySelector('[aria-label="Fit map to screen"]')`);
  await ui.waitFor(`document.querySelector('.campus-nav-zoom-value').textContent==='100%'`,2000);
  await check('fit resets map zoom',`document.querySelector('.campus-nav-zoom-value').textContent==='100%'`);
  await ui.screenshot('PAULA_MOBILE_MAP_FINAL.png');
  await tap(byText('.campus-nav-location-item','Main Entrance'));
  await ui.waitFor(`document.querySelector('.campus-nav-path-line')`);
  await check('real backend route visible',`document.querySelector('.campus-nav-directions-summary').textContent.includes('Main Entrance')&&document.querySelector('.campus-nav-path-line').getAttribute('points').length>5`);
  await ui.screenshot('PAULA_MOBILE_ROUTE_FINAL.png');
  await tap(byText('button','Change Starting Point'));
  await ui.evaluate(`window.__mobileRealFetch=window.fetch;window.fetch=(url,options)=>String(url).includes('/api/navigation/route/')?Promise.reject(new Error('Synthetic network failure')):window.__mobileRealFetch(url,options)`);
  await tap(byText('.campus-nav-location-item','Main Entrance'));
  await ui.waitFor(`document.querySelector('[role="alert"]')`);
  await check('route error is visible and recoverable',`document.querySelector('[role="alert"]').textContent.includes('try again')`);
  await ui.evaluate(`window.fetch=window.__mobileRealFetch`);
  await tap(byText('button','Try again'));await ui.waitFor(`document.querySelector('.campus-nav-path-line')`);
  checks.push({name:'route retry uses real backend',passed:true});
  await tap(byText('button','Change destination'));await ui.waitFor(`document.querySelector('[aria-label="Search destinations"]')`);
  checks.push({name:'destination can be changed without restarting chat',passed:true});
  await tap(`document.querySelector('.module-close-btn')`);await ui.waitFor(`document.querySelector('[aria-label="Smart Virtual Tour"]')`);
  await tap(`document.querySelector('[aria-label="Smart Virtual Tour"]')`);await ui.waitFor(`document.querySelector('.vt-aerial-img')?.naturalWidth>0`);
  await tap(`document.querySelector('.vt-aerial-img')`);
  assert.equal(dialogs,0,'Ordinary tour tap opened a calibration alert');
  await check('tour offers five accessible locations',`document.querySelectorAll('.vt-location-list button').length===5`);
  await ui.screenshot('PAULA_MOBILE_TOUR_FINAL.png');
  await tap(`document.querySelector('.vt-location-list button')`);
  await ui.waitFor(`document.querySelector('.vt-viewer canvas')`,20000);
  await check('360 viewer has usable height',`document.querySelector('.vt-viewer').getBoundingClientRect().height>200`);
  await tap(`document.querySelector('.vt-back-btn')`);await ui.waitFor(`document.querySelector('.vt-aerial-img')`);
  checks.push({name:'return from panorama to aerial view',passed:true});
  }

  // Isolated component fixtures. Never impersonate a logged-in user or submit
  // student/admin mutations. Fixture GET responses exist only in this tab.
  ui.on('Fetch.requestPaused',event=>ui.command('Fetch.fulfillRequest',{requestId:event.requestId,responseCode:200,
    responseHeaders:[{name:'Content-Type',value:'application/javascript'}],body:''}).catch(()=>{}));
  await ui.command('Fetch.enable',{patterns:[{urlPattern:'http://localhost:5173/src/main.jsx*',requestStage:'Request'}]});
  await ui.emulate(375,812);await ui.command('Page.navigate',{url:'http://localhost:5173/'});
  await ui.waitFor(`document.readyState==='complete'&&document.querySelector('#root')`);
  await ui.command('Fetch.disable');
  await ui.evaluate(`(async()=>{
    document.getElementById('root').id='mobile-fixture';
    const runtime=await import('/@react-refresh');runtime.default.injectIntoGlobalHook(window);
    window.$RefreshReg$=()=>{};window.$RefreshSig$=()=>type=>type;window.__vite_plugin_react_preamble_installed__=true;
    await import('/@vite/client');await import('/src/index.css?import');await import('/src/App.css?import');await import('/src/responsive.css?import');
    const reactModule=await import('/node_modules/.vite/deps/react.js');window.__React=reactModule.default||reactModule;
    const dom=await import('/node_modules/.vite/deps/react-dom_client.js');window.__uiRoot=(dom.default||dom).createRoot(document.getElementById('mobile-fixture'));
  })()`);
  await ui.evaluate(`(async()=>{const {default:Dashboard}=await import('/src/components/Dashboard.jsx');window.__uiRoot.render(window.__React.createElement(Dashboard,{user:{type:'STUDENT',id:'layout-fixture',name:'Layout fixture'},messages:[],isTyping:false,conversations:[{id:1,title:'A long synthetic conversation title for layout testing'}],onSend:()=>{},onLogout:()=>{},onNewChat:()=>{},onLoadChat:()=>{},onDeleteChat:()=>{}}));})()`);
  await ui.waitFor(`document.querySelector('.hamburger-btn')`);await tap(`document.querySelector('.hamburger-btn')`);
  await ui.waitFor(`document.querySelector('.sidebar').getBoundingClientRect().left>=-.5`);
  await check('student history drawer fits phone',`document.querySelector('.sidebar').getBoundingClientRect().right<=innerWidth&&document.querySelector('.sidebar').classList.contains('sidebar-open')`);
  await tap(`document.querySelector('.profile-trigger')`);await ui.waitFor(`document.querySelector('[role="dialog"]')`);
  await check('profile dialog remains on screen',`(()=>{const r=document.querySelector('[role="dialog"]').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight+1})()`);
  await ui.emulate(375,420);await pause(100);
  await check('profile dialog scrolls at reduced height',`document.querySelector('[role="dialog"]').clientHeight<=420&&getComputedStyle(document.querySelector('[role="dialog"]')).overflowY==='auto'`);
  await ui.command('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'});
  await ui.waitFor(`!document.querySelector('[role="dialog"]')`);
  await ui.emulate(375,812);
  await ui.evaluate(`(async()=>{const {default:Register}=await import('/src/components/RegisterPage.jsx');window.__uiRoot.render(window.__React.createElement(Register,{onNavigateLogin:()=>{}}));})()`);
  await ui.waitFor(`document.querySelector('.register-container')`);
  for (const [width,height] of [[320,568],[375,812],[812,375]]) {
    await ui.emulate(width,height);await pause(100);
    await check(`registration contained ${width}x${height}`,`document.documentElement.scrollWidth<=${width}+1&&innerWidth<=${width}+1`);
  }
  await ui.emulate(375,812);await ui.screenshot('PAULA_MOBILE_REGISTER_FINAL.png');
  await ui.evaluate(`(async()=>{
    window.fetch=async url=>{const path=String(url);let data={};
      if(path.includes('/metrics/'))data={total_enrolled:12,total_queries:34,satisfaction_rate:95,at_risk:1,unresolved_requests:2,pending_enrollments:3};
      else if(path.includes('/campus-pulse/'))data=[{day:2,hour:9,count:3}];
      else if(path.includes('/trending-confusion/'))data=[{category:'Enrollment',count:3}];
      else if(path.includes('/student-needs/'))data={count:1,num_pages:1,current_page:1,results:[{id:1,student_id:'LAYOUT-ONLY',name:'Layout fixture',need_type:'Academic',urgency:'Low',status:'Pending',assigned_advisor:'Unassigned',date:'2026-11-04'}]};
      return new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json'}});
    };
    const {default:Admin}=await import('/src/components/AdminDashboard.jsx');window.__uiRoot.render(window.__React.createElement(Admin,{user:{is_superuser:true},onBackToChat:()=>{}}));
  })()`);
  await ui.waitFor(`document.querySelector('.admin-data-table tbody tr')`);
  for (const [width,height] of [[320,568],[375,812],[768,1024],[1280,900]]) {
    await ui.emulate(width,height,width<1100);await pause(100);
    await check(`admin fixture contained ${width}x${height}`,`document.documentElement.scrollWidth<=${width}+1&&innerWidth<=${width}+1`);
  }
  await ui.emulate(375,812);
  await check('admin table scrolls internally',`(()=>{const e=document.querySelector('.admin-data-table').parentElement;return e.scrollWidth>e.clientWidth&&getComputedStyle(e).overflowX==='auto'})()`);
  await ui.screenshot('PAULA_MOBILE_ADMIN_FINAL.png');
  assert.equal(dialogs,0);
  complete=true;
} finally {
  const target=process.argv.includes('--fixtures-only')?'PAULA_MOBILE_FIXTURE_VERIFICATION.json':'PAULA_MOBILE_VERIFICATION.json';
  await writeFile(target,JSON.stringify({complete,passed:checks.length,checks,dialogs,notes:'Chrome touch emulation. Guest map/routes use actual backend; student, profile and admin layouts use isolated synthetic UI fixtures without accounts or writes.'},null,2));
  ui.close();
}
