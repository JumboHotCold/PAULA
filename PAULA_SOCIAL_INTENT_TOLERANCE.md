# Lightweight conversational intent and typo tolerance

Verified November 7, 2026. This implements the attached intent-recognition specification incrementally within the existing social/knowledge boundary.

## Personality and scope

PAULA remains approachable, concise, patient, and candid about uncertainty. Social acknowledgments use reviewed local responses. University facts continue through verified retrieval. This is application-layer intent/routing work, not model training or a replacement RAG architecture.

No provider, model, embedding dimensions, retrieval cutoff, database schema, authentication rules, data volumes, frontend source, dependencies, or infrastructure were changed. Deferred broader performance/infrastructure work was not implemented.

## Root cause

`chatbot/dialogue.py` already provided fast whole-utterance social rules, an existing MiniLM social classifier, and guarded routing to knowledge. The gratitude rule recognized `thank you`, but omitted common abbreviations and joined/misspelled forms.

Consequently `ty` and `thankyoui` missed the local rules, went through social embedding classification, then reached RAG and its short-question repair fallback. In the initial live reproduction, `thank you` returned `thanks`, while `ty`, `thankyoui`, `TYSM PAULA!!`, `thnak you`, `goodmorning`, `howareyou`, Cebuano gratitude, and brief yes/no/help messages returned repair or knowledge fallbacks.

The request-ID-correlated benchmark confirms the bottleneck: **60 of 81 social requests invoked social embeddings and retrieval before the fix**. None made an external provider call. Unnecessary local classification/retrieval, rather than provider latency, caused these measured delays.

## Implementation

- Added bounded whole-utterance normalization using the existing Unicode NFKC/casefold/word-normalization utility. Factual queries are not passed through social spelling repair or rewritten by it.
- Maintained a small registry of conventional abbreviations (`ty`, `thx`, `tnx`, `tq`, `tysm`) and canonical social phrases. Joined forms are compared to canonical compact phrases; spelling mistakes are handled generically rather than registering every variant.
- Reused the existing edit-distance utility. Fuzzy candidates permit one edit, a protected two-character prefix, compatible phrase word counts, a minimum normalized similarity of 0.82, and stricter substitution handling. Inputs are capped at 120 characters; fuzzy comparison is limited to 5–24 ASCII letters. Numbers, URLs, identifiers, and explicit controls are excluded. The score is an engineering matching signal, not a calibrated probability.
- Unknown single-word subjects/names are kept on knowledge routing instead of being turned into social talk by semantic proximity. Lookalikes such as `tanks`, `thinks`, `thunks`, and `shanks` are rejected by the social matcher.
- Added fast affirmation, negation, capabilities/help, and clarification recognition. These require whole-utterance matches, so `help` can be local while `Help me locate the Registrar office` remains a substantive request.
- Strip shorthand/misspelled thanks only at an explicit social edge with a substantive remaining clause. Dates, negation, qualifiers, and the remaining request span are preserved. Mixed responses retain existing API semantics, including `response_mode: mixed` where appropriate.
- Added a small reviewed Cebuano gratitude reply set (`Walay sapayan!`). Language hints apply to that reply only; explicit English/Filipino preferences still take precedence. No new persistent language state is introduced.
- Preserved local reply variation based only on the current bounded conversation history. No user text or final answers are cached globally.

## Brief contextual responses

`yes`, `no`, `sure`, `okay`, and `dili` do not choose a student category, select a destination, authorize an action, or claim an institutional fact.

When an enrollment/navigation clarification is pending, PAULA acknowledges the reply, repeats the missing choice, and preserves the signed pending task. A subsequent `Transferee student` or `Registrar` then follows the existing grounded procedure/navigation flow. Guest history remains unsaved.

`explain` or `what do you mean?` asks which part of the previous answer needs explanation when an anchor exists. It does not fabricate a paraphrase of institutional facts. Without an anchor it asks what to explain.

## Modified files

| File | Purpose |
| --- | --- |
| `chatbot/social_normalization.py` | Canonical phrases, abbreviation registry, bounded edit matching and temporary language hints |
| `chatbot/dialogue.py` | Local matcher integration, safe social edges, brief-intent rules and unknown-name guard |
| `chatbot/social_responses.py` | Reviewed affirmative/negative/clarification and Cebuano gratitude replies |
| `chatbot/logic.py` | Preserve pending choices and explicit language preferences; context-aware clarification |
| `chatbot/test_social_tolerance.py` | Variant, false-positive, no-model/no-provider, context, language and guest privacy regressions |
| `scripts/benchmark_social_tolerance.py` | Identical before/after guest request matrix |
| `scripts/verify_social_tolerance.py` | Live signed-context/language/isolation and data checks |
| `scripts/verify_social_timing.mjs` | Correlate benchmark request IDs with payload-free timing records |

## Results

**381 automated tests passed**, including 13 new social-tolerance tests plus existing grounding, retrieval, personnel, listing, compound-query, context, enrollment, dialogue, web ingestion, admin asset, provider/runtime and session-isolation tests. Deliberate failure-path fixtures generated expected warning logs; the suite completed successfully.

Live benchmark: identical 27 social inputs plus six factual controls, repeated three times per phase: 99 requests before and 99 after, with no guest persistence.

| Social subset | Before | After |
| --- | ---: | ---: |
| Expected intent labels | 21/81 | 81/81 |
| Local warm p50 HTTP latency | 123.68 ms | 4.46 ms |
| Local warm p95 HTTP latency | 204.64 ms | 23.07 ms |
| Requests with social embeddings | 60/81 | 0/81 |
| Requests with RAG retrieval/query embeddings | 60/81 | 0/81 |
| External-provider requests | 0/81 | 0/81 |
| Cumulative SQL queries for gratitude samples | 468 | 0 |

All 81 request timing records per phase were correlated. The existing performance framework was reused; `social_normalization` adds a nested stage without logging messages, SQL text, identities, cookies, or credentials. Capabilities/help retains existing source-aware starter suggestions, which may read the public FAQ catalog; zero SQL is asserted for gratitude, not every possible social interaction.

These are small sequential local measurements and developer-labeled regression cases, not a load test, independent NLU accuracy estimate, or production latency guarantee. Startup readiness remained separate: the final three-worker wait was approximately 74 seconds. No new cold-start solution was introduced.

All **18 factual-control requests** remained on knowledge/mixed routing. Positive retrieval, navigation action, and unsupported-question safeguards were also checked after the fix. Controls include shorthand thanks before an ICT Director query, thanks after a program question, the previously failing uppercase SPUS compound question, Registrar navigation, an unknown TY scholarship, and a future-year document/fee inquiry.

**Seven live signed-context sequences, 19 turns, passed**: enrollment through thanks/yes/no/dili to the transferee procedure; navigation through thanks/sure to Registrar; clarification after an actual personnel answer; explicit English preference; isolated Cebuano thanks; repeated-response variation; and a fresh conversation's independence.

The actual frontend proxy (`localhost:5173/api/chat`) returned `thanks`, no sources, and `saved: false` for `ty`, `thankyoui`, and `salamat kaayo`. The recorded responses were:

- `ty` / `thankyoui`: “You're welcome! Glad that helped.”
- `salamat kaayo`: “Walay sapayan! Let me know if you need anything else.”

Knowledge, stored embeddings, conversations, and historical chat fingerprints remained unchanged. Only the web container was restarted; PostgreSQL and volumes were preserved. No new accounts or institutional facts were created.

## Evidence

- `PAULA_SOCIAL_TOLERANCE_BEFORE.json`: initial reproduction.
- `PAULA_SOCIAL_TOLERANCE_BEFORE_BENCHMARK.json` / `PAULA_SOCIAL_TOLERANCE_AFTER_BENCHMARK.json`: identical live request matrix.
- `PAULA_SOCIAL_TOLERANCE_TIMING.json`: correlated stage/provider/SQL evidence.
- `PAULA_SOCIAL_TOLERANCE_CONTEXT.json`: live multi-turn/language checks.
- `PAULA_SOCIAL_TOLERANCE_FRONTEND.json`: real Vite proxy checks.
- `PAULA_SOCIAL_TOLERANCE_INTEGRITY.json`: unchanged-data fingerprints.
- `PAULA_SOCIAL_TOLERANCE_READINESS.json`: three-worker readiness.

## Compatibility and limits

Existing API fields, source attribution, context tokens, thread/owner isolation, authenticated-history logic, navigation actions, and RAG grounding remain in use. Automated backend tests and real API checks cover these boundaries; this task did not perform a new physical-device UI test, real credential-based login test, production-host benchmark, or independent institutional fact verification.

Fuzzy repair is deliberately conservative. Multiple edits, missing characters near the beginning, longer expressions, unreviewed dialect phrases, and nuanced yes/no contexts can still need clarification. Reviewed Cebuano gratitude is supported; full Cebuano conversational understanding is not claimed. The existing semantic social router remains available for longer casual conversation. No yes/no answer triggers a real-world or administrative operation.

## Further work, in priority order

| Priority | Work | Benefit | Effort / risk |
| --- | --- | --- | --- |
| 1 | Evaluate held-out English/Filipino/Taglish/Cebuano conversations with student reviewers | Find false positives and misunderstood language beyond synthetic cases | Medium effort, low implementation risk |
| 2 | Add explicitly typed pending questions as new conversational workflows are introduced | More useful yes/no handling with clear referents and authorization boundaries | Medium effort, medium behavioral risk |
| 3 | Measure concurrent traffic and cold starts on the intended deployment host | Establish realistic p50/p95, memory and availability limits | Medium effort; measurement is low risk |

Broader caching, retrieval/index changes, infrastructure changes, and provider/model replacements require their own measured justification and scope. They were not included in this incremental change.
