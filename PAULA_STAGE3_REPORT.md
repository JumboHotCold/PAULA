# PAULA Stage 3 — manual retest fixes and measured reliability

November 9, 2026. Baseline: `d58f55d` / `spelling-robustness-v1`. Final application and verification-tool revision: `cb7e3a37684f93db84447c50822ff5bb3b5a9fbd`. Later evidence/report commits do not change that tested application source.

**The public Log #9 checks pass 14/14. General conversational recognition is still incomplete: the separate synthetic test set reaches only 37.0% social intent accuracy. This is an improvement, not evidence that PAULA understands arbitrary student language or is ready for an unrestricted conversational demo.** No private student-question file was accessed. No deployment, shared-worker reload, ingestion, re-embedding, provider/model replacement, or application-data correction occurred.

## 1. Reproduced causes before editing

The original retest assertions were run red first; they are now included in default discovery through `chatbot/test_stage3_original_retest.py`. Diagnostic observations are frozen in [baseline.json](artifacts/stage3/baseline.json). Similarities are diagnostic cosine similarities, not confidence probabilities. The old social semantic minimum/margin was .65/.08. A path that stopped before retrieval did not reach a lexical or grounding gate.

| Public input | Actual baseline rejection / acceptance | Recorded score or distance |
| --- | --- | --- |
| `tel me abt urself` | Global protected-name guard intercepted an introduction before identity matching; shorthand was not expanded. | `tel` is one edit from protected name token `del`, and one from ordinary `tell`. `abt` had no eligible candidate. Diagnostic best social class was farewell, .3367. |
| `wat r the programs offerd` | `wat` became `what`, but `r` remained; ambiguous spelling caused clarification before retrieval. | `offerd` tied `offer`, `offered`, `offers`, each at distance 1. Diagnostic knowledge similarity .7162 did not settle the spelling tie. |
| `where is the registrr` | Ambiguous spelling stopped navigation before checking destinations. | `register` and `registrar`, each distance 1. Diagnostic knowledge similarity .2095. |
| `thank u po` | No complete local gratitude match; semantic fallback did not accept it. | Gratitude .3310. |
| `salamat gyud` | No complete local match; semantic result below the old minimum. | Gratitude .5928. |
| `salamat kaayo` | Already passed through normalized local gratitude. | Local Cebuano match; embeddings were unnecessary. Diagnostic top class was actually celebration .6398. |
| `maraming salamat po` | Already passed through the local rule. | Diagnostic gratitude .7615; not required for the answer. |
| `daghang salamat` | Already passed through normalized local gratitude. | Diagnostic gratitude .5347; not required. |
| `thanks a lot` | Already passed through the local rule. | Diagnostic gratitude .4923; not required. |

Three of twelve clean staff-name lookups failed because website matching declared a possible name variant ambiguous **before the literal local staff record could be considered**. This was a retrieval precedence issue with unresolved data variations underneath it; it was not missing embeddings.

The final manual recheck also exposed a pending-selection grammar defect: “how about **for** transferees” was not accepted as a short response to PAULA's category question. The shared pending-selection wrapper now removes that conversational frame only when a task is pending, then validates the complete remaining choice. Extra constraints and dates are retained rather than silently discarded. This public Log #9 case is development evidence, not held-out evidence.

## 2. Implemented mechanisms

### Matching, social intent and spelling evidence

* `chatbot/spelling.py` scopes the near-name guard to person-lookup frames. It preserves identifiers and never substitutes a neighboring staff name. Identity/capability requests and non-person questions no longer inherit that guard simply because a word resembles a name.
* `chatbot/chat_language.py` reads a small shorthand map and modifier classes from `chatbot/config/conversation.json`. Expansion affects the matching view. Uppercase identifiers and explicit person-name spans retain protection. Politeness/intensifier removal applies only when the remaining **whole phrase** is a known local social intent; it cannot erase an institutional clause.
* Configured exemplars, matching and social framing share that representation. Language fallback stays within the recognized intent. The manual gratitude cases return Filipino, Cebuano or English acknowledgements as appropriate.
* `chatbot/spelling_evidence.py` bounds spelling alternatives to six candidate queries. It groups simple inflections for presentation, but a stem alone never authorizes an answer. Each evaluated candidate must pass the existing retrieval and eligibility gates. A unique supported interpretation, or candidates sharing the same top evidence, can proceed; divergent evidence requires clarification. Navigation alternatives use curated destination identifiers rather than a generic registration paragraph. Protected names never enter this candidate-replacement path.
* Inflection grouping does **not** eliminate every duplicate retrieval: bounded variants are still evaluated to establish agreement. Over-budget ambiguity may still require more than one clarification. This is a remaining efficiency/usability limit.
* On spelling uncertainty, the local social semantic fallback can inspect the uncorrected shorthand view before factual clarification, with substantive-question, self-reference, single-word, number and identifier guards. It does not bypass grounding for university facts.

No failing full input string or typo-variant list was added to application code/config. Public failing inputs live in tests. The permitted small shorthand lexicon and clean development exemplars are configuration, not institutional answer facts.

### Confirmation, context and frontend

* `chatbot/clarifications.py` validates bounded pending state; `context_tokens.py` signs it and binds it to owner, thread and saved-message anchor. A single proposed question can be confirmed with `yes/oo/opo/sige/ok`; multiple proposals require a choice. `no/hindi/dili` cancels. Existing enrollment/navigation task state can be resumed without putting answer facts in the token.
* `chatbot/views.py` restores correction choices only from the last **owned, server-saved** reply. Client history is not trusted as confirmation authority. Tests cover owner/thread/anchor mismatches and explicit guest mode despite an authenticated test identity.
* `frontend/src/suggestions.js` preserves required correction choices after saved-history restoration, even if the canonical question was asked earlier. Real browser clicks and “yes” after refresh were verified against a separate synthetic student account.
* `frontend/src/messageBlocks.js` and `components/Dashboard.jsx` render program/procedure lists as semantic `ul/ol/li` with explicit markers. Visual checking caught Tailwind's marker reset; the final screenshots show visible bullets and no horizontal overflow at 390 px.
* `clarifications.selection_view` is reused by pending enrollment and navigation selections. The caller must validate the entire remaining selection. A new substantive question, unsupported constraint or unrelated topic is not reduced to a category label.

Ordinary follow-up suggestion ranking was left unchanged. It can still suggest broadly related enrollment items instead of the most useful next transferee question. That needs separate relevance evaluation; no extra LLM call was added to disguise it.

### Staff records and source uncertainty

`chatbot/rag.py` permits a literal exact local staff-name hit to survive an ambiguous website formatting match. Its answer explicitly says **“The local staff record lists…”** and includes review metadata; it does not merge records or certify the current appointment. Role/title requests retain conflict checks. All twelve clean local identities now retrieve at rank one.

| Previously failing local record | Stored website variation | Classification / remaining review |
| --- | --- | --- |
| Dr. Karen Plaza — CEIT Dean | Dr. Karen T. Plaza — CEIT Dean, Graduate School Faculty, Program Chair | Name/title formatting variation; exact-identity retrieval precedence fixed. |
| Arnold Magalona — Instructor | Engr. Arnold A. Magalona — ICT Systems and Services Director | Possible same-person name variation plus different role records. Could be concurrent or outdated roles; human verification required. |
| Mr. Nikko Ederio — Dean, College of Information and Computing Sciences | Dr. Nikko T. Ederio, LPT — VP for Academics Services | Name/honorific and substantial role difference; human verification required. |

The database also contains the longer Arnold and Nikko names as separate staff entries. They were **not** automatically merged. PBMO's office FAQ spells its director **Michelle Timblacol-Plaza**, while stored website records say **Michelle Timblaco-Plaza**. That spelling/provenance conflict remains for human review. See [personnel_review.json](artifacts/stage3/personnel_review.json).

The stored official-directory records were scraped October 27, 2026. The CEIT Dean answer agrees with those stored official-site records. A fresh direct fetch of the [official SPUS directory](https://spus.edu.ph/administrator/) returned HTTP 403 during verification; therefore a current appointment and exact spelling were **not freshly confirmed from the live page**. No new scrape or institutional fact was imported.

### Frontend version stamp

`frontend/buildMetadata.mjs`, Vite and `src/buildInfo.js` expose the frontend commit, source SHA-256 and dirty flag through `window.__PAULA_BUILD__`, the startup console and development `/__paula_build`. Production builds emit `dist/paula-build.json` with bundle hashes.

The final browser and production build both identify `cb7e3a3…`, frontend digest `2154e44186e86966df2258482489b9ae63e440d8a194d6b2a8b7f4968d4128a7`, with a clean frontend tree. The temporary backend reports the same commit and backend digest `c35de1580582e458eb254f980bc10200cd177e4025de4f4c42c398fdcbc7ef47`. Evidence: [browser result](artifacts/stage3/browser/result.json), [frontend manifest](artifacts/stage3/frontend-build.json).

These are process/build snapshots. Restart Vite after source changes when verifying its stamp; HMR does not recapture startup metadata. A stamp does not certify environment variables, database freshness or future files. Later report commits can legitimately make Git HEAD newer than the tested build.

## 3. Evaluation protocol and threshold decision

[Frozen sets and hashes](artifacts/stage3/sets/manifest.json):

* **608 distinct social inputs** from 76 source phrases, and **960 distinct institutional negative controls** from 120 source phrases.
* Eight operations: clean, transposition, deletion, insertion, substitution, doubled letters, spacing and case. All variants of a source phrase stay together.
* Source-family split: 53/23 social and 84/36 institutional source phrases, approximately 70/30. Development has 1,096 cases; synthetic test has 472.
* The separate 1,284-case golden set includes all 138 FAQ questions with perturbations, twelve staff and six location records, added paraphrase/multilingual cases, eight unsupported/ambiguous controls, two compound and two multi-turn cases.

These are **agent-authored synthetic datasets**, not the user's private real-student held-out file. Development cases were used to select 28 additional clean exemplar prototypes. Development scores therefore include training fit. The test split was not used to select prototypes or thresholds. It was rerun unchanged after the separately reported public-manual selection fix; it is not a newly unseen second test set.

The development-only grid selected **social semantic minimum .55 and margin .05**, compared with the old .65/.08. With the same expanded development prototypes: 963/1,096 correct versus 942/1,096, and zero institutional captures in both configurations. [Calibration](artifacts/stage3/calibration.json) records every grid point and the selection rule. This local classifier change was justified by measured development data; **the document retrieval cutoff stays .45**. The embedding model/revision/dimensions, provider models, SDK settings and grounding thresholds were not changed.

### Before/after results

| Measure | Baseline `d58f55d` | Final source |
| --- | ---: | ---: |
| Public Log #9 API checks | Reported failures reproduced | **14/14** |
| Social development intent accuracy | 67/424 = 15.8% | **291/424 = 68.6%** |
| Social synthetic test intent accuracy | 24/184 = 13.0% | **68/184 = 37.0%** |
| Institutional social false positives, dev | 0/672 | **0/672** |
| Institutional social false positives, test | 0/288 | **0/288** |
| Overall dev intent accuracy, including controls | 739/1,096 = 67.4% | **963/1,096 = 87.9%** |
| Overall test intent accuracy, including controls | 312/472 = 66.1% | **356/472 = 75.4%** |
| FAQ golden recall @1 / @3, 1,128 cases | 766 / 779 = 67.9% / 69.1% | **800 / 825 = 70.9% / 73.1%** |
| Clean FAQ API recall @1 / @3, 138 | 120 / 121 | **120 / 121** |
| Clean staff rank-one identity | 9/12 | **12/12** |
| All staff perturbations @1 / @3 | 18/96 / 18/96 | **24/96 / 24/96** |
| Wrong-person results in staff perturbations | 0/96 | **0/96** |
| Location recall @1 / @3 | 31/48 / 39/48 | **31/48 / 39/48** |
| Correct refusals, narrow unsupported/ambiguous controls | 8/8 | **8/8** |
| Compound cases answered | 2/2 | **2/2** |
| Golden follow-up chains answered | 1/2 | **1/2** |
| Golden clarification rate | 342/1,284 = 26.6% | **279/1,284 = 21.7%** |
| Golden HTTP/server-unavailable error rate | 0/1,284 | **0/1,284** |

The institutional control score measures **routing only**, not answer accuracy. Only 14/23 clean social test source phrases classify correctly; weak recognition is not explained solely by artificial spelling errors. No observed institutional capture or wrong-person answer is a guarantee beyond the evaluated cases.

Of the final 279 golden clarifications, **277 have a labeled source/name already present**. This is a review upper bound, not 277 proven avoidable clarifications: protected misspelled names and incomplete questions should often be clarified. Eleven clean FAQ strings clarify, including six OCR fragment headings and five composite/ambiguous question forms. The summary's legacy field name `confirmed_avoidable_clean_faq` overstates certainty; interpret it as a source-present review count.

Raw FAQ self-match auditing is a different check and still passes **138/138**. Conversational orchestration can split a composite stored question or recognize a persona question before exact lookup. The golden labels also identify particular records; an equivalent answer from another record can be counted as a source-recall miss. For example, the college-course paraphrase returns supported evidence but misses its narrow expected record ID. These scores are record-recall/intent metrics, not independent audits of every institutional fact.

The remaining golden follow-up failure is the three-turn chain “What are the enrollment requirements?” → “Old/continuing college student” → “How about for transferees?”. The intermediate turn loses usable task continuity. The direct Log #9 pending-category chain passes, but this longer case is **still a BAD_CONTEXT failure**.

### Spacing ablation

On the same 156 golden spacing cases, current safe spacing repair enabled yields **67/156 @1, 77/156 @3**; disabled yields **45/156 @1, 56/156 @3**. This isolates the existing bounded split/join mechanism with a context-local evaluation switch. Known words and protected identifiers remain excluded. It does not demonstrate unrestricted word segmentation or justify joining names.

### Complete failure export

[failures.csv](artifacts/stage3/failures.csv) contains **1,588 failed rows** across before/after dev, test and golden runs. Final failures: 133 dev, 116 test, 385 golden. Each row includes query, expected label, actual intent, outcome, reason, source, preview and the requested cause taxonomy. Labels are diagnostic heuristics, not proof of absent knowledge. Raw per-request stage/rank evidence is in [measurements](artifacts/stage3/measurements/); aggregate metrics are in [comparison.json](artifacts/stage3/comparison.json).

## 4. Latency and measurement limits

Before/after use identical frozen inputs, the same existing PostgreSQL knowledge, cached MiniLM and sequential in-process guest DRF requests. Providers are disabled during evaluation. API timings include view/orchestration work; they exclude browser/network delivery and model startup. The observer additionally probes plans/ranks; its separate `latency_ms` must not be mistaken for HTTP latency. Percentiles are nearest-rank empirical values, not concurrent-load SLOs.

| API scope | Before p50 / p95 ms | After p50 / p95 ms |
| --- | ---: | ---: |
| Social development | 68.27 / 190.11 | **11.61 / 141.22** |
| Social synthetic test | 18.05 / 150.37 | **22.23 / 160.23** |
| Institutional test controls | 137.72 / 188.57 | **128.85 / 173.74** |
| FAQ golden | 63.75 / 167.32 | **57.83 / 165.26** |
| Compound golden, only two samples | 204.20 / 230.15 | **195.36 / 198.84** |
| All golden | 62.69 / 163.04 | **57.81 / 158.83** |

| Stage, golden cases where stage ran | Before p50 / p95 ms | After p50 / p95 ms |
| --- | ---: | ---: |
| Dialogue routing | 1.129 / 3.752 | 1.362 / 3.474 |
| Spelling matching | .377 / 1.000 | .446 / .945 |
| Context resolution | .515 / 1.531 | .511 / 1.013 |
| Retrieval | 6.411 / 109.061 | 5.645 / 115.540 |
| Query embedding | 22.431 / 86.022 | 19.282 / 68.166 |
| Grounding | 18.177 / 34.305 | 15.491 / 29.198 |
| Follow-up suggestions | 55.749 / 88.840 | 48.450 / 65.491 |
| Evidence selection, local fallback only | .071 / .125 | .056 / .135 |
| Stored response rendering | .039 / .139 | .036 / .103 |

Stage timings are inclusive, can overlap, and have different sample counts; do not sum their percentiles. Candidate spelling evidence ran in 27 golden cases, p50/p95 **89.44/189.69 ms**. The final temporary one-worker readiness initialization took **41.86 seconds**, including model preparation. This is not a cold-start optimization claim. Social test p95 worsened slightly. No general latency guarantee, LLM latency improvement, concurrent capacity or free-tier deployment result is claimed.

## 5. Tests, CI and data integrity

Baseline full suites: **471 backend / 27 frontend**. Final full suites: **499 backend tests discovered, 498 passed and one explicitly opt-in live test skipped; 31/31 frontend passed**. The final backend suite also passes in the separate CI PostgreSQL tmpfs environment. Final production frontend build passes; existing large-chunk and Node deprecation warnings remain.

The requested mechanisms were committed separately, with both full suites after each change. Per-step records are `artifacts/stage3/*-checks.json` (revision is the checked parent HEAD; source edits were present during the run):

| Mechanism | Commit | Backend discovered / frontend |
| --- | --- | ---: |
| Person-lookup guard | `a2eba43` | 472 / 27 |
| Shorthand/social modifiers | `48a0bb5` | 474 / 27 |
| Grounded spelling alternatives | `7ae0947` | 479 / 27 |
| Signed confirmation/restoration | `bd3e2d9` | 483 / 27 |
| Restored frontend choices | `876d36a` | 483 / 29 |
| Exact staff identities with review metadata | `513fe24` | 485 / 29 |
| Frontend build stamp | `32a4dcb` | 485 / 30 |
| Rank/spacing measurement support | `4304cb9` | 487 / 30 |
| Fault injection / CI knowledge gate | `16b5491` | 490 / 30 |
| Measured semantic precedence/config | `6181064` | 495 / 30 |
| Frozen sets / private runner | `57ca490` | 497 / 30 |
| Semantic list rendering | `9f5b6bc` | 497 / 31 |
| Visible list markers | `0f69646` | 497 / 31 |
| Validated pending-selection wrappers | `2ccb645` | 499 / 31 |
| HTTP/browser verification tools | `cb7e3a3` | 499 / 31 |

From the fault/CI commit onward, one backend test is the skipped live-provider smoke. Concurrent user migration commits/merge were preserved; the pgvector extension migration was not authored as a spelling or content change.

New regression coverage includes name-guard negative cases, institutional social-capture protection, tied candidates with same/different/no/conflicting evidence, semantic guard precedence, English/Filipino/Bisaya confirmation, signed-state isolation, owned refresh restoration, short pending selections with constraints, staff identity variants, spacing ablation, frontend choices, semantic lists and build metadata. See `chatbot/test_stage3_*.py` and the frontend test files listed below.

Fault tests inject Groq 429, timeout, invalid output, empty retrieval and database exceptions. They verify safe stored-source fallback or an appropriate no-match/unavailable outcome without leaking exception text. These are injected failures, not real API quota/account tests. `chatbot/test_stage3_live.py` requires `PAULA_RUN_LIVE_SMOKE=1`; it was not run.

The existing `audit_knowledge` management command was made CI-runnable with a guarded, disposable fixture. It checks counts, PostgreSQL/pgvector, dimension 384, finite/nonzero vectors and FAQ self-matches. `.github/workflows/ci.yml` now runs migrations, the synthetic audit gate, regression suites, frontend build and the **actual frontend API module against Django HTTP**. The local HTTP contract passes: four guest turns unsaved, signed pending-task context, and anonymous history access redirected to login. Browser integration additionally passes an actual saved-thread reload, pointer click, bare-yes confirmation, 21 visible program list items and 390 px layout. [Browser screenshots](artifacts/stage3/browser/) and [CI suite summary](artifacts/stage3/ci-suite.json) preserve evidence.

Remote GitHub Actions and a fresh dependency image build were **not** executed. Local isolated CI reused the existing runtime image. An attempted fresh image build was stopped while downloading a new unpinned base, before a completed image or dependency change. Initial isolated-suite failures caused by missing collected static assets were resolved by running its normal `collectstatic` setup; final suites pass. Browser-harness selector/reload timing issues were corrected before its final passing run. Browser automation is a separate local test tool, not the default CI browser job; CI runs the portable frontend-transport HTTP integration.

[Full-row fingerprints](artifacts/stage3/integrity.json) are identical before/after, including embeddings and saved messages:

| Existing table | Unchanged rows |
| --- | ---: |
| FAQ | 138 |
| StaffMember | 12 |
| Location | 6 |
| WebResource | 476 |
| Conversation | 140 |
| ChatHistory | 177 |

[Strict knowledge audit](artifacts/stage3/knowledge_audit.json): **632 valid 384-dimensional vectors**, no missing/invalid/zero vectors, **138/138 raw FAQ self-matches**. No shared-application schema migration, re-embedding, replacement application account or historical data change was performed by this work. CI migrations and synthetic account/history fixtures existed only in the separate CI tmpfs database. Normal unanswered-query text logging remains disabled.

## 6. Knowledge/source gaps and remaining risks

[knowledge_gaps.json](artifacts/stage3/knowledge_gaps.json) lists 366 final golden no-source/no-action outcomes for review. It deliberately separates labeled-source retrieval/grounding failures from unsupported/ambiguous labels. It is **not** a shopping list for new invented content.

* Source-present questions still fail, including some SPUS overview/rationale paraphrases, Filipino/Bisaya forms and the longer enrollment follow-up. Correct routing/context/labels before adding duplicate facts.
* OCR fragment titles and stored multi-question FAQ titles need source/label review. The eleven clean source-present clarifications cannot all be called missing knowledge.
* Current dated tuition/fee and examination information would require approved, dated institutional sources. Synthetic requests for 2037/2099 values remain unanswered; no future schedule or fee was invented.
* Personal balances and passwords are not public knowledge-base facts. Their absence should not be “fixed” by inserting private data into RAG.
* Vague “the director” / “that office” needs an office or antecedent. The fictional college/program controls should remain unsupported.
* Personnel name/role differences and the PBMO spelling difference require human reconciliation against official evidence. No institutional fact was silently selected for overwrite.
* Name perturbation recall stays deliberately low; protected identities are clarified rather than guessed. A human-reviewed alias policy would be a separate decision.
* Synthetic social test performance, particularly multilingual/free-form phrasing, is inadequate for claiming general conversational intelligence. More dev prototypes alone do not establish generalization. The user's private real-student evaluation is the next independent check, not permission to tune on that file.
* Suggestion relevance, concurrent load, live provider behavior, new production images and deployment/security readiness were not established here.

## 7. Run the private evaluation yourself

```powershell
python scripts/run_questions.py "C:\path\outside-the-repo\student_questions.txt" --no-providers
```

The runner prints each normalized form, intent, reason code, reply preview, top source and latency, then writes a UTF-8 CSV beside the input. It uses the existing Docker PostgreSQL backend through a separate management process; it does not copy the file into the repository/container or save guest chat history. JSON/JSONL/CSV can supply `query`/`question` and a shared `thread` identifier for multi-turn cases. Plain text lines run independently. Omit `--no-providers` only when intentionally evaluating the configured provider path.

The runner deliberately prints private input/reply previews into **your terminal and output CSV**. Protect those files; application raw-query logging remains disabled. Startup timing and API-stage timings are distinct. Only the public two-question demo was run during this task; no private file was requested or opened.

## 8. Modified files and stop point

Runtime/config: `chatbot/chat_language.py`, `spelling.py`, `spelling_evidence.py`, `social_normalization.py`, `social_responses.py`, `dialogue.py`, `config/conversation.json`, `conversation_config.py`, `logic.py`, `clarifications.py`, `context_tokens.py`, `views.py`, `intents.py`, `rag.py`; CI audit support in `management/commands/audit_knowledge.py`. Provider, embedding-runtime, grounding implementation and database model definitions retain their architecture/values.

Frontend: `frontend/buildMetadata.mjs`, `vite.config.js`, `src/buildInfo.js`, `src/main.jsx`, `src/App.jsx`, `src/suggestions.js`, `src/messageBlocks.js`, `src/components/Dashboard.jsx`.

Tests/fixtures: `chatbot/audit_stage3_retest.py`, `test_stage3_*.py`, `testdata/conversation_v1.json`, targeted expectation updates in `test_dialogue.py`, `test_query_understanding.py`, `test_spelling.py`, `test_stage2_config.py`; `frontend/buildMetadata.test.mjs`, `src/stage3History.test.mjs`, `src/messageBlocks.test.mjs`.

Evaluation/CI tools: `scripts/stage3_{baseline,checks,engine,evaluate,final_snapshot,browser_fixture}`, `build_stage3_sets.py`, `calibrate_stage3.py`, `select_stage3_dev_exemplars.py`, `summarize_stage3.py`, `question_worker.py`, `run_questions.py`, `verify_stage3_{manual,browser,transport}`, `ci_knowledge_gate.py`, `ci_pgvector.sql`, `.github/workflows/ci.yml`, `docker-compose.ci.yml`, `docker-compose.stage3-test.yml`; this report and `artifacts/stage3/`. Script extensions are `.py`, `.ps1` or `.mjs` as appropriate.

**Stage 3 stops here.** The temporary CI/browser services are cleaned up; the shared app is not deployed or reloaded. Its observed running build remains `d58f55d` ([record](artifacts/stage3/shared-service-unchanged.json)), so the existing 8080 workers will not show these backend fixes until a deliberate local reload. Verify both backend readiness and the frontend build stamp when activating a tested build. No Stage 4, new model, data reconciliation or deployment is included.
