import assert from 'node:assert/strict';
import test from 'node:test';
import { userFromLogin, userFromSession, restoreIdentity } from './authIdentity.js';

const admin = { authenticated: true, id: 'admin-fixture', is_superuser: true };
const guest = { type: 'GUEST', id: null, is_superuser: true };

test('both login forms recognize server-confirmed superusers immediately', () => {
  assert.equal(userFromLogin({ account_id: admin.id, is_superuser: true }, 'fallback').type, 'ADMIN');
  assert.equal(userFromLogin({ student_id: 'S-1', is_superuser: false }, 'fallback').type, 'STUDENT');
  assert.equal(userFromLogin({ account_id: 'S-1', is_superuser: 'true' }, 'fallback').is_superuser, false);
});
test('opening React admin restores a real admin despite stale guest state or absent local profile', () => {
  for (const stored of [guest, null]) {
    const result = restoreIdentity(stored, admin, true);
    assert.equal(result.user.type, 'ADMIN');
    assert.equal(result.user.id, admin.id);
  }
});
test('a guest page never silently adopts an admin session or its identity', () => {
  const result = restoreIdentity(guest, admin);
  assert.equal(result.user.type, 'GUEST');
  assert.equal(result.user.id, null);
  assert.equal(result.user.is_superuser, false);
  assert.equal(result.availableAdmin.id, admin.id);
});
test('a saved guest cannot hide the React admin login form when no admin is authenticated', () => {
  assert.equal(restoreIdentity(guest, { authenticated: false }, true).user, null);
});
test('saved admin flags cannot grant privilege without a matching verified session', () => {
  const stored = { type: 'ADMIN', id: 'S-1', is_superuser: true };
  assert.equal(restoreIdentity(stored, { authenticated: true, id: 'S-1', is_superuser: false }).user.type, 'STUDENT');
  assert.equal(restoreIdentity(stored, { authenticated: false }).user, null);
  assert.equal(restoreIdentity(stored, { authenticated: true, id: 'S-2' }).user, null);
});
test('restored profile data is isolated by account and guest names do not become admin names', () => {
  assert.equal(userFromSession(admin, { type: 'STUDENT', id: 'another', nickname: 'Private' }).nickname, undefined);
  assert.equal(userFromSession(admin, guest).name, admin.id);
  assert.equal(userFromSession(admin, { type: 'ADMIN', id: admin.id, name: 'Existing name' }).name, 'Existing name');
});
test('network failures retain only safe guest state; malformed identities do not restore privileges', () => {
  assert.equal(restoreIdentity(guest, null).user.type, 'GUEST');
  assert.equal(restoreIdentity({ type: 'ADMIN', id: admin.id }, null).user, null);
  assert.equal(userFromSession({ authenticated: true, is_superuser: true }), null);
});
