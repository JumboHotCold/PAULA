// Existing administrator, short-lived isolated DB session, real Vite/Django GETs.
// Never prints session credentials, changes passwords, creates users, or chats.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { writeFile } from 'node:fs/promises';
import { connect } from './mobile_browser.mjs';
const ui = await connect(), checks = [];
let sessionKey = null, complete = false;
const shell = code => execFileSync('docker', ['exec', 'paulibot_web', 'python', '-B', 'manage.py', 'shell', '-c', code], { encoding: 'utf8', timeout: 60000 });
async function check(name, expression) {
  assert.ok(await ui.evaluate(expression), name);
  checks.push({ name, passed: true }); console.log(name);
}
const button = label => `[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(label)})`;
try {
  const session = JSON.parse(shell(`import json
from importlib import import_module
from django.conf import settings
from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY
from chatbot.models import CustomUser
user=CustomUser.objects.filter(is_active=True,is_staff=True,is_superuser=True).first()
assert user is not None
store=import_module(settings.SESSION_ENGINE).SessionStore()
store[SESSION_KEY]=str(user.pk)
store[BACKEND_SESSION_KEY]='django.contrib.auth.backends.ModelBackend'
store[HASH_SESSION_KEY]=user.get_session_auth_hash()
store.set_expiry(300)
store.save()
print(json.dumps({'key':store.session_key,'cookie':settings.SESSION_COOKIE_NAME}))`));
  sessionKey = session.key;
  await ui.command('Network.enable');
  await ui.command('Network.clearBrowserCookies');
  await ui.command('Network.setCookie', { name: session.cookie, value: session.key, url: 'http://localhost:5173', path: '/', httpOnly: true, sameSite: 'Lax' });
  await ui.emulate(1280, 900, false);
  await ui.evaluate(`localStorage.clear();sessionStorage.clear();localStorage.setItem('paulibot_user',JSON.stringify({type:'GUEST',id:null,name:'Guest'}))`);
  await ui.command('Page.navigate', { url: 'http://localhost:5173/admin' });
  await ui.waitFor(`document.querySelector('.admin-title')?.textContent==='Institutional Analytics'`);
  await check('real Docker admin session restores analytics over Vite despite saved guest state', `JSON.parse(localStorage.getItem('paulibot_user')).type==='ADMIN'&&!document.querySelector('.guest-warning-badge')`);
  await ui.evaluate(`(${button('← Back to Chat')}).click()`); await ui.waitFor(`document.querySelector('.chat-layout')`);
  await ui.evaluate(`document.querySelector('[aria-label="Campus map"]').click()`);
  await ui.waitFor(button('Map tools'));
  await check('real backend-verified administrator sees Map Tools after Back to Chat', `!!(${button('Map tools')})&&!document.querySelector('.guest-warning-badge')`);
  await ui.evaluate(`(${button('Map tools')}).click()`); await ui.waitFor(`document.querySelector('.campus-nav-mapper-panel')`);
  await check('real administrator can open coordinate mapper', `!!document.querySelector('.campus-nav-mapper-copy-btn')`);
  await ui.command('Page.reload'); await ui.waitFor(`document.querySelector('.chat-layout')`);
  await ui.evaluate(`document.querySelector('[aria-label="Campus map"]').click()`); await ui.waitFor(button('Map tools'));
  await check('real authenticated identity and map authorization survive page refresh', `!!(${button('Map tools')})&&!document.querySelector('.guest-warning-badge')`);
  complete = true;
} finally {
  await ui.command('Network.clearBrowserCookies').catch(() => {});
  if (sessionKey) {
    // This key came from SessionStore, not user input; only delete our own row.
    assert.match(sessionKey, /^[a-z0-9]{32}$/);
    shell(`from django.contrib.sessions.models import Session; Session.objects.filter(session_key='${sessionKey}').delete()`);
  }
  await writeFile('PAULA_ADMIN_HANDOFF_LIVE.json', JSON.stringify({ complete, passed: checks.length, checks,
    temporary_test_session_removed: !!sessionKey,
    notes: 'Real Docker session and Vite proxy; existing active superuser, ephemeral 5-minute session removed afterward. No credential-based login claim; no account, password, institutional fact, map-coordinate, or chat-history changes.' }, null, 2));
  ui.close();
}
