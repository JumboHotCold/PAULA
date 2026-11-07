# PAULA MVP reliability stabilization

**Audit and local validation: November 7–8, 2026.** The tested development runtime is active on Docker port 8080 with three prepared semantic workers. This is a completed local stabilization pass, **not public deployment approval or a claim that every possible question is reliable**. No framework upgrade or remote deployment was performed.

## Recommendation and release decision

**Conditional GO for rehearsing the local defense demonstration**, using the prepared runtime, current knowledge snapshot and operational checks. **NO-GO for public production deployment** until a supported-framework build and target-host release checks pass. Django 4.2.10 remains installed and its release series stopped receiving fixes on April 7, 2026. Recommended next step: a separately tested Django 5.2 LTS candidate, which has extended support through April 2028. [Official Django support table](https://www.djangoproject.com/download/), [separate upgrade scope](PAULA_DJANGO_LTS_UPGRADE_PLAN.md).

The user's question about the safest approach was treated as a request for a recommendation, not authorization to upgrade the running framework. Stabilization and compatibility migration are kept separate so their effects can be measured and rolled back independently.

## Actual execution path and confirmed causes

React Dashboard → App → chat transport → Vite `/api` proxy → Docker Django middleware → `views.chat_api` identity/thread/context validation → `PauliBotLogic.process_query` → deterministic social routing or knowledge processing → bounded contextual resolution/decomposition → structured lookup/exact FAQ/hybrid pgvector retrieval → evidence eligibility → optional evidence-ID selector → source extracts → suggestions → explicit authenticated persistence → JSON → React rendering. Conversation text supplies intent only; prior assistant answers do not become institutional evidence. The unchanged cosine-distance cutoff is **0.45**.

| Confirmed defect | Evidence and resolution |
| --- | --- |
| Regression tests were not reliably discoverable | Standard `manage.py test chatbot` produced **17 relative-import errors across 22 entries**. Missing `chatbot/__init__.py` caused tests to load outside their package. It now discovers and passes **409 tests**; a single verification script and CI workflow use this command. |
| Tested source was absent from the original Git release | Core dialogue/runtime/retrieval/test/frontend files were new/untracked. Deploying the original HEAD omits them. A local source checkpoint was made **before application edits**, and a final local candidate captures selected required source and assets. Nothing was pushed. See `PAULA_MVP_CHECKPOINT.json` and `PAULA_MVP_RELEASE.json`. |
| A broad personnel guard rejected policy documents | Any faculty mention could require a named roster. Four active handbook FAQ records failed even when queried by their own stored question. Shared `faculty_identity_request` separates roster requests from policy mentions. Exact self-matches are now **138/138**, up from **134/138**. |
| Index maintenance occurred inside semantic chat requests | `_hybrid_search` invoked `ensure_embeddings`, scanning four tables and potentially encoding/writing every missing vector during a user request. This duplicated work across workers and coupled chat availability to unrelated maintenance. Interactive retrieval is now read-only; admin saves index their own record, and explicit maintenance fills missing vectors only. |
| Partial updates could retain stale embeddings | `save(update_fields=...)` cleared the Python attribute but omitted the embedding column from the database update. Web category changes were also omitted from invalidation despite being embedding input. A shared save helper invalidates exactly the persisted text fields; maintenance uses compare-and-set updates to avoid attaching an old vector to concurrently edited text. |
| Filipino attribute grammar differed from follow-up grammar | `Ano naman ang requirements?` recognized continuity but missed the attribute rule, attempted an unnecessary provider edit, and clarified despite a clear transferee context. Shared attribute-prefix parsing now binds requirements/fees/deadlines/etc. to prior subjects across domains. It does not add institutional facts or an enrollment-only exception. |
| Failures were leaked or mislabeled | API catch-all handlers returned exception strings; React called every non-401 failure a network error. Safe typed errors and request IDs now distinguish input, server, storage and navigation failures. Successful responses add `answer_status`; an explicit evidence-selector veto is `selection_rejected`, preserving the veto instead of claiming the KB is empty. |
| Readiness and packaging allowed environment drift | Readiness checked only workers/models; settings silently fell back to SQLite; Docker lacked an ignore file; the standalone Docker CMD omitted model-readiness hooks. Readiness now checks PostgreSQL and public knowledge counts. Missing vectors remain visible without disabling exact FAQs. PostgreSQL is required, packaging excludes local secrets/dependencies/runtime data, and the Docker CMD uses the same Gunicorn hooks. |
| Deployment was not repeatable enough | Several direct dependencies were unpinned, a fresh cache had no explicit preparation command, and the legacy seed could overwrite reviewed facts. Dependencies now pin the **already installed** versions, cache preparation is explicit, and legacy seeding refuses a nonempty knowledge database. Fresh-image and remote-CI validation remain pending. |

The corpus was **not missing all embeddings**: all 632 were already present and structurally valid before these changes. Removing request-time indexing fixes a confirmed lifecycle defect; it is not evidence that a bulk embedding rebuild was needed. No embeddings were regenerated in the active database.

## Database, source and regression validation

Active database: PostgreSQL **15.4**, pgvector extension **0.5.1**. Counts: **138 FAQs, 12 staff, 6 locations, 476 web resources**. All four embedding columns are `vector(384)` with zero missing, nonfinite, invalid-dimension or zero vectors. Exact normalized FAQ conflicts: **0**. The model remains MiniLM `all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.

Before/after hashes match for **StaffMember, FAQ, WebResource, Conversation and ChatHistory**, including their stored values and vectors. Historical counts remain **140 conversations / 177 messages**. Location count/vector checks also remain valid; the original hash helper did not include Location, so this report does not claim a before/after Location content hash. No active facts, accounts or history were deleted, reassigned or reseeded. Test inserts/deletes occur only in Django's separate PostgreSQL test database.

| Check executed | Result |
| --- | --- |
| Full default Django discovery through Docker PostgreSQL | **409 passed**, final verification run **4.281 s** test execution; 28 new backend tests in four MVP files |
| Frontend Node suite | **24 passed**; 3 new transport tests |
| Django checks, migration drift and pending migration checks | Passed; **no schema change** introduced |
| Strict active knowledge audit / default index dry run | Passed; 632 valid vectors, 138/138 FAQ self-matches, zero missing/conflicting equivalent FAQs |
| Cached model availability / installed dependency consistency | Passed; `pip check`: no broken requirements |
| React production build | Passed; large-chunk and local Node deprecation warnings remain |
| Identical live guest matrix, 28 cases × 3 rounds | **81/84 before → 84/84 after**; each turn checks no history persistence |
| Isolated production-policy Gunicorn | **8/8 checks passed**, DEBUG=false, HTTPS proxy headers, secure CSRF cookie, real PostgreSQL, cached MiniLM, **all three provider keys cleared** |
| Live Groq selector probe | `openai/gpt-oss-20b` succeeded; expected fixture selection; **1,513.51 ms** total / **1,476.41 ms** provider time |
| Three-worker activation and first semantic requests | All three workers ready/observed; first semantic requests **378–380 ms** after readiness |
| CI Compose configuration syntax | Passed; GitHub Actions run and clean image build **not yet executed** |

The isolated WSGI smoke checks database/index readiness, secure headers/cookies, grounded FAQ/compound/semantic answers without providers, Unfold CSS, admin login rendering, unsupported-request abstention, safe malformed-input handling and HTTP→HTTPS redirect. It is not a cloud deployment, real TLS certificate test or browser login/cross-site-cookie test.

Failure injection covers database/model/provider outages, deadlines, explicit selector rejection, missing/zero/conflicting knowledge, malformed payloads and navigation failures. Existing suites retain authentication isolation, guest switching, owner/thread-bound context, multi-intent queries, suggestions, typography/typo controls, enrollment, source conflicts and other domains. During incremental validation, six context assertions caught an introduced English-prefix/capitalization regression; it was corrected before the final 409-test pass. No final test failures are being hidden.

## Measured performance

Identical synthetic guest inputs against warm Docker workers, sequential requests, three rounds. p95 is nearest rank; the small groups are not statistically representative of production traffic. Hardware/cache/provider/network variation affects these numbers; they are observed comparisons, not universal speed guarantees.

| Request group | Samples per phase | Before p50 / p95 (ms) | After p50 / p95 (ms) |
| --- | ---: | ---: | ---: |
| Knowledge, including procedural follow-ups | 33 | 123.81 / 1,970.30 | 121.39 / 245.88 |
| Compound | 12 | 277.03 / 1,121.18 | 251.71 / 456.99 |
| Social/identity | 21 | 9.40 / 253.86 | 9.30 / 49.50 |
| Navigation intent | 3 | 5.74 / 5.75 | 6.16 / 43.57 |
| Unsupported questions | 9 | 252.43 / 1,424.33 | 215.47 / 261.73 |
| Partially supported question | 3 | 261.98 / 335.69 | 268.46 / 300.79 |
| Clarification | 3 | 11.39 / 13.05 | 5.22 / 5.40 |

Matched privacy-safe logs cover **84/84 requests in each phase**. Server overall p50/p95: **121.58/891.49 → 115.00/345.25 ms**. For requests that used hybrid retrieval, median total SQL count fell **14→10**, matching removal of four coverage scans. Their hybrid stage p50/p95 was **124.13/1,297.27 → 86.92/151.32 ms**. Grounding p95 was **35.32→32.37 ms**; suggestions **115.79→93.70 ms**. SQL-time p95 for those requests rose **55.69→75.82 ms**, so there is no claim that every database metric improved.

The baseline made **3 Groq context-edit calls** for the unresolved Filipino follow-up; deterministic resolution eliminated these calls in the after matrix. The after matrix needed **no provider requests**. The separate live provider probe verifies connectivity; it does not turn the zero-provider matrix into an LLM latency benchmark. Stage values are cumulative inclusive timings and can overlap during recursive orchestration; do not sum them as independent wall-clock components. See `PAULA_MVP_STAGE_TIMINGS.json` for every measured stage.

Cold preparation remains material: three-worker **activation-to-readiness 83.89 s**, including restart/shutdown/startup; per-worker initialization **52.73–54.01 s**. The isolated single-worker production-policy run became ready in **57.61 s**. These are different measurements, not a before/after cold-start speed claim. An idle container sample used **1.543 GiB** of its **3.498 GiB** limit; this is not peak memory or a capacity/load test. The sampled warm groups meet the stated latency objectives; complex free-form semantic/LLM traffic and simultaneous users are not certified by this matrix.

## Files changed in this stabilization pass

The workspace already contained many previous enhancements. The following list identifies **this pass**, rather than claiming every dirty/untracked file as new work:

* Retrieval/index lifecycle: `chatbot/__init__.py`, `chatbot/models.py`, `chatbot/rag.py`, `chatbot/admin.py`, `chatbot/grounding.py`, `chatbot/logic.py`, `chatbot/conversation_context.py`.
* Safe errors/readiness/audit: `chatbot/api_errors.py`, `chatbot/performance.py`, `chatbot/health.py`, `chatbot/knowledge_audit.py`, `chatbot/views.py`.
* Management commands: `chatbot/management/commands/index_knowledge.py`, `audit_knowledge.py`, `prepare_embedding_model.py`, `seed_knowledge.py`.
* Backend regression files: `chatbot/test_mvp_indexing.py`, `chatbot/test_mvp_api.py`, `chatbot/test_mvp_operations.py`, `chatbot/test_mvp_context.py`.
* Frontend: `frontend/src/api/chatTransport.js`, `chatTransport.test.mjs`, `chatApi.js`, `chatApi.test.mjs`, `frontend/src/App.jsx`, `frontend/package.json`.
* Configuration/build/CI: `paulibot/settings.py`, `paulibot/settings_production.py`, `.dockerignore`, `.env.example`, `Dockerfile`, `requirements.txt`, `docker-compose.ci.yml`, `.github/workflows/ci.yml`.
* Reproducible checks: `scripts/audit_mvp_knowledge.py`, `benchmark_mvp.py`, `smoke_mvp_production.py`, `smoke_mvp_provider.py`, `summarize_mvp_timings.py`, `verify_mvp.ps1`, `checkpoint_mvp.ps1`.
* Documentation: `README.md`, `PAULA_MVP_AUDIT_INITIAL.md`, this report, `PAULA_MVP_OPERATIONS.md`, `PAULA_DJANGO_LTS_UPGRADE_PLAN.md`. JSON measurement/checkpoint artifacts are separate from application source.

The active development environment file, embedding dimensions, model/provider choice, retrieval cutoff, PostgreSQL container/volume and existing records remain intact. The Dockerfile CPU-install path is for future builds, not a claim that the running image was rebuilt or its dependencies upgraded. New production settings are opt-in and were exercised only by the isolated smoke.

## Remaining risks and unverified areas

1. **Supported-framework migration is outstanding.** Run the separate LTS plan with DRF/Unfold/auth/session/migration compatibility checks before public exposure. The rest of this audit does not compensate for unsupported Django.
2. **Publication/reproducibility is incomplete.** The local checkpoint is not GitHub publication. A new clean CPU image, remote CI, artifact/secret inspection, pinned base-image review and actual hosting configuration still need validation. The current bind-mounted development image is not an immutable production release. Old PostgreSQL/extension versions also require a planned compatibility/security review, not an in-place major upgrade or volume replacement.
3. **Security controls need their own release pass.** The API registration serializer does not invoke configured Django password validators; profile uploads are assigned without backend image/size validation. These confirmed paths, login/guest abuse controls, student identity policy, media serving, actual reverse-proxy trust and cross-site session cookies must be reviewed/tested before public deployment. No accounts were created or passwords/media changed to work around these findings.
4. **Grounding is not institutional fact verification.** Valid vector dimensions do not prove the historical encoder/revision for each record, and source metadata does not establish that every scraped name/program/date is current. The 177 supplementary CSV records remain reference/review data. No automatic fact replacement or conflict resolution was performed. The strict audit currently detects exact-equivalent FAQ conflicts; it is not a complete cross-source semantic contradiction detector.
5. **Coverage is bounded.** FAQ self-match and synthetic examples are regression measures, not independent accuracy/recall/faithfulness estimates. Continue with a held-out, office-reviewed question set containing paraphrases, languages, misspellings, compound queries, unknowns and conflicting sources. Score correct source retrieval and each supported claim, clarification/fallback correctness and false social interception separately. Deterministic parsing and MiniLM do not guarantee arbitrary multilingual conversation understanding.
6. **Operations are not fully rehearsed remotely.** Backups/restores, target-host startup/memory/concurrency, actual remote TLS/cookies, authenticated browser/mobile/360-tour scenarios and live deployment rollback still require testing. The frontend build retains a large JavaScript chunk warning. This pass does not certify RA 10173 compliance or an external security assessment.

## Evidence and next action

Run the [operations checklist](PAULA_MVP_OPERATIONS.md), preserve these measurements, and freeze/rehearse this candidate for the local defense. Start the separate supported-LTS compatibility pass before approving public deployment. No external deployment has been performed.

Evidence artifacts: `PAULA_MVP_AUDIT_BASELINE.json`, `PAULA_MVP_AUDIT_AFTER.json`, `PAULA_MVP_HTTP_BEFORE.json`, `PAULA_MVP_HTTP_AFTER.json`, `PAULA_MVP_STAGE_TIMINGS.json`, `PAULA_MVP_WORKER_READINESS.json`, `PAULA_MVP_PRODUCTION_SMOKE.json`, `PAULA_MVP_PROVIDER_SMOKE.json`, `PAULA_MVP_RESOURCES.json`, `PAULA_MVP_INTEGRITY.json`, `PAULA_MVP_CHECKPOINT.json`, and `PAULA_MVP_RELEASE.json`.
