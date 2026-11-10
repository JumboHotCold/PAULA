# PAULA Stage 1 audit — November 9, 2026

**Stage 1 only. Application behavior is unchanged. Stop here until the user replies “continue.”** `CONFIRMED` marks source-backed/reproduced findings; `HYPOTHESIS` marks an unverified cause or proposed next action. Known failing audit tests are reported explicitly, not skipped or presented as passing.

## Checkpoint and actual stack

**CONFIRMED:** pre-audit checkpoint branch `checkpoint/pre-intent-audit-20261109` points to `4dfc0409d7d534b90917b09aa3bac65abd690ac8` (“paula optimization partial”). The original working tree was clean. Reproduction scripts/tests were committed separately as `6ddf7aed79d09b466f2e3c939f1b02197e668b7c`. Nothing was pushed or deployed.

**CONFIRMED:** the expected MySQL/Chroma/BGE-M3/Ollama architecture in the supplied prompt does **not** match this code/runtime. PAULA uses **Django 4.2.10, PostgreSQL/pgvector, 384-dimensional local MiniLM, and conditional Groq/OpenAI/Gemini SDK clients**. Evidence: `paulibot/settings.py:199`, `chatbot/models.py:184`, `chatbot/embedding_runtime.py:12`, `chatbot/logic.py:58`, `artifacts/stage1/audit.json` → `database`/`runtime`. No database or embedding migration was attempted.

**CONFIRMED:** Docker web/PostgreSQL are running; Vite 5173 responds and proxies `/api` to Docker 8080. Three existing workers report compatible models and readiness. Evidence: `frontend/vite.config.js:15`, `docker-compose.yml:105`, `chatbot/readiness.py:56`; actual browser requests in `artifacts/stage1/browser.json`. This is not validation of any unrelated port-8000 process or remote deployment.

## One message, end to end

All paths below are **CONFIRMED** in the named source:

1. Dashboard form or starter/suggestion click calls `App.handleSend`: `frontend/src/components/Dashboard.jsx:194`, `frontend/src/components/Dashboard.jsx:383`, `frontend/src/App.jsx:367`.
2. App appends the user message, constructs bounded history and passes explicit guest/authenticated mode, account/thread identity and signed context token to `sendMessage`: `frontend/src/App.jsx:370`, `frontend/src/api/chatApi.js:65`.
3. `postChat` sends one POST with a 30-second transport/body deadline and no automatic retry; guest transport omits credentials: `frontend/src/api/chatTransport.js:2`, `frontend/src/api/chatApi.js:81`.
4. Vite forwards `/api` to Docker. Django timing, session/security and DRF enter `chat_api`, validate the payload, enforce owner/thread isolation and build bounded intent history: `frontend/vite.config.js:15`, `chatbot/performance.py:117`, `chatbot/views.py:240`.
5. `PauliBotLogic.process_query` normalizes and calls `route_turn`. Recognized social/identity responses use local choices. Other queries proceed to contextual resolution/decomposition and domain adapters: `chatbot/logic.py:260`, `chatbot/dialogue.py:189`, `chatbot/logic.py:334`.
6. Resolution produces standalone retrieval queries; exact enrollment/personnel, exact/equivalent FAQs and hybrid lexical/pgvector search run locally: `chatbot/conversation_context.py:199`, `chatbot/compound_queries.py:175`, `chatbot/rag.py:164`, `chatbot/rag.py:216`, `chatbot/rag.py:287`.
7. Eligible evidence is validated against role/college/year/topic constraints. Multiple candidates may use a provider to select **only evidence IDs**. Raw unsupported model-authored facts cannot become an answer through this selector: `chatbot/grounding.py:96`, `chatbot/logic.py:168`, `chatbot/grounding.py:222`.
8. Stored excerpts are rendered with sources, suggestions are generated, and the view saves only explicitly authenticated conversations. JSON includes per-part/status/context metadata; React appends and renders it: `chatbot/grounding.py:251`, `chatbot/views.py:355`, `chatbot/views.py:389`, `frontend/src/App.jsx:390`, `frontend/src/components/Dashboard.jsx:388`.

## Reproduced cases and failure classification

The live matrix used **15 synthetic public questions × 3 rounds = 45 guest requests**. Every request asserted no chat-history persistence. Full responses/statuses/source metadata are in `artifacts/stage1/audit.json`; privacy-safe timing correlation covers 45/45 request IDs.

| Status | Case | Observed result | Classification / evidence |
| --- | --- | --- | --- |
| CONFIRMED | `ty`, `thankyoui`, `thank you` | 3/3 each routed to gratitude; no retrieval, embeddings, provider calls or SQL | Historical failure is **not currently reproduced**. `chatbot/social_normalization.py:21`, `chatbot/social_normalization.py:36`; audit/metrics artifacts. |
| CONFIRMED | `hi`; `tell me about yourself` separately | 3/3 each works | Local greeting/identity paths: `chatbot/dialogue.py:52`, `chatbot/social_responses.py:58`. |
| CONFIRMED | `hi, tell me about yourself` with/without `?` | 0/3 each; knowledge route and no-match response | **WRONG_INTENT**. Social-wrapper removal accepts only factual/domain/follow-up tails, not the existing identity command. `chatbot/dialogue.py:162`, `chatbot/dialogue.py:177`, `chatbot/dialogue.py:213`. |
| CONFIRMED | `tell me about SPUS and why should i enroll in this institution` | Overview answered, second part declined in all 3 rounds | **BAD_CONTEXT → BAD_RETRIEVAL**. A word-level pronoun substitution makes `why should i enroll in SPUS institution?`. `chatbot/conversation_context.py:322`. |
| CONFIRMED | Same compound message with explicit `at SPUS` | Both supported parts in 3/3 rounds | Correct source exists; not a missing-knowledge or provider-generation failure. `chatbot/query_normalization.py:22`; `artifacts/stage1/retrieval.json`. |
| CONFIRMED | Programs, `why spus?`, ICT Director + CEIT Dean, enrollment clarification, Registrar navigation | All 3/3 for each sampled case | Current controls work. Intermittent failure of these exact FAQs is **not reproduced** by this bounded sample. |
| CONFIRMED | Exact transferee fee in unsupported future year 2037 | No fabricated answer in 3/3 rounds | Correct unsupported-control behavior; this is not a request to invent/add a future fee schedule. `chatbot/grounding.py:113`. |
| CONFIRMED | Two starter clicks in the same browser frame | 2 requests, 2 user messages, 2 answers | **ERROR**, frontend submission race. App has no synchronous in-flight latch; two handlers see the old `isTyping` state. `frontend/src/App.jsx:367`, `frontend/src/components/Dashboard.jsx:383`, `frontend/src/components/PromptGrid.jsx:14`. |
| CONFIRMED | Single form submit / ordinary dispatched double-click | 1 request and answer each | React StrictMode is present, but did not duplicate these cases. `frontend/src/main.jsx:8`, `artifacts/stage1/browser.json`. |
| HYPOTHESIS | This browser race caused every previously reported duplicate | Historical network traces/input events are unavailable | The same-frame reproduction proves a race, not the origin of all past UI duplication. |

**CONFIRMED:** the compound failure persists with no external provider calls. Retrieval of its malformed second query returns `no_match`; the explicit query retrieves FAQ **116**, “Why choose SPUS?”. FAQ **98** also contains a combined why-choose source. Both are present in the actual PostgreSQL catalog. Raw nearest rows can pass cosine distance yet fail the lexical/intent guard; loosening the cutoff would not repair the malformed referent. `artifacts/stage1/retrieval.json`, `chatbot/grounding.py:195`, `chatbot/rag.py:347`.

**CONFIRMED:** directly calling `RAGSearcher.retrieve('why spus?')` in the diagnostic script is not the full application route: `process_query` first performs source-backed short-query completion. The live `why spus?` control passes. This audit does not mislabel the deliberately lower-level probe as an additional user-facing regression. References: `chatbot/logic.py:377`, `chatbot/rag.py:30`, `chatbot/query_understanding.py:34`.

## Repeated/conflicting interpretation and coarse error handling

| Status | Finding | Source |
| --- | --- | --- |
| CONFIRMED | `normalize_query` typo/whitespace normalization, `normalized_text` NFKC/casefold/token cleanup, `canonical_text` aliases, `faq_question_key` FAQ grammar and grounding `terms` are distinct transformations. The route and knowledge path normalize again; not every call uses one shared representation. | `chatbot/intents.py:83`, `chatbot/query_normalization.py:17`, `chatbot/query_normalization.py:22`, `chatbot/query_normalization.py:37`, `chatbot/grounding.py:72`, `chatbot/logic.py:336` |
| CONFIRMED | FAST phrase regexes, social forms/abbreviations, semantic exemplars and social reply/persona text are Python constants in separate modules. The current router's whole-utterance safeguards reduce false matches, but the config-driven single pipeline requested for Stage 2 does not yet exist. | `chatbot/dialogue.py:13`, `chatbot/dialogue.py:52`, `chatbot/social_normalization.py:14`, `chatbot/social_responses.py:4` |
| CONFIRMED | Semantic social-classifier exceptions fall through without a diagnostic event; worker preparation also catches arbitrary exceptions and leaves readiness false. These are observability gaps, not failures induced in the live worker for this audit. | `chatbot/dialogue.py:240`, `chatbot/readiness.py:40` |
| CONFIRMED | RAG catches arbitrary errors into `unavailable`; outer knowledge handling also catches broadly. Provider failures have internal outcomes/cooldowns, but schema-invalid responses are not a distinct provider circuit state. | `chatbot/rag.py:160`, `chatbot/logic.py:478`, `chatbot/providers.py:148`, `chatbot/logic.py:191` |
| CONFIRMED | Failures do not all map to one response: current code distinguishes clarification, no-match, unavailable, conflict/ambiguous, selection rejection and view-level safe errors. However, no-match still asks to rephrase and the requested full failure taxonomy is absent. | `chatbot/logic.py:88`, `chatbot/logic.py:435`, `chatbot/logic.py:460`, `chatbot/api_errors.py:18` |
| HYPOTHESIS | These overlapping normalizers explain every historical intermittent FAQ refusal | They explain the reproduced cases, but broader attribution needs the Stage 3 labeled/golden set and any additional exact failing queries. |

## Git provenance

**CONFIRMED:** `git blame` attributes the incomplete social-wrapper checks to **4dfc040** (November 8). The earlier **d8947c6** implementation used narrowly formatted social matches and did not include current abbreviation/typo matching. This supports the historical `ty`/`thankyoui` mechanism, while live testing confirms it is fixed in this checkout. Sources: historical `chatbot/logic.py:237`, current `chatbot/social_normalization.py:21`.

**CONFIRMED:** the word-level `PRONOUN.sub` behavior is attributed to **d8947c6** (October 28), and the unlatched App send entry to **3d201a83** (April 3), with later surrounding edits. These are older retained weaknesses, not proof that the newest optimization introduced every failure. References: current `chatbot/conversation_context.py:322`, `frontend/src/App.jsx:367`.

**HYPOTHESIS:** commit-level causal attribution beyond those inspected lines. The November commit bundles many changes; this audit did not bisect/run every historical full environment or database snapshot. Current failing tests and a pre-audit checkpoint now make targeted future changes reviewable.

## PostgreSQL knowledge/index checks

**CONFIRMED:** active counts are **138 FAQ / 12 StaffMember / 6 Location / 476 WebResource = 632 vectors**. Every stored vector is present, finite, nonzero and dimension 384; all embedding columns are `vector(384)`. All **138 FAQ self-matches** pass and exact normalized FAQ conflicts are zero. Evidence: `artifacts/stage1/audit.json` → `database`, `chatbot/knowledge_audit.py:12`. The two why-choose records are not treated as an exact conflict because their normalized question subjects differ.

**CONFIRMED:** source IDs and vectors live in the same PostgreSQL rows. There is no separate Chroma collection to compare against MySQL; primary keys are scoped by record type. The relevant check is row/vector coverage plus source-type identity, not comparing two unrelated engines. References: `chatbot/models.py:184`, `chatbot/models.py:202`, `chatbot/models.py:239`, `chatbot/models.py:262`, `chatbot/rag.py:341`.

**CONFIRMED:** vector retrieval uses raw cosine **distance**, ascending order, with a maximum distance **.45** applied before ranking adjustments. This corresponds to a similarity lower bound of .55, not 45% confidence. Lexical candidate expansion also remains subject to the semantic cutoff and evidence gates. References: `chatbot/rag.py:305`, `chatbot/grounding.py:199`, `chatbot/grounding.py:210`.

**CONFIRMED:** the explicitly loaded cached query model returned 384 dimensions. Its standalone audit-process initialization took **35.91 seconds**, separate from all warm HTTP timings. The pinned query revision is `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. References: `chatbot/embedding_runtime.py:29`, `artifacts/stage1/retrieval.json`.

**CONFIRMED:** the current model definitions do not persist the historical encoder/revision per vector. Shape and current ingestion/query code establish structural compatibility, not provenance for every prior embedding. **HYPOTHESIS:** any particular vector came from a different historical encoder; no evidence justified a bulk rebuild. No indexing/backfill was performed.

**CONFIRMED:** full before/after fingerprints match for FAQ, StaffMember, WebResource, Location, Conversation and ChatHistory. No historical or institutional data changed during the audit, including after the browser guest tests. Evidence: `artifacts/stage1/audit.json` → `integrity`; `scripts/audit_stage1.py:46`.

## Topics the university must add to the knowledge base

**CONFIRMED:** **no new institutional topic is required to fix the reproduced failures**. Why-choose content exists; greeting/identity belongs in the persona/intent layer, not additional FAQ variants; duplicate submissions are a frontend issue. Adding rows for each failing wording would conceal the defects.

**CONFIRMED:** the 2037 fee question is an intentionally unsupported future-specific control. Do not create a fictional schedule for it. The safe absence of an answer is desirable.

**HYPOTHESIS:** other real FAQ topics are missing. This Stage 1 catalog and 45-case matrix do not establish comprehensive current-year coverage of fees, calendars, scholarship deadlines, every personnel roster or all office procedures. Specific failed questions and approved office sources are needed before declaring those facts absent, importing data or recommending new content. The catalog in `artifacts/stage1/audit.json` is available for that review; the supplementary CSVs were not ingested.

## Actual tests and baseline measurements

| Status | Executed check | Result |
| --- | --- | --- |
| CONFIRMED | Existing `manage.py test chatbot --keepdb --verbosity 0` | **409 passed**, 2.989 s test execution |
| CONFIRMED | Existing frontend `npm test` | **24 passed** |
| CONFIRMED | Explicit `manage.py test chatbot.audit_stage1_reproductions` | **7 tests: 3 pass, 4 intentionally fail on current defects** |
| CONFIRMED | Isolated browser regression script | Single-submit/ordinary-double-click assertions pass; same-frame duplicate assertion **fails: 2 requests instead of 1** |
| CONFIRMED | Live synthetic guest matrix | **36/45 pass**; the 9 failures are three input variants repeated three times, not nine independent root causes |
| CONFIRMED | Synthetic provider faults | **8/8** preserve gated stored evidence; no real credentials were invalidated or external fault induced |
| CONFIRMED | Active knowledge audit | 632 valid vectors, 138/138 exact FAQ self-matches, zero exact normalized FAQ conflicts |

**CONFIRMED:** the red audit module is explicitly invoked and kept separate from default discovery while fixes await approval. The existing 409-test green result does not include those known-failing assertions. Source: `chatbot/audit_stage1_reproductions.py:1`. CI was not changed in Stage 1.

| Status | HTTP query, 3 samples each | p50 / nearest-rank p95 ms |
| --- | --- | ---: |
| CONFIRMED | `ty` | 3.93 / 127.98 |
| CONFIRMED | `thankyoui` | 3.92 / 98.44 |
| CONFIRMED | `thank you` | 2.63 / 4.04 |
| CONFIRMED | Standalone introduction | 37.58 / 130.55 |
| CONFIRMED | Greeting + introduction, no final `?` — currently wrong | 746.90 / 1,146.60 |
| CONFIRMED | Compound with “this institution” — partial | 194.42 / 215.88 |
| CONFIRMED | Equivalent explicit `at SPUS` compound — supported | 79.06 / 87.67 |
| CONFIRMED | Programs FAQ | 76.20 / 156.11 |
| CONFIRMED | ICT Director + CEIT Dean | 339.11 / 439.68 |

**CONFIRMED:** all 45 matched HTTP traces contain **zero provider calls**; recognized gratitude uses zero SQL and query embeddings. Failed identity wrappers unnecessarily invoke both local semantic social matching and knowledge retrieval. Aggregate stage p50/p95: normalization **.821/4.654 ms**; context resolution **.309/4.737 ms**; retrieval **75.337/294.730 ms**; grounding **12.810/38.023 ms**; source rendering **.045/.453 ms**; suggestions **45.076/68.183 ms**. Stage observations are conditional and inclusive, not additive wall-clock pieces. Evidence: `artifacts/stage1/metrics.json`.

**CONFIRMED:** these are small sequential baseline measurements on an already-ready development runtime, not before/after improvements, concurrency capacity, full intent accuracy, or FAQ top-1/top-3 recall. The requested 200 social/100 institutional labeled corpus and golden paraphrase set belong to Stage 3 and have not been built or claimed as validated here.

## Provider supplement and Stage 2 boundary

**CONFIRMED:** [the provider audit](PAULA_PROVIDER_AUDIT.md) lists every inspected Groq/OpenAI request site, role, model, temperature, timeout, retry/cooldown, key loading, fallback and user-visible failure behavior. It also flags the disabled deprecated OpenAI model and inactive retired Gemini fallback using official documentation. The observed 9 HTTP failures cannot be attributed to an external model call, because none occurred in those traces.

**HYPOTHESIS / proposed next changes:** centralize matching representations/config-driven persona/exemplars without rewriting factual queries; fix social-wrapper composition and full referring-noun-phrase binding; add a synchronous send guard; improve safe failure diagnostics; preserve exact/hybrid lookup, authorization and source extraction. Calibration and broader measured claims require the later labeled corpus. No threshold, model or provider change is justified by the Stage 1 evidence alone.

**CONFIRMED — readiness decision:** **NO-GO on declaring the reported behaviors stabilized**: the explicit red tests and duplicate race remain open by design. No deployment was performed. Stop after this report and wait for **“continue”** before Stage 2 implementation.

## New files and repeatable commands

**CONFIRMED:** Stage 1 adds only audit/reproduction code, reports and evidence artifacts:

* `chatbot/audit_stage1_reproductions.py`
* `scripts/audit_stage1.py`
* `scripts/audit_stage1_browser.mjs`
* `scripts/audit_stage1_retrieval.py`
* `scripts/audit_stage1_metrics.py`
* `PAULA_STAGE1_AUDIT.md`, `PAULA_PROVIDER_AUDIT.md`
* `artifacts/stage1/audit.json`, `browser.json`, `retrieval.json`, `metrics.json`, `google_model_lifecycle.json`

```powershell
# Existing green baseline; controlled PostgreSQL fixtures only
docker exec paulibot_web python -B manage.py test chatbot --keepdb --verbosity 0

# Explicit red reproductions: expected exit 1 until Stage 2 fixes
docker exec paulibot_web python -B manage.py test chatbot.audit_stage1_reproductions --keepdb --verbosity 1
node scripts/audit_stage1_browser.mjs

# Live guest-only audit; requires existing Docker/Vite, may use configured RAG providers
docker exec paulibot_web python -B manage.py shell -c "import runpy; runpy.run_path('scripts/audit_stage1.py')"

# Read-only vector/gate inspection; explicitly loads one local cached model
docker exec paulibot_web python -B manage.py shell -c "import runpy; runpy.run_path('scripts/audit_stage1_retrieval.py')"
python -B scripts/audit_stage1_metrics.py
```
