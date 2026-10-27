# PAULA conversational RAG implementation

> Multi-part extension (28 October 2026):
> [PAULA_COMPOUND_QUERY_REPORT.md](PAULA_COMPOUND_QUERY_REPORT.md).

Implemented on 27 October 2026 in the active GitHub workspace and Docker backend.

## Design and scope

`chatbot/conversation_context.py` is a reusable, per-request resolution layer.
It operates on entity groups, grammatical subject slots and conversational
operations. Existing student categories, departments and campus destinations are
adapters. Public FAQ subjects, locations, personnel, offices, website titles and
active announcement titles also supply entity vocabulary, cached for 60 seconds.
New named topics can be recognized from metadata, quoted subjects or grammatical
objects without a new `if topic == ...` branch in the resolver.

The pipeline is:

1. Normalize the original message and validate bounded context.
2. Recover the active intent from user turns or a verified rolling intent token.
3. Resolve entity substitution, attribute changes, pronouns, comparisons, numbered
   references, or an explicit topic switch. Ask when the referent is ambiguous.
4. Send the effective standalone query through exact, semantic and keyword
   retrieval. Validate evidence against that same effective query.
5. Render fresh stored evidence with citations and a brief English/Filipino
   conversational introduction. Never use old assistant prose as factual evidence.

The existing four-value `process_query` response remains compatible. A tuple
subclass carries optional intent metadata for the HTTP layer. Thresholds remain
unchanged: the configured raw cosine cutoff is still **0.45**.

## Memory and isolation

- Clients send at most four recent exchanges. User constraints are never silently
  truncated; overlong user-history messages are rejected. Long assistant excerpts
  can be shortened because they are not factual retrieval inputs.
- Timestamped history expires after 15 minutes. Older clients without timestamps
  remain compatible; their history is an untrusted routing hint, not proof of
  freshness or factual authority.
- A signed, 15-minute token carries only the latest effective query, owner/thread
  binding and authenticated message anchor. It preserves a long chain when the
  initial question leaves the four-exchange window.
- Authenticated tokens are checked against the user, conversation and latest
  stored message. Guest tokens are scoped to an in-memory tab identifier.
- Tokens are signed, not encrypted. They contain intent text, not answer facts;
  browsers already hold the user's own messages. They are not written to browser
  persistent storage or a new server-side conversation store.
- New Chat/logout clears in-memory context. No guest chat records are saved.
- Only the public vocabulary/model is cached across requests. No conversation is
  stored on the shared bot instance. Existing ownership and active-thread filters
  remain in place.

## Understanding and safeguards

The deterministic path handles entity changes across domains, grammatical or
quoted named subjects, attribute questions, explicit topic changes, English and
Filipino/Taglish continuation markers, comparisons and numbered-step references.
Comparisons retrieve each side independently, with at most two scoped queries;
they do not invent a comparative conclusion. A subsequent ambiguous "it" asks
which side the user means.

Step explanations re-fetch the original topic and quote the matching numbered
step. They do not repeat an amount/name invented in an earlier assistant message.
Explicit years, conditions and categories remain in rewritten queries. Complete
new questions override prior context. Thanks/greetings do not become new factual
topics.

An unresolved elliptical request can make **at most one optional Groq edit call**.
The provider may select an exact prior-user span and an exact current-user span;
the server constructs the replacement. Arbitrary generated queries, added facts,
deleted dates/negation and omitted follow-up conditions are rejected. Ambiguous
pronoun-only fragments ask directly without an edit call. Provider failures also
leave clarification available. Normal deterministic continuations make no rewrite
API call. The optional live provider-edit path was mocked in tests, not benchmarked
against paid external services.

`RetrievalOutcome` distinguishes `ok`, `no_match`, `conflict`, `ambiguous` and
`unavailable`. A failed exact lookup may make one constrained hybrid fallback;
an already-completed hybrid search is not repeated. Conflicts and failures do not
trigger progressively less constrained searches. Same-attribution, same-subject
conflicting excerpts are detected generically; arbitrary differently worded
contradictions are not fully solved.

Active dashboard announcements are now also retrievable as a structured public
source, with their stored publication timestamp. Inactive announcements are
excluded. This does not interpret the publication date as the event date.

## Validation and measurements

The final suite passes **115 automated tests**, including the previous 81
regressions. Cross-topic fixtures cover scholarships, programs, policies,
procedures, offices, personnel, announcements and concepts absent from the core
implementation. These are synthetic test fixtures, not invented university facts.
Tests cover topic switching, ambiguity, preserved constraints, source references,
comparisons, provider edit validation, guest/authenticated isolation, token expiry,
tampering, rolling twelve-turn continuity, inactive announcements, retrieval
failures, and the actual query passed into vector encoding.

```powershell
docker exec paulibot_web python -B manage.py test chatbot.test_grounding chatbot.test_intents chatbot.test_web_crawler chatbot.test_enrollment chatbot.test_conversation_context --verbosity 1
```

The frontend production build passed. Existing large-bundle and Node deprecation
warnings remain. The legacy chat JavaScript passed a Node syntax check after
substitution of Django template expressions.

`PAULA_CONVERSATION_EVALUATION.json` records a paired, read-only PostgreSQL
evaluation of literal fragments versus the implemented resolver plus retrieval.
Six labeled positives cover enrollment procedures, enrollment documents and
faculty rosters, including English, Filipino and Taglish. Each case has a warm-up
and 20 measured repetitions per mode. Expected-source recovery changed from
**0/6 to 6/6**. Per-case warm p50 changed from **49.97–68.34 ms** to **5.01–7.76 ms**;
p95 changed from **54.93–99.49 ms** to **5.66–11.95 ms**. The resolved queries use
existing exact lookups. This is not a general vector-search accuracy improvement
or a university-wide correctness percentage.

The benchmark disables embedding writes and enforces `SET TRANSACTION READ ONLY`.
No LLM calls, network/browser time or model startup are included. The frontend
still has its existing 600 ms message-display delay. Initial live requests after
a web restart previously measured roughly 9–10 seconds; warm retrieval timings
must not be presented as cold end-to-end latency. A proxy request made immediately
after a restart also failed transiently before the backend was ready.

```powershell
docker exec -e HF_HUB_OFFLINE=1 -e OMP_NUM_THREADS=2 -e MKL_NUM_THREADS=2 -e TQDM_DISABLE=1 paulibot_web python -B manage.py shell -c "import runpy; runpy.run_path('scripts/evaluate_conversation.py', run_name='__main__')"
python -B scripts/verify_conversation_http.py
```

`PAULA_CONVERSATION_LIVE_CHECKS.json` records **29 passing live guest checks** through
the Vite proxy, including ten consecutive signed-context follow-ups beyond the
history window and cross-tab rejection. Real
authenticated login/browser interaction was not automated; authenticated request
handling was verified with mocked accounts/storage. No replacement users were
created. Publication visibility was verified with controlled fixtures; the test
does not certify every live institutional announcement or policy.

## Files changed for this implementation

| File | Purpose |
| --- | --- |
| `chatbot/conversation_context.py` | Generic resolution, bounded history, entity vocabulary interface, edit validation |
| `chatbot/context_tokens.py` | Signed, expiring, isolated intent continuity and compatible response metadata |
| `chatbot/retrieval_types.py` | List-compatible evidence status and retrieval outcomes |
| `chatbot/logic.py` | Effective-query orchestration, references, comparisons, optional edit, grounded introductions |
| `chatbot/rag.py` | Public vocabulary, effective-query retrieval outcomes, bounded fallback, announcement source |
| `chatbot/views.py` | Context validation, owner/message binding, additive token response field |
| `chatbot/grounding.py` | Announcement normalization and continuing-category evidence constraint |
| `chatbot/enrollment.py`, `chatbot/personnel.py` | Preserve exact-lookup conflict/ambiguity diagnostics |
| `chatbot/test_conversation_context.py` | Cross-domain and security regression suite |
| `frontend/src/App.jsx`, `frontend/src/api/chatApi.js` | Bounded timestamped memory and rolling token transport |
| `chatbot/templates/chatbot/chat.html` | Equivalent legacy guest history/token support |
| `scripts/evaluate_conversation.py` | Reproducible paired retrieval evaluation |
| `scripts/verify_conversation_http.py` | Real guest multi-turn HTTP verification |
| `PAULA_CONVERSATION_EVALUATION.json`, `PAULA_CONVERSATION_LIVE_CHECKS.json` | Measured results and source-bearing responses |
| `PAULA_CONVERSATIONAL_RAG.md`, `PAULA_RESPONSE_GROUNDING.md` | Current implementation documentation |

## Remaining limits

- A generalized layer is not a guarantee that every possible natural-language
  reference is unambiguous. Complex or unsupported phrasing asks for clarification.
- Factual details stay in source wording; Filipino/Taglish introductions do not
  constitute automatic translation of every stored policy or document.
- Entity metadata is cached briefly and bounded. A new source format may need a
  vocabulary/source adapter, not a new topic-specific resolver branch.
- Source correctness/freshness remains dependent on institutional knowledge
  maintenance. No response mechanism can verify an unpublished policy change.
- General paraphrased contradiction detection and arbitrary step references in
  unnumbered documents remain limited.
- No database schema migration, volume reset, knowledge rewrite, dependency
  installation, account creation, credential copying, commit or push was required.
