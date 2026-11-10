import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync,writeFileSync,mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { frontendStamp } from './buildMetadata.mjs';

test('frontend source stamps are stable, change with source, and validate revision metadata',()=>{
  const root=mkdtempSync(join(tmpdir(),'paula-build-test-'));mkdirSync(join(root,'src'));
  const file=join(root,'src','example.js');writeFileSync(file,'export const value=1;\n');
  const first=frontendStamp({root,revision:'a'.repeat(40)});
  assert.equal(first.git_commit,'a'.repeat(40));assert.match(first.source_digest,/^[a-f0-9]{64}$/);
  assert.deepEqual(frontendStamp({root,revision:'a'.repeat(40)}),first);
  writeFileSync(file,'export const value=2;\n');
  assert.notEqual(frontendStamp({root}).source_digest,first.source_digest);
  assert.equal(frontendStamp({root,revision:'not-a-sha'}).git_commit,null);
});
