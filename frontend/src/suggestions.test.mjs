import test from 'node:test';
import assert from 'node:assert/strict';
import { latestSuggestions, parseMessage, questionKey } from './suggestions.js';

const user = text => ({ text, isUser: true });
const bot = suggestions => ({ text: 'Answer.', isUser: false, suggestions, suggestionsKind: 'related' });

test('only the latest assistant response owns suggestions; sending hides previous chips immediately', () => {
  const messages = [bot(['What is the mission?']), user('What is the vision?'), bot(['What programs are offered?'])];
  assert.deepEqual(latestSuggestions(messages), { index: 2, suggestions: ['What programs are offered?'] });
  assert.equal(latestSuggestions([...messages, user('What programs are offered?')]).index, -1);
  assert.equal(latestSuggestions(messages, true).index, -1);
});

test('manually typed questions and clicked suggestions are both filtered with lexical paraphrases', () => {
  const messages = [user('What courses are available at SPUS?'), bot(['What programs are offered at SPUS?', 'What is the mission?'])];
  assert.deepEqual(latestSuggestions(messages).suggestions, ['What is the mission?']);
  assert.equal(questionKey('Why should I choose SPUS?'), questionKey('Why choose SPUS?'));
  assert.equal(questionKey('Ano ang mga programa sa SPUS?'), questionKey('What programs are offered at SPUS?'));
  assert.notEqual(questionKey('Why not choose SPUS?'), questionKey('Why choose SPUS?'));
  assert.equal(questionKey('Tell me about SPUS'), questionKey('What is Saint Paul University Surigao (SPUS)?'));
});

test('full loaded thread is filtered even when a used question is older than the backend window', () => {
  const messages = [user('What is the mission?'), ...Array.from({ length: 80 }, (_, i) => user(`Question ${i}?`)), bot(['What is the mission?', 'What is the vision?'])];
  assert.deepEqual(latestSuggestions(messages).suggestions, ['What is the vision?']);
});

test('restored legacy messages parse labels and discard obsolete groups', () => {
  const messages = [user('What is the mission?'), { text: 'Answer. [SUGGESTIONS: "What is the mission?" | "What is the vision?"]' }];
  assert.deepEqual(latestSuggestions(messages).suggestions, ['What is the vision?']);
  assert.equal(parseMessage(messages[1].text).text, 'Answer.');
});

test('new conversations and account switches do not inherit seen-question state', () => {
  const reply = bot(['What is the mission?']);
  assert.deepEqual(latestSuggestions([user('What is the mission?'), reply]).suggestions, []);
  assert.deepEqual(latestSuggestions([reply]).suggestions, ['What is the mission?']);
});

test('clarification choices remain usable when an explicit clarification is repeated', () => {
  const reply = { ...bot(['Freshman', 'Transferee', 'Continuing student']), suggestionsKind: 'choice' };
  assert.equal(latestSuggestions([user('Transferee'), reply]).suggestions.length, 3);
});

test('structured empty suggestions win over old markers and malformed metadata is ignored', () => {
  assert.deepEqual(latestSuggestions([{ ...bot([]), text: 'Answer [SUGGESTIONS: "Old question?"]' }]).suggestions, []);
  assert.deepEqual(latestSuggestions([bot([null, {}, '  ', 'What is the vision?', 'What is the vision?'])]).suggestions, ['What is the vision?']);
});

test('protocol supports JSON escaping, apostrophes, fewer than three options and historical single quotes', () => {
  const question = 'What is the "Research" policy?';
  assert.deepEqual(parseMessage(`Answer [SUGGESTIONS: ${JSON.stringify(question)}]`).suggestions, [question]);
  assert.deepEqual(parseMessage("Answer [SUGGESTIONS: 'Where is Finance?']").suggestions, ['Where is Finance?']);
  assert.deepEqual(parseMessage('Answer [SUGGESTION: "Where is Finance?"]').suggestions, ['Where is Finance?']);
  assert.deepEqual(parseMessage('').suggestions, []);
});
