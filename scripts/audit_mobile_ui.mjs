import { writeFile } from 'node:fs/promises';
import { connect, metrics } from './mobile_browser.mjs';

const phase = process.argv[2] || 'before';
const ui = await connect();
const results = [];
try {
  await ui.emulate(375, 812);
  await ui.command('Page.navigate', { url: 'http://localhost:5173' });
  await ui.waitFor(`document.querySelector('.navbar') || document.querySelector('.chat-layout')`);
  if (await ui.evaluate(`Boolean(document.querySelector('.chat-layout'))`)) {
    await ui.evaluate(`localStorage.clear();sessionStorage.clear();location.reload()`);
    await ui.waitFor(`Boolean(document.querySelector('.navbar'))`);
  }
  for (const [width, height] of [[320,568],[375,812],[768,1024]]) {
    await ui.emulate(width,height);
    results.push({screen:'entry',...(await ui.evaluate(metrics))});
  }
  await ui.emulate(375,812);
  await ui.screenshot(`PAULA_MOBILE_ENTRY_${phase.toUpperCase()}.png`);
  await ui.evaluate(`[...document.querySelectorAll('button')].find(el=>el.textContent.trim()==='Continue as Guest').click()`);
  await ui.waitFor(`Boolean(document.querySelector('.chat-input'))`);
  results.push({screen:'chat',...(await ui.evaluate(metrics))});
  await ui.evaluate(`document.querySelector('.chat-input').value='Where is the Registrar office?';document.querySelector('.input-wrapper').requestSubmit()`);
  await ui.waitFor(`Boolean(document.querySelector('.campus-nav-container'))`);
  await ui.waitFor(`document.querySelector('.campus-nav-map-img')?.complete`);
  for (const [width,height] of [[320,568],[375,812],[812,375],[768,1024],[1280,900]]) {
    await ui.emulate(width,height,width<1000);
    await new Promise(resolve=>setTimeout(resolve,200));
    results.push({screen:'map',...(await ui.evaluate(metrics))});
  }
  await ui.emulate(375,812);
  await ui.screenshot(`PAULA_MOBILE_MAP_${phase.toUpperCase()}.png`);
  await writeFile(`PAULA_MOBILE_${phase.toUpperCase()}.json`,JSON.stringify(results,null,2));
  console.log(JSON.stringify(results));
} finally {ui.close();}
