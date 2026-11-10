import test from 'node:test';
import assert from 'node:assert/strict';
import { restoredMessages,latestSuggestions } from './suggestions.js';

test('refresh preserves explicit spelling choices even when a similar question was already asked',()=>{
  const rows=[{message:'What programs are offered?',response:'Did you mean "What programs are offered?"? [SUGGESTIONS: "What programs are offered?"]'}];
  const messages=restoredMessages(rows);
  assert.equal(messages[1].suggestionsKind,'choice');
  assert.deepEqual(latestSuggestions(messages).suggestions,['What programs are offered?']);
});

test('restored normal suggestions still filter answered questions',()=>{
  const rows=[{message:'What programs are offered?',response:'Answer [SUGGESTIONS: "What programs are offered?" | "Where is Finance?"]'}];
  assert.deepEqual(latestSuggestions(restoredMessages(rows)).suggestions,['Where is Finance?']);
});
