# PAULA conversational enhancement: implementation and validation

4 November 2026. Implemented and activated in the local Docker web service.

## What changed

PAULA now separates social conversation from institutional questions before
retrieval. Greetings, acknowledgements, thanks, wellbeing, farewells, simple
jokes, encouragement, preferences, identity and capability questions have bounded
conversational responses in English or Filipino/Taglish. Mixed messages retain
their factual request and use the existing knowledge retrieval and grounding.

Examples verified through the running application:

- `Okay` receives `Got it!`, rather than a thank-you response.
- `How are you?` receives a friendly readiness response without a KB lookup.
- `Hi! Who is the ICT Director and CEIT Dean?` acknowledges the greeting and
  returns the independently sourced personnel answers.
- An enrollment clarification survives `Thank you`, an emotional statement,
  `Taglish please`, and `Okay`, even after the original question leaves the
  four-turn history window. `I am a transferee` still retrieves URO-PR-017.
- A subsequent `How about old students?` retrieves URO-PR-016.
- `How about CHS?` continues the preceding personnel topic after a social turn.

This is a conservative conversational layer. It does not provide unrestricted
general-purpose chat or claim human experiences. Institutional facts continue
to come from eligible stored evidence.

## Implementation

`chatbot/dialogue.py` provides a reusable route object and a per-worker semantic
intent classifier. Common social acts use fast full-message rules. Other social
phrasing can use the existing cached MiniLM model against 64 public intent
examples, including negative knowledge examples. The model is shared with RAG;
no additional model, dependency, institutional embeddings, or database vectors
are created. The public prototype matrix uses approximately 192 KiB per worker.

Social classification requires cosine similarity of at least 0.65 and a margin
of at least 0.08 over the next intent. These are intent-routing values; the
existing document retrieval cutoff remains **0.45**. Explicit institutional
entities, factual constraints, dates/numbers, references, and instruction-like
requests have conservative guards. Unknown phrases and future entities default
to the existing contextual knowledge path. The router is not the evidence gate.

`chatbot/social_responses.py` selects locally from fixed non-factual replies,
avoiding exact repetition within the bounded supplied history. An early version
asked Groq to select a reply ID. Live measurements showed up to 3.27 seconds for
that unnecessary call, so it was removed. The final social path has no provider
call, retry, or provider dependency.

`chatbot/response_style.py` adds short friendly introductions outside source
excerpts. It preserves institutional text, names, amounts, dates, conditions,
citations and actions. It localizes PAULA's own enrollment/navigation questions;
it does not translate institutional evidence. Existing follow-up introductions
are not duplicated.

`chatbot/conversation_context.py` filters social interludes from intent replay.
Feedback such as `That is wrong` re-fetches the previous question against the
current sources. Assistant prose is never promoted into factual evidence.
New fully specified questions retain the existing topic-switching behavior.

`chatbot/context_tokens.py` extends existing signed continuity tokens with an
optional language preference and pending clarification intent. Tokens remain
bound to owner, thread, authenticated message anchor, and a 900-second TTL.
They contain intent state, not source answers, and are signed rather than
encrypted. History remains bounded to eight messages, with the existing size
and timestamp validation. The API validates tokens before supplying state to
the logic layer. No cross-request user state is kept in the shared router.

Authenticated messages still persist together in their owned conversation.
Guest messages and context are not saved as database chat history. Explicit
guest mode continues to override a stale authenticated browser cookie.

`chatbot/readiness.py` prepares the public intent vectors using the existing
worker model before marking that worker ready. A prototype initialization
failure leaves its marker unready. Request timing adds `dialogue_routing`,
`social_query_embedding`, and `social_reply` stages without logging prompts,
answers, account identifiers, or conversation state.

## Validation results

| Check | Result |
|---|---|
| Backend regression suite | 285 tests passed, including 33 new dialogue tests |
| Existing frontend transport/suggestion tests | 9 passed |
| Synthetic routing scenarios using actual cached MiniLM | 82/82 passed; zero institutional questions misrouted in this set |
| Live guest conversational sequence through Vite | 20 steps passed |
| Live About SPUS checks, including missing future-date knowledge | 14 passed |
| Live compound, partial success, conflict, multilingual and isolation checks | 12 passed |
| Dynamic suggestion replay | 6 steps passed |
| Existing PostgreSQL authentication/privacy checks | 18 passed |
| New PostgreSQL conversational session checks | 11 passed |
| Native Chrome React guest-chat check | 6 steps passed |
| Cited excerpts checked against actual PostgreSQL records | 33/33 preserved verbatim |

The session checks used existing accounts and a fixture retriever to isolate
ownership/persistence behavior. Every temporary database/session change was
rolled back; no accounts were created. Live factual checks used the actual
Docker PostgreSQL knowledge sources.

The first routing evaluation passed 77/82 cases. Five failures concerned commas
before addresses, such as `Hello, PAULA`. General punctuation handling corrected
those failures. The initial result is retained in
`PAULA_DIALOGUE_ROUTING_INITIAL.json`. The final set is consequently a regression
suite, not an independent held-out accuracy estimate. No document-retrieval or
intent-similarity thresholds were fitted to this evaluation.

The first browser harness attempt ran before Chrome DevTools was ready. Adding
a bounded startup wait corrected the harness; the six UI steps then passed.
The intermediate backend check also exposed a terminal punctuation expectation
in a query-span test, which was aligned with delimiter stripping. The final
reported suites have no failures.

## Measured latency

Identical 12 public synthetic queries, repeated three times in each phase:
36 sequential local HTTP requests per phase, guest mode, after service readiness.
Percentiles use nearest rank. Benchmarks are through host port 8080; separate
functional checks exercise Vite at port 5173 and the actual browser.

| Request group | n per phase | Before p50 | After p50 | Before p95 | After p95 |
|---|---:|---:|---:|---:|---:|
| Social | 24 | 145.38 ms | 8.29 ms | 1,070.60 ms | 39.98 ms |
| Mixed greeting plus personnel question | 3 | 245.34 ms | 167.38 ms | 397.61 ms | 193.74 ms |
| Institutional factual/compound/clarification | 9 | 112.76 ms | 67.74 ms | 511.88 ms | 597.66 ms |

All 36 final samples were correlated with structured Docker request timings.
The 24 social requests made **zero external provider calls and zero SQL queries**.
Authenticated requests still require ownership checks and chat persistence.

The institutional tail increased slightly in this small sample. This phase does
not establish a general RAG speedup or concurrency capacity. Some old social
queries returned insufficient-information responses, so latency is accompanied
by routing/functional checks rather than treated as equivalent answer quality.

Final activation to all three workers ready took **89.49 seconds**, including
container startup. Each worker took approximately 63.7–64.1 seconds to initialize
its embedding model and social prototypes. All three reported
`social_router_ready: true`. Their first simultaneous calendar requests after
readiness took approximately 1.59 seconds each. Cold service startup remains
separate from warm response latency and is still a deployment consideration.

## Data integrity

Full-row fingerprints, including stored embedding arrays, match before and
after validation for all five audited models:

| Model | Unchanged records |
|---|---:|
| StaffMember | 12 |
| FAQ | 138 |
| WebResource | 476 |
| Conversation | 139 |
| ChatHistory | 176 |

Proof: `PAULA_DIALOGUE_INTEGRITY.json`. No knowledge ingestion, migration,
historical cleanup, database-volume reset, embedding regeneration, new package,
paid service, response cache, streaming, or worker-count change was introduced.

## Files for this phase

New production modules: `chatbot/dialogue.py`, `chatbot/social_responses.py`,
`chatbot/response_style.py`.

Updated integration: `chatbot/logic.py`, `chatbot/conversation_context.py`,
`chatbot/context_tokens.py`, `chatbot/intents.py`, `chatbot/views.py`,
`chatbot/readiness.py`. The API adds optional `response_mode` metadata and uses
the existing context-token transport; React production code required no change.
Other pre-existing workspace changes belong to earlier tasks.

Tests/data: `chatbot/test_dialogue.py`, `chatbot/dialogue_cases.py`.

Reproducible scripts:

- `scripts/benchmark_dialogue_http.py`
- `scripts/evaluate_dialogue_routing.py`
- `scripts/verify_dialogue_http.py`
- `scripts/verify_dialogue_sessions.py`
- `scripts/verify_dialogue_grounding.py`
- `scripts/verify_dialogue_browser.mjs`
- `scripts/summarize_dialogue_performance.py`

Evidence files: `PAULA_DIALOGUE_ROUTING.json`, `PAULA_DIALOGUE_BEFORE.json`,
`PAULA_DIALOGUE_AFTER.json`, `PAULA_DIALOGUE_AFTER_PROVIDER.json`,
`PAULA_DIALOGUE_PERFORMANCE.json`, `PAULA_DIALOGUE_STARTUP_FINAL.json`,
`PAULA_DIALOGUE_LIVE_CHECKS.json`, `PAULA_DIALOGUE_SESSIONS.json`,
`PAULA_DIALOGUE_GROUNDING.json`, `PAULA_DIALOGUE_BROWSER.json`.

Run management tests/evaluation inside Docker, for example:

```powershell
docker exec paulibot_web python -B manage.py test chatbot.test_dialogue chatbot.test_suggestions chatbot.test_about_spus_ingestion chatbot.test_performance chatbot.test_compound_queries chatbot.test_retrieval_consistency chatbot.test_grounding chatbot.test_intents chatbot.test_web_crawler chatbot.test_enrollment chatbot.test_conversation_context chatbot.test_chat_sessions --keepdb --verbosity 1
docker exec -e HF_HUB_DISABLE_PROGRESS_BARS=1 paulibot_web python -B manage.py shell -c "import runpy;runpy.run_path('scripts/evaluate_dialogue_routing.py',run_name='__main__')"
python -B scripts/verify_dialogue_http.py
```

The browser script requires a dedicated headless Chrome profile with DevTools on
localhost:9339. The temporary profile used for this validation was removed.

## Limits and next evaluation needs

- Social replies have deliberately bounded expressive range. This is not an
  open-domain generative chatbot; unfamiliar casual phrasing can still enter
  the cautious knowledge path.
- MiniLM is not a comprehensive multilingual language-understanding model.
  The sampled Filipino/Taglish cases passing does not establish universal
  dialect, spelling, humor, or code-switching coverage.
- Intent continuity generalizes across knowledge domains. Pending clarification
  metadata currently represents PAULA's existing enrollment/navigation flows;
  a future custom clarification flow needs its own validated state adapter.
- Language preference affects social replies, framing and known UI questions.
  Institutional excerpts retain their stored language and wording.
- Source matching demonstrates extractive preservation in 33 cases. It does
  not prove that institutional sources are complete, current, or universally
  correct. No zero-hallucination guarantee is claimed.
- Naturalness ratings by students/independent reviewers, a larger independently
  annotated corpus, and realistic concurrent deployment testing remain undone.
  The proposed human-rating and broad accuracy objectives are not certified by
  these engineering regression tests.

The web container has already been restarted and all three workers are ready.
Use `npm run dev` for the frontend connected to Docker on port 8080.
