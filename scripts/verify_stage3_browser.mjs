// Real UI/API integration using ONLY the isolated synthetic CI account/database.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp,writeFile,mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { connect } from './mobile_browser.mjs';

const root='artifacts/stage3/browser';await mkdir(root,{recursive:true});
const health=await (await fetch('http://127.0.0.1:18080/api/health/ready')).json();
assert.equal(health.ready,true,'Isolated backend must be ready');
assert.equal(health.expected_workers,1,'This must be the isolated test service');
try {await fetch('http://127.0.0.1:9340/json/version');throw new Error('Dedicated browser port occupied');}
catch(error) {if(error.message==='Dedicated browser port occupied')throw error;}
const profile=await mkdtemp(join(tmpdir(),'paula-stage3-browser-'));
const browser=spawn('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',[
  '--headless=new','--remote-debugging-port=9340',`--user-data-dir=${profile}`,'--no-first-run','--no-default-browser-check','http://127.0.0.1:5174/'
],{windowsHide:true,stdio:'ignore'});
const report={scope:'Isolated CI account and tmpfs database; no personal browser profile or production account',backend:health,requests:[]};
let page;
try {
  page=await connect();await page.command('Network.enable');
  page.on('Network.requestWillBeSent',event=>{if(event.request.url.endsWith('/api/chat')){
    const payload=JSON.parse(event.request.postData);
    report.requests.push({message:payload.message,mode:payload.mode,conversation_id:payload.conversation_id,has_context_token:Boolean(payload.context_token)});
  }});
  await page.waitFor(`document.querySelector('#student_id')`);
  await page.evaluate(`(() => {
    const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    for(const [selector,value] of [['#student_id','C-2099-0001'],['#password','Synthetic-Stage3-Only-2026!']]) {
      const input=document.querySelector(selector);set.call(input,value);input.dispatchEvent(new Event('input',{bubbles:true}));
    }
  })()`);
  await page.evaluate(`document.querySelector('#student_id').form.requestSubmit()`);
  await page.waitFor(`document.querySelector('.chat-input')&&!document.querySelector('.chat-input').disabled`,30000);
  report.logged_in=await page.evaluate(`!document.body.textContent.includes('Guest Mode: Chat history not saved')`);
  assert.equal(report.logged_in,true);
  async function send(text,needle) {
    await page.waitFor(`document.querySelector('.chat-input')&&!document.querySelector('.chat-input').disabled`);
    const before=await page.evaluate(`document.querySelectorAll('.message-wrapper.bot').length`);
    await page.evaluate(`(() => {const input=document.querySelector('.chat-input');input.value=${JSON.stringify(text)};input.form.requestSubmit();})()`);
    await page.waitFor(`document.querySelectorAll('.message-wrapper.bot').length>${before}&&!document.querySelector('.chat-input').disabled&&[...document.querySelectorAll('.message-wrapper.bot')].at(-1)?.textContent.includes(${JSON.stringify(needle)})`,30000);
  }
  async function reload() {
    let timer;
    const loaded=new Promise((resolve,reject)=>{
      page.on('Page.loadEventFired',resolve);timer=setTimeout(()=>reject(new Error('Reload did not finish')),30000);
    });
    try {await page.command('Page.reload',{ignoreCache:true});await loaded;}
    finally {clearTimeout(timer);}
  }
  await send('What is the fixture president?','Reviewed synthetic');
  await send('What is the fixture preseidnt?','Did you mean');
  report.before_refresh=await page.evaluate(`({chips:[...document.querySelectorAll('.follow-up-chip')].map(b=>({text:b.textContent,disabled:b.disabled}))})`);
  await reload();
  await page.waitFor(`document.querySelector('.follow-up-chip')&&!document.querySelector('.chat-input').disabled`,30000);
  report.after_refresh=await page.evaluate(`({chips:[...document.querySelectorAll('.follow-up-chip')].map(b=>({text:b.textContent,disabled:b.disabled}))})`);
  assert.equal(report.after_refresh.chips.length,1);
  assert.equal(report.after_refresh.chips[0].disabled,false);
  await page.evaluate(`Promise.all(document.getAnimations().filter(a=>a.effect?.getComputedTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})))`);
  const chip=await page.evaluate(`(() => {const b=document.querySelector('.follow-up-chip');b.scrollIntoView({block:'nearest'});const r=b.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2,width:r.width,height:r.height,opacity:getComputedStyle(b).opacity};})()`);
  assert.ok(chip.width>=44&&chip.height>=40&&Number(chip.opacity)>.95,'Choice must be visible and large enough to click');
  report.choice_hit_target=chip;
  await page.screenshot(join(root,'choices-after-refresh.png'));
  await page.command('Input.dispatchMouseEvent',{type:'mousePressed',x:chip.x,y:chip.y,button:'left',clickCount:1});
  await page.command('Input.dispatchMouseEvent',{type:'mouseReleased',x:chip.x,y:chip.y,button:'left',clickCount:1});
  await page.waitFor(`!document.querySelector('.chat-input').disabled&&[...document.querySelectorAll('.message-wrapper.bot')].at(-1)?.textContent.includes('Reviewed synthetic')`);
  report.clicked_choice_answer=true;
  await send('What is the fixture preseidnt?','Did you mean');
  await reload();
  await page.waitFor(`document.querySelector('.follow-up-chip')&&!document.querySelector('.chat-input').disabled`);
  await send('yes','Reviewed synthetic');report.yes_after_refresh=true;
  await send('What programs are offered at SPUS?','Bachelor');
  report.list_items=await page.evaluate(`[...document.querySelectorAll('.message-wrapper.bot')].at(-1).querySelectorAll('.answer-list li').length`);
  assert.ok(report.list_items>=4,'Program answer must render semantic list items');
  report.bullet_style=await page.evaluate(`getComputedStyle([...document.querySelectorAll('.answer-list')].at(-1)).listStyleType`);
  assert.equal(report.bullet_style,'disc');
  await page.emulate(390,844);
  await page.evaluate(`Promise.all(document.getAnimations().filter(a=>a.effect?.getComputedTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})))`);
  await page.screenshot(join(root,'programs-mobile.png'));
  report.layout=await page.evaluate(`({viewport:innerWidth,document:document.documentElement.scrollWidth,build:window.__PAULA_BUILD__})`);
  assert.ok(report.layout.document<=report.layout.viewport+2,'Mobile answer must not overflow horizontally');
  assert.match(report.layout.build.git_commit,/^[a-f0-9]{40}$/);
  assert.match(report.layout.build.source_digest,/^[a-f0-9]{64}$/);
  report.passed=true;
} catch(error) {
  report.passed=false;report.error=error.message;
  if(page){report.visible_text=await page.evaluate(`document.body?.textContent.slice(0,1600)||''`);await page.screenshot(join(root,'failure.png'));}
  throw error;
} finally {
  await writeFile(join(root,'result.json'),JSON.stringify(report,null,2));
  if(page){await page.command('Browser.close').catch(()=>{});page.close();}
  browser.kill();
}
