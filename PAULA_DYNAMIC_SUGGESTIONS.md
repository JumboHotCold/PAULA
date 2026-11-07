# PAULA dynamic follow-up suggestions

Implemented and verified on 4 November 2026.

## Problem and resulting behavior

The response engine appended the same three questions to ordinary answers and
fallbacks. React rendered the suggestion group under every historical response.
Clicking a question did not consume it. The reproduced five-turn conversation
had four identical generic groups, including a programs suggestion immediately
after the programs answer. `PAULA_SUGGESTIONS_BEFORE.json` records this behavior.

The API now selects up to three related questions from existing, embedded public
FAQ records. Selection uses the current/resolved question, displayed source
categories and offices, known entities, and questions already asked. Questions
with the same stored answer are deduplicated even when their labels differ.
This avoids recommending the same program list under a second title.

The active React dashboard displays chips only below the latest assistant
response. Sending a typed or clicked question removes the older group immediately.
Restored conversations use the same filtering, including old stored marker
responses. New chats and account switches use their own message state.

## Actual final replay through Vite

| After this question | Actual next questions, abbreviated here only |
| --- | --- |
| Tell me about SPUS? | SPUS vision and mission; Paulinian core values |
| Why should I choose SPUS? | College courses/programs; graduate-school programs |
| What programs are offered at SPUS? | Graduate-school programs; transferee documents; freshman documents |
| How do I enroll at SPUS? | Original freshman/transferee/continuing clarification choices |
| Transferee student | Transferee documents; subject-change approval; Registrar location |
| Selected transferee-documents question | Subject-change approval; Registrar location |

All six requests returned the expected sourced answer or enrollment clarification,
with `saved: false` and no conversation ID. Full labels, answers, timings and
sources are in `PAULA_SUGGESTIONS_AFTER.json`.

An isolated Chrome guest test also typed the opening question and clicked the
vision/mission suggestion. The first reply then had zero chip groups, the newest
reply had one group, and the clicked question was absent from that group.
`PAULA_SUGGESTIONS_BROWSER.json` and `PAULA_SUGGESTIONS_BROWSER.png` record this.

## Grounding, isolation and compatibility

- No additional LLM, embedding or vector-search call generates recommendations.
  The helper reads public FAQ metadata and database-computed answer digests.
- Labels use stored question wording. Malformed text, control injection,
  conflicting exact-question answers and extracted handbook headings are excluded.
- Explicit clarification and compound-navigation controls retain their existing
  behavior. They are choices required to complete a request, not generic FAQs.
- Numeric scopes that were not requested, conflicting college/student-category
  scopes, and unrelated responsible offices are filtered. Related results are
  not padded to three with unrelated office questions.
- The API accepts at most 64 prior question strings of at most 500 characters
  for exclusions. These do not enter factual evidence or change authentication.
  The existing eight-message conversational context remains unchanged.
- React additionally filters the full loaded thread. Guest exclusions stay in
  transient browser/request state; no guest chat storage or shared user-memory
  cache was introduced.
- Structured `suggestions` and `suggestions_kind` fields are returned alongside
  the existing `[SUGGESTIONS: ...]` marker. Authenticated saved responses retain
  that marker, so historical messages can still be parsed without schema changes.

## Validation and measured cost

- **252 backend tests passed**, including 21 new suggestion tests for relevance,
  duplicate answers, previously asked questions, English/Filipino lexical forms,
  scope constraints, source conflicts, malformed input, controls, exhaustion,
  new-topic extensibility and guest isolation.
- **9 Node tests passed**, covering transport isolation and latest-only React
  presentation, typed/clicked questions, restored threads, long threads, new-chat
  reset, account-state separation and variable-length suggestion groups.
- **18 PostgreSQL authentication/session integration checks passed**. Temporary
  changes rolled back; no replacement accounts were created.
- Frontend production build passed, retaining the existing large-chunk warning.
- Six live replay requests and a real browser click workflow passed.

Matched traces in `PAULA_SUGGESTIONS_TIMINGS.json` show the recommendation step
took **22.58–44.71 ms** across the five ordinary replay replies. The clarification
reply bypassed catalog selection. All six replay requests made zero provider
calls. HTTP durations were **16.98–568.11 ms** in this small sequential smoke run;
these are individual observations, not a new p95 benchmark or concurrency result.

`PAULA_SUGGESTIONS_INTEGRITY.json` confirms unchanged knowledge, embeddings and
history fingerprints: **138 FAQs, 12 staff records, 476 web resources,
139 conversations and 176 messages**.

## Scope and remaining limitations

Recommendations use conservative lexical matching and public FAQ metadata, not
unrestricted semantic reasoning. Some paraphrases may not be recognized as the
same previously asked question. Backend exclusions are bounded to 64 questions;
the React display also checks the full loaded thread.

Stored FAQ labels are predominantly English and remain in their source language.
Sources available only as staff/web/handbook records do not automatically gain
new generated question labels. New eligible FAQs are available on the next
request. Source availability is not certification of institutional freshness;
existing retrieval/conflict/grounding checks still decide the actual answer.

An initial live test caught a document-code procedure title that the existing
router did not answer, and recommendations for another student category. Those
labels/scopes are now excluded and regression-tested. The underlying handling of
arbitrary document-code questions was not changed in this task.

Latest-only chip presentation is implemented in the active React `Dashboard`.
Other clients still receive the text marker but control their own presentation.
The initial empty-chat starter grid remains available before the first message.

## Modified implementation files

- `chatbot/suggestions.py`: catalog selection, exclusions, novelty, safety and protocol.
- `chatbot/logic.py`: removes repeated default footer questions; preserves explicit choices.
- `chatbot/views.py`: request-local augmentation before authenticated persistence.
- `chatbot/test_suggestions.py`: backend regressions.
- `frontend/src/suggestions.js`: parsing and full-thread/latest-reply filtering.
- `frontend/src/suggestions.test.mjs`: frontend regressions.
- `frontend/src/components/Dashboard.jsx`: latest reply owns the chip group.
- `frontend/src/components/MessageBubble.jsx`: legacy component shares the variable-length marker parser.
- `frontend/src/App.jsx`: thread exclusions and structured response metadata.
- `frontend/src/api/chatApi.js`, `chatApi.test.mjs`: bounded transient exclusions.
- `scripts/verify_suggestions_http.py`: original conversation replay and selected-question check.
- `scripts/verify_suggestions_browser.mjs`: isolated Chrome guest click test.

No database migration, knowledge ingestion, dependency installation, retrieval
cutoff change, or provider/model configuration change was needed.
