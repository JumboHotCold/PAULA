// Thread-local display filtering. The backend owns knowledge selection.
const marker = /\[SUGGESTIONS?:\s*([^\]]*)\]/gis;
const ignored = new Set(('a an the is are was were be who what which how do does can could would should i me my we our you your '
  + 'of for in on at to as and or with about please tell give show list all available current latest official offered '
  + 'information details detail spus saint st paul university surigao ang mga ng sa sino ano paano po ba naman anong mag').split(/\s+/));
const aliases = { programs: 'program', courses: 'program', course: 'program', programa: 'program', kurso: 'program',
  enrollment: 'enroll', enrolment: 'enroll', enrol: 'enroll', scholarships: 'scholarship', requirements: 'requirement',
  documents: 'document', students: 'student', transferees: 'transferee', freshman: 'freshmen', where: 'location', saan: 'location' };

export function questionKey(value) {
  const words = String(value || '').normalize('NFKC').toLowerCase().replace(/^\s*\[[^\]\n]+\]\s*/, '')
    .match(/[\p{L}\p{N}]+/gu) || [];
  const relevant = [...new Set(words.filter(word => !ignored.has(word))
    .map(word => Object.hasOwn(aliases, word) ? aliases[word] : word))].sort();
  return relevant.join(' ') || (/^(what is|tell me about|give me information about|ano ang)\b/.test(words.join(' '))
    ? 'institution overview' : words.join(' '));
}

export function parseMessage(rawText = '') {
  const text = String(rawText || '');
  const match = [...text.matchAll(marker)].at(-1);
  let suggestions = [];
  if (match) {
    try {
      suggestions = JSON.parse(`[${match[1].replace(/\s+\|\s+/g, ',')}]`);
    } catch {
      // Historical messages also used single-quoted labels.
      suggestions = match[1].split('|').map(value => value.trim().replace(/^["']|["']$/g, ''));
    }
  }
  return { text: text.replace(marker, '').trim(), suggestions: cleanSuggestions(suggestions) };
}

function cleanSuggestions(values) {
  if (!Array.isArray(values)) return [];
  return [...new Set(values.filter(value => typeof value === 'string' && value.trim() && value.length <= 500)
    .map(value => value.trim()))].slice(0, 3);
}

function isConfirmation(text) {
  return /^(?:Did you mean |Ang ibig mo bang sabihin ay |Which question did you mean\?|Alin sa mga tanong ang ibig mong sabihin\?)/i.test(String(text).trim());
}

export function restoredMessages(rows) {
  return rows.flatMap(row => {
    const parsed=parseMessage(row.response);
    return [{text:row.message,isUser:true},{text:row.response,isUser:false,suggestions:parsed.suggestions,
      suggestionsKind:isConfirmation(row.response)?'choice':undefined}];
  });
}

export function latestSuggestions(messages, isTyping = false) {
  const index = messages.length - 1;
  const latest = messages[index];
  if (isTyping || !latest || latest.isUser) return { index: -1, suggestions: [] };
  const values = cleanSuggestions(Array.isArray(latest.suggestions) ? latest.suggestions : parseMessage(latest.text).suggestions);
  // Required clarification choices remain available when the bot asks again.
  const choice = latest.suggestionsKind === 'choice' || (latest.suggestionsKind == null && (isConfirmation(latest.text) || values.some(value =>
    !/^(what|why|how|who|where|when|which|does|do|is|are|can|ano|sino|saan|paano)\b/i.test(value))));
  const asked = new Set(messages.filter(message => message.isUser).map(message => questionKey(message.text)));
  return { index, suggestions: choice ? values : values.filter(value => !asked.has(questionKey(value))) };
}
