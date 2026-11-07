import test from 'node:test';
import assert from 'node:assert/strict';
import { backendUrl } from './backendUrl.js';

test('backend media and admin links use the supplied host rather than phone localhost',()=>{
  assert.equal(backendUrl('/media/avatar.webp','http://192.0.2.1:8080'),'http://192.0.2.1:8080/media/avatar.webp');
  assert.equal(backendUrl('/admin/','https://backend.example.edu'),'https://backend.example.edu/admin/');
});
test('absolute storage URLs and local photo previews remain unchanged',()=>{
  assert.equal(backendUrl('https://storage.example.edu/avatar.webp','https://backend.example.edu'),'https://storage.example.edu/avatar.webp');
  assert.equal(backendUrl('data:image/png;base64,AAAA','https://backend.example.edu'),'data:image/png;base64,AAAA');
});
