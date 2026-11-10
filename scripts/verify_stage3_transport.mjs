// Actual frontend transport -> isolated Django HTTP contract, without a browser
// or model/network dependency. Run only against a dedicated test service.
import assert from 'node:assert/strict';
import { sendMessage } from '../frontend/src/api/chatApi.js';

const origin=process.env.PAULA_INTEGRATION_ORIGIN||'http://127.0.0.1:18081';
assert.ok(['http://127.0.0.1:18080','http://127.0.0.1:18081'].includes(origin),'Use the isolated test service');
const httpFetch=globalThis.fetch;
const requests=[];
globalThis.document={cookie:''};
globalThis.fetch=(path,options={})=>{
  assert.ok(path.startsWith('/api/'),'Unexpected transport target');
  requests.push({path,credentials:options.credentials});
  return httpFetch(new URL(path,origin),options);
};
const deadline=Date.now()+30000;
while(true){
  try {const response=await httpFetch(`${origin}/api/health/live`);if(response.ok)break;}
  catch { /* Allow only this dedicated test service to finish starting. */ }
  assert.ok(Date.now()<deadline,'Isolated HTTP service did not start');
  await new Promise(resolve=>setTimeout(resolve,200));
}
let history=[],token=null;
for(const [query,expected] of [['hi','greeting'],['tell me about yourself','identity'],['ty','thanks']]){
  // A stale conversation ID must never make guest transport save a message.
  const reply=await sendMessage(query,999999,history,token,'guest');
  assert.equal(reply.saved,false);assert.equal(reply.conversation_id,null);
  assert.equal(reply.response_mode,expected);assert.ok(reply.response.trim());
  assert.ok(reply.context_token===null||typeof reply.context_token==='string');
  assert.deepEqual(reply.sources,[]);
  history.push({role:'user',content:query},{role:'assistant',content:reply.response});token=reply.context_token;
}
const pending=await sendMessage('How do I enroll?',999999,history,token,'guest');
assert.equal(pending.saved,false);assert.equal(pending.conversation_id,null);
assert.equal(pending.answer_status,'clarification');
assert.ok(pending.context_token,'A pending guest task must carry bounded signed context');
assert.ok(requests.every(request=>request.credentials==='omit'));
const privateHistory=await httpFetch(`${origin}/api/conversations`,{redirect:'manual'});
assert.ok([302,401,403].includes(privateHistory.status),'Anonymous transport cannot read private history');
if(privateHistory.status===302)assert.match(privateHistory.headers.get('location'),/^\/(?:login|accounts\/login)/);
console.log(JSON.stringify({passed:true,scope:'real frontend module -> isolated Django HTTP',guest_turns:4,private_history_status:privateHistory.status}));
