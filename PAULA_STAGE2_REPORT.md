# PAULA Stage 2 implementation report

**November 9, 2026 — Stage 2 only.** `CONFIRMED` identifies executed tests, source inspection or recorded measurements. Limitations and proposed future work are explicitly distinguished. No deployment, model/provider replacement, threshold calibration or Stage 3 evaluation corpus was undertaken.

## Result and commit order

**CONFIRMED:** all three reported defects were reproduced before fixing, implemented in the requested order, and committed separately. The full backend and frontend suites ran after each commit. The original Stage 1 red cases now participate in ordinary backend discovery through `chatbot/test_stage2_original_reproductions.py`.

| Change | Commit | Post-commit backend / frontend result |
| --- | --- | --- |
| (a) Greeting + identity/capability composition | `1bd1de2` | **412 / 24 passed** |
| (b) Complete institutional referring-noun phrases | `29de400` | **417 / 24 passed** |
| (c) Synchronous frontend send guard | `b30b5d0` | **417 / 27 passed** |
| Optional config and matching-view centralization | `40206a5` | **422 / 27 passed** |
| Build/revision visibility | `016b617` | **429 / 27 passed** |
| Diagnostics, rehearsal opt-in and original-test promotion | `02ff808` | **442 / 27 passed** |
| Committed live-verification tools | `ce72314` | **442 / 27 passed** |

Evidence: `artifacts/stage2/commit_checks.json`. The pre-Stage-2 rollback branch is `checkpoint/pre-stage2-20261109`, pointing to `ce9a449`. Additional report/evidence changes do not alter runtime source; the readiness endpoint exposes the revision actually loaded by its workers, rather than following later Git commits dynamically.

## Confirmed fixes

### (a) Composed self-introduction and capabilities

**CONFIRMED:** `hi, tell me about yourself`, its `?` variant, and greeting-wrapped capability commands now reuse the existing deterministic self intents. Social-edge extraction recognizes a complete local identity/capability command as a valid tail. Extra institutional clauses still route through knowledge retrieval, so a greeting cannot discard an enrollment constraint or personnel question. Greeting acknowledgements reuse existing framing, without repeating an existing `Hi!` prefix.

Sources: `chatbot/dialogue.py:115`, `chatbot/dialogue.py:124`, `chatbot/logic.py` → `_social_reply`; tests `chatbot/test_stage2_composition.py`. The fix adds no university facts or provider calls.

### (b) Full referring-noun-phrase binding

**CONFIRMED:** `this/that/the same institution`, `school`, `university`, and `campus` are treated as complete spans. With a unique prior SPUS subject, “why should I enroll in this institution” resolves to an explicit SPUS enrollment-rationale query, using the same grammatical connector as its named equivalent. The resolver never hardcodes an answer or a personnel/FAQ record ID.

**CONFIRMED:** other predicates and future named subjects are covered. Dates and exclusions remain in attribute queries. Missing, coordinated/ambiguous, or known incompatible antecedents such as a Registrar office cause clarification instead of silently turning that office into a university. Explicit new institutions retain their own names. Sources: `chatbot/compound_queries.py:25`, `chatbot/compound_queries.py:31`, `chatbot/conversation_context.py:186`; tests `chatbot/test_stage2_references.py` and the original Stage 1 cases.

**Limitation:** this remains bounded grammatical/entity resolution, not unrestricted multilingual coreference. An ambiguous reference is deliberately clarified. Broader held-out language evaluation remains Stage 3 work.

### (c) Duplicate-send race

**CONFIRMED:** App acquires a synchronous guard **before** appending a user message or starting the request. React `isTyping` remains presentation state; it is not relied on as the lock. The guard is scoped to the existing chat/account epoch. An old request's completion cannot release a newer epoch's lock. `finally` releases the correct request after success or failure, without automatic retry.

Sources: `frontend/src/App.jsx:372`, `frontend/src/App.jsx:420`, `frontend/src/sendGuard.js:2`. Before: two same-frame starter activations produced **2 requests / 2 questions / 2 answers**. After: **1 / 1 / 1**. Single submit and ordinary double-click also remain **1 / 1 / 1**. Evidence: frozen `artifacts/stage1/browser.json` and separate `artifacts/stage2/browser_after.json`.

**Limitation:** this is browser-component request protection, not distributed server-side idempotency for arbitrary clients or intentional submissions from different tabs.

## Low-risk configuration and normalization scope

**CONFIRMED:** persona/reply text, local recognition patterns, social forms/abbreviations, semantic exemplars and friendly framing now have one backend configuration source: `chatbot/config/conversation.json`. They were mechanically copied from the existing Python constants. A migration-contract test checks the complete pre-migration content hash, including every existing reply, regex and exemplar. No new intent phrases, model, threshold or knowledge facts were added during this move.

**CONFIRMED:** `chatbot/conversation_config.py:11` validates required intents, languages, patterns and exemplar shapes. Invalid configuration fails explicitly; it does not silently substitute an unrelated persona. Loaded data is cached once and recursively immutable. Config edits require tests and worker reload. The unused frontend guest-greeting constant was removed; the active assistant response persona comes from this backend config.

**CONFIRMED:** `chatbot/query_normalization.py:26` provides one immutable matching representation with original, spaced, squashed and punctuation-aware forms. The spaced form retains the existing NFKC/casefold/token normalization semantics; the original text is retained unchanged in the representation. The punctuation-aware form preserves grammatical apostrophes such as “What's your name?”. Retrieval keys and original factual constraints were not rewritten into social-match text.

Tests: `chatbot/test_stage2_config.py`, existing identity/social/grounding suites. During implementation, tests caught an apostrophe regression and a typed-attribute duplicate-subject issue; both were corrected before their commits. No final test failures are concealed. Aggressive repeated-character normalization across factual queries was deliberately not introduced.

## Build/version stamp

**CONFIRMED:** `/api/health/live` and `/api/health/ready` expose:

* `build_commit`: full Git revision captured by the worker;
* `build_source`: `git`, `environment`, or explicit `unknown`;
* `build_source_digest`: normalized backend Python/config/template source digest;
* readiness also includes per-worker stamps and `build_consistent`.

**CONFIRMED:** the snapshot is cached at worker startup, included in startup logs and request timing records, and does not change just because someone commits newer files while an old process remains loaded. Local Git metadata is read without requiring a Git executable. A development bind mount takes precedence over an older baked image stamp. Clean images can receive the full revision through Docker's `PAULA_BUILD_COMMIT` build argument; `.git` remains excluded from the image.

Sources: `chatbot/build_info.py:57`, `chatbot/readiness.py:30`, `chatbot/readiness.py:75`, `chatbot/views.py` → `health_live`, `chatbot/performance.py:18`, `Dockerfile`, `docker-compose.yml`.

**CONFIRMED:** the measured live matrix ran on commit `ce723145803c3f7d7fccbf3fb8dc52ba7886a3fc`. All three workers reported the same commit and backend digest `93becd8b26f6732c0dfdb7286866454a297b56f703770282979a237f82fe13b8`; `build_consistent=true`. Evidence: `artifacts/stage2/readiness.json` and `artifacts/stage2/live/readiness.json`. After report commits, a reload and revision check are required to make the running commit match the newer HEAD even though backend source is unchanged.

**Limitations:** a commit stamp alone does not certify uncommitted edits, environment variables, database freshness or the separately served frontend bundle. Compare the source digest and clean source tree as well. Unknown metadata is reported as unknown; model/database readiness is not falsely described as version verification. The clean-image build-argument path has unit coverage but a new production image was not built or deployed here.

Example verification in PowerShell:

```powershell
$expected = (git rev-parse HEAD).Trim()
$ready = Invoke-RestMethod http://127.0.0.1:8080/api/health/ready
$ready | Select-Object ready, build_commit, build_source_digest, build_consistent
$ready.workers | Select-Object worker, build_commit, build_source_digest
if ($ready.build_commit -ne $expected -or -not $ready.build_consistent) {
    throw 'The running workers do not match the expected revision.'
}
```

## Privacy-safe diagnostics and rehearsal flag

**CONFIRMED:** distinct structured reasons now include `CLASSIFIER_ERROR`, `RETRIEVAL_ERROR`, `DB_ERROR`, `NO_MATCH`, `KNOWLEDGE_PIPELINE_ERROR`, and `WORKER_PREPARATION_ERROR`. Answer outcomes also distinguish `UNCLEAR_INTENT`, `RETRIEVAL_UNAVAILABLE`, `SOURCE_CONFLICT`, `AMBIGUOUS_EVIDENCE`, `VALIDATION_REJECTED`, `PARTIAL_ANSWER`, and `UNRESOLVED_PARTS`.

**CONFIRMED:** normal diagnostics include request/worker/build correlation, stage, reason and bounded status/count metadata. They exclude submitted text, history, source/answer text, SQL, identities, cookies and context tokens. A no-match outcome is not counted as a server exception and is not asserted to prove that the physical database contains no related fact. User-facing fallback behavior and grounded provider degradation remain intact.

Sources: `chatbot/dialogue.py:210`, `chatbot/rag.py:160`, `chatbot/logic.py:481`, `chatbot/performance.py:104`, `chatbot/diagnostics.py:15`, `chatbot/views.py:345`.

**CONFIRMED:** `PAULA_LOG_UNANSWERED_QUERIES=false` is the default and remained disabled in the live checks. Only explicitly enabling it writes bounded unanswered message text to the separate `paula.rehearsal` logger. That event contains the submitted query, reason and request ID; it does not include conversation history, identity or answers. JSON encoding prevents newline log injection. The event is not emitted for answered social turns.

**CONFIRMED:** tests with the flag enabled and an authenticated test user explicitly in guest mode create **zero Conversation / ChatHistory records**. The live default-mode audit likewise preserves existing records. Opting in affects operational logging, never the guest chat-history persistence rule.

**Important operational distinction:** when enabled, query text **is retained in Docker/host logs** according to their retention policy. It is not automatically anonymized. Use synthetic rehearsal inputs, protect those logs, and turn the flag off afterwards. Normal production/student use should retain the default `false`.

To enable/disable deliberately, set the process variable and recreate only the development web service using the existing launcher and existing private environment file:

```powershell
$env:PAULA_LOG_UNANSWERED_QUERIES = 'true'
.\scripts\start_workspace_backend.ps1 -EnvFile '<existing environment file>'
# Run synthetic rehearsal inputs only.
$env:PAULA_LOG_UNANSWERED_QUERIES = 'false'
.\scripts\start_workspace_backend.ps1 -EnvFile '<existing environment file>'
```

Changing an environment variable followed by `docker restart` alone does not update an existing container's environment. The flag was tested with isolated settings/fixtures; it was not enabled on the shared live service during this task.

## Before/after validation

| CONFIRMED check | Before | After |
| --- | --- | --- |
| Default backend regression suite | 409 pass | **442 pass**: 26 new tests plus 7 promoted original audit tests |
| Frontend Node suite | 24 pass | **27 pass** |
| Explicit original Stage 1 backend suite | 3 pass / 4 fail | **7/7 pass**, included in default discovery |
| Original live matrix, identical 15 cases × 3 rounds | 36/45 pass | **45/45 pass** |
| Expanded bounded live matrix | Not run in Stage 1 | **60/60 pass** |
| Same-frame starter race | 2 submissions/answers | **1 submission/answer** |
| Matched timing traces | 45/45 | **60/60**, zero external provider calls |
| Query text in normal-mode matched logs | No deliberate text logging | **None**, flag remains false |
| Knowledge audit | 632 valid vectors; 138/138 FAQ self-matches | **Unchanged**, strict audit passes |
| Schema checks | Existing schema | **No migration drift or pending migration** |
| Production frontend bundle | Existing bundle | **Build passes**; existing large-chunk/Node warnings remain |

**CONFIRMED:** tests cover social/institutional false-positive boundaries, full reference spans, constraints and ambiguity, config integrity and immutability, stale/mixed build metadata, synchronous send ownership, error redaction and opt-in guest privacy. They retain the existing context, navigation, compound retrieval, auth isolation, suggestion and provider safeguards. New test files are listed below.

Measured sequential warm HTTP timings, **three samples per query**, nearest-rank p95:

| Query | Before p50 / p95 ms | After p50 / p95 ms |
| --- | ---: | ---: |
| `hi, tell me about yourself` | 746.90 / 1,146.60 — wrong answer | **31.41 / 44.22** — identity |
| Same introduction with `?` | 165.23 / 170.61 — wrong answer | **32.37 / 88.87** — identity |
| Overview + enroll in “this institution” | 194.42 / 215.88 — partial | **100.37 / 130.57** — both supported |
| `ty` | 3.93 / 127.98 | **3.28 / 10.04** |
| `thankyoui` | 3.92 / 98.44 | **4.62 / 11.85** |
| Programs FAQ | 76.20 / 156.11 | **79.26 / 81.67** |

**CONFIRMED:** the greeting+identity fix removes knowledge-query embeddings from that path; identity suggestions still perform one public FAQ lookup. The institution-reference compound now uses supported exact retrieval instead of the malformed semantic attempt. Unchanged paths exhibit sampling variation; not every p50 improved. These observations support the specific path fixes, not general latency or accuracy guarantees. Evidence: `artifacts/stage2/comparison.json`.

**CONFIRMED:** first activation-to-three-worker readiness was **55.67 s**, with worker initialization around **34.36–34.59 s**. This is a readiness validation measurement, not a claimed cold-start optimization. The existing MiniLM model/cache architecture was preserved. Remote CI, target-host capacity, broad multilingual accuracy and the Stage 3 labeled/golden corpus were not executed. A long interruption initially put the completed samples outside the summarizer's relative two-hour log window; using their recorded absolute timestamps recovered all 60 traces without changing the application or benchmark results.

## Data integrity and unchanged boundaries

**CONFIRMED:** `artifacts/stage2/integrity.json` shows identical before/after full-row fingerprints for FAQ, StaffMember, Location, WebResource, Conversation and ChatHistory, including stored vectors. Counts remain **138 FAQ, 12 staff, 6 locations, 476 web resources, 140 conversations and 177 saved messages**. No ingestion, re-embedding, source correction, historical deletion/reassignment, replacement application account, or database-volume operation was performed. New test accounts/data exist only in Django's isolated PostgreSQL test database.

**CONFIRMED:** the .45 cutoff, models/providers, vector dimensions/revision, grounding rules, ORM models and dependencies are unchanged. `chatbot/providers.py`, `chatbot/embedding_runtime.py`, `chatbot/grounding.py`, `chatbot/models.py` and `requirements.txt` have no diff from the Stage 1 checkpoint. The RAG change adds diagnostic events only. No extra model/API request was introduced by diagnostics or build stamps.

## Disabled/retired paths for a separate decision

**CONFIRMED from the Stage 1 provider audit and unchanged source:**

* **OpenAI `gpt-4o-mini`:** disabled in the current runtime; marked deprecated in the checked official documentation, with listed snapshot shutdown January 14, 2027. It was not activated, replaced or tested against account credits/access.
* **Gemini `gemini-1.5-flash`:** retired September 29, 2025; conditional chat fallback remains inactive because its configured key is a placeholder. It was not changed or enabled.
* **Manual Gemini `gemini-2.5-flash` OCR/cleanup:** separate ingestion commands retain their existing behavior and were not run.

See [the provider audit](PAULA_PROVIDER_AUDIT.md) for the official lifecycle citations and call sites. Groq remains `openai/gpt-oss-20b`; institutional responses remain source-extractive. A fallback migration, supported-Django upgrade and public deployment are separate decisions.

## Files changed

**CONFIRMED — runtime and configuration:**

* `chatbot/dialogue.py`, `chatbot/logic.py`: composition and diagnostic hooks.
* `chatbot/compound_queries.py`, `chatbot/conversation_context.py`: full reference binding and conservative antecedent checks.
* `frontend/src/App.jsx`, `frontend/src/sendGuard.js`: synchronous request guard and unused persona constant removal.
* `chatbot/config/conversation.json`, `chatbot/conversation_config.py`, `chatbot/social_normalization.py`, `chatbot/social_responses.py`, `chatbot/response_style.py`, `chatbot/query_normalization.py`: shared conversation data and matching views.
* `chatbot/build_info.py`, `chatbot/readiness.py`, `chatbot/performance.py`, `chatbot/views.py`: build visibility, startup/request correlation and answer observation.
* `chatbot/diagnostics.py`, `chatbot/rag.py`: safe outcome/error reasons and explicit rehearsal logging.
* `paulibot/settings.py`, `.env.example`, `Dockerfile`, `docker-compose.yml`: new metadata/diagnostic settings and build-argument wiring; model/database/provider settings retain their values.

**CONFIRMED — tests and verification:**

* `chatbot/test_stage2_composition.py`, `test_stage2_references.py`, `test_stage2_config.py`, `test_stage2_build.py`, `test_stage2_diagnostics.py`, `test_stage2_original_reproductions.py`.
* `frontend/src/sendGuard.test.mjs`.
* `scripts/audit_stage1.py`, `scripts/audit_stage1_browser.mjs`: additive audit-case/output support; frozen Stage 1 evidence remains preserved.
* `scripts/verify_stage2.py`, `scripts/summarize_stage2.py`.
* This report and `artifacts/stage2/`: per-commit results, live results, browser result, readiness, comparison and data-integrity evidence.

## Stop point

**CONFIRMED:** the three reported defects and the authorized Stage 2 additions pass the available validation. This is a local regression result, not certification of every possible query or public deployment readiness. **Stage 2 stops here.** No Stage 3 corpus/calibration, new fallback/model selection or deployment will proceed without the next instruction.
