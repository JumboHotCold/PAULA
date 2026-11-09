import test from 'node:test';
import assert from 'node:assert/strict';
import { messageBlocks } from './messageBlocks.js';

test('program lists and numbered procedures preserve headings, groups and numbering',()=>{
  const blocks=messageBlocks('**Programs**\n- BS IT\n- BS Nursing\n\n**Procedure**\n3. Submit records\n4. Pay at Finance');
  const lists=blocks.filter(block=>block.type==='list');
  assert.equal(lists.length,2);assert.equal(lists[0].ordered,false);assert.equal(lists[0].items.length,2);
  assert.equal(lists[1].ordered,true);assert.equal(lists[1].items[0].number,3);
  assert.equal(lists[1].items[1].text,'Pay at Finance');
});
