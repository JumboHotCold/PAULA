# PAULA spelling robustness — Log #7

**November 9, 2026.** Implemented locally after Stage 2. No deployment, shared-worker reload, ingestion, re-embedding, provider/model change, retrieval-cutoff change, or application-data modification. Stage 3 has not started.

## Result

- All reported examples, including each short phrase individually, pass their regression tests.
- **471 backend tests / 27 frontend tests pass.** The starting Stage 2 suites had 442 / 27 passing tests; 29 backend tests were added.
- **55/55 isolated guest API checks pass**, including enrollment → continuing student → gratitude → transferee follow-up. External provider execution was trapped: **zero calls**.
- The frozen **1,995-case synthetic development set** shows better FAQ recall and intent accuracy. Name and location recall have safety-related trade-offs, reported below.
- Full-row application-data fingerprints, including existing embeddings and conversation records, are identical before and after.

Evidence: [comparison](artifacts/spelling/comparison.json), [API checks](artifacts/spelling/api.json), [database integrity](artifacts/spelling/integrity.json), [backend output](artifacts/spelling/backend.log), [frontend output](artifacts/spelling/frontend.log).

## Reproduction and rejection stages

The new reproduction module ran before implementation: four test methods produced **six failed assertions**. `who r u` passed individually; the three other short phrases failed. The greeting + correctly spelled introduction already passed. Detailed traces were recorded before changing the application: [before.json](artifacts/spelling/before.json).

Distances below are raw cosine distances to the nearest FAQ in the diagnostic probe. The unchanged retrieval cutoff is **0.45**. Social similarities are cosine similarities, with the existing semantic classifier minimum **0.65** and margin **0.08**. Diagnostic semantic probes do not imply that the actual router invoked embeddings on every input.

| Input | Actual rejection path before the fix | Recorded evidence |
| --- | --- | --- |
| `tell me abuot yourself` | Old normalization leaves `abuot`; identity regex misses. Identity has no semantic exemplar class. Semantic fallback cannot rescue the request; retrieval/grounding then reject it. | Top social class is celebration, **0.3051**, margin **0.0123**. Nearest FAQ distance **0.8056**, grounding false. `abuot` → `about` is one transposition, outside the old correction vocabulary. |
| `hi, tell me about yourself?` | **No rejection.** Existing Stage 2 wrapper composition routes locally to identity. | No retrieval/provider needed. |
| `who r u` | **No rejection.** Existing full identity regex already accepts it. | No retrieval/provider needed. |
| `wat can u do` | Old normalization does not repair `wat`; capability regex requires its supported complete wording. Semantic fallback is below threshold and lacks the required self-reference affordance for `u`. | Capability similarity **0.4755**. Nearest FAQ distance **0.8960**, grounding false. |
| `thnx` | Not an exact abbreviation. The old social fuzzy path rejects four-character compact inputs before distance matching. Unknown single-word routing then skips semantic fallback. | Diagnostic-only gratitude similarity **0.3641**. Both configured aliases `thx` and `tnx` are one edit away. Nearest FAQ distance **0.8542**, grounding false. |
| `thankyouuu` | No repeated-run handling. It is two deletions from compact `thankyou`, exceeding the old one-edit/length-difference allowance. Unknown single-word routing skips semantic fallback. | Diagnostic-only best social similarity **0.2771**; nearest FAQ distance **0.8627**, grounding false. |
| All four short phrases in one message | No complete local pattern matches; old social matching cannot accept nine words. Existing factual decomposition is not a social-intent composer. | Best semantic class capability **0.3828**, margin **0.0459**; nearest FAQ distance **0.8065**, grounding false. |
| `hi, what are the programs ofered` | Greeting is stripped, but `ofered` remains. Exact FAQ/listing equivalence fails. Hybrid retrieval encounters both a distance rejection and a grounding rejection. | Nearest FAQ distance **0.6398**. Query terms are `{program, ofered}`: only `program` is supported, **1/2 coverage**, below the required **1.0** for two terms. |

For the correctly spelled programs question, exact listing lookup succeeds. Its diagnostic nearest-vector FAQ distance is still **0.5122**: lowering the vector cutoff would be the wrong fix. Correcting the matching form restores exact retrieval and its corresponding grounding check.

## Implemented design

The path is: **submitted text → immutable normalization view → spelling plan → local intent/composition or clarification → contextual retrieval → unchanged grounding and source rendering**.

### One public vocabulary, one spelling implementation

[chatbot/spelling.py](chatbot/spelling.py) builds an immutable per-worker snapshot before readiness from:

- Existing configured exemplars, social forms, abbreviations, and literal local-pattern vocabulary.
- Existing navigation aliases, valid-word guards, lexical aliases and grammatical words.
- All **138 FAQ questions**, **12 staff records**, and **6 location names**.
- Names/roles from **407 already-stored structured website personnel records**. These strings protect identifiers; including them does **not** newly verify their accuracy or import scraped CSV data.

The final snapshot has **1,653 known tokens** and **717 protected name tokens**. It reads no user, conversation, or chat-history tables. The snapshot and candidate indexes are cached; submitted tokens and messages are not globally cached. Vocabulary preparation measured **81.7 ms** in the final isolated API run; this is not a production startup guarantee.

The former phrase-specific typo overrides were removed from `intents.normalize_query`; that function now delegates to the shared matching plan. No reported typo or list of its variants was added to application code/configuration.

### Correction and safety rules

- NFKC normalization, whitespace cleanup and case-insensitive lookup use the shared normalization representation. A new case-preserving view retains uppercase acronym gates. `original` remains untouched.
- Known vocabulary tokens are never spelling-corrected.
- Only OOV ordinary words with a **unique minimum Damerau/optimal-string-alignment edit distance** can be replaced. Adjacent transpositions count as one edit.
- One edit is allowed for ordinary eligible tokens; two edits are considered only for words of at least eight characters. **Two-edit factual repairs always require confirmation.**
- Ordinary correction confidence is based on edit distance/length. Scores below **0.80** require confirmation. A unique leading question-word repair receives a grammatical confidence floor of 0.80. These are matching scores, not probabilities.
- Ambiguous candidates remain unchanged. The assistant offers complete question choices instead of selecting one silently.
- Names and acronyms are excluded from correction targets. Numbers, codes, URLs, emails and unknown uppercase abbreviations are opaque. Unknown proper-name spans are preserved.
- OOV tokens near stored person names trigger name/role confirmation. Known full names one edit from another known full name also require disambiguation.
- Missing/inserted spaces receive bounded repairs only when the split/join is unique and does not consume an already-known token or protected identifier.
- Repeated-letter collapsing is used **only in whole social/identity matching**. Collapsed text never becomes an institutional embedding or retrieval query. Ordinary single duplicated-letter edits can still be corrected by the general spelling step.

The corrected matching query reaches exact lookup, keyword matching, vector encoding and grounding together. [RAGSearcher.retrieve](chatbot/rag.py) also checks spelling plans defensively. Uncertain plans do not proceed to retrieval. **The 0.45 document cutoff and the semantic social thresholds were not changed or calibrated.**

### Social composition and short replies

All local intents share the matching step, including the tail following a greeting. Existing configured complete exemplars are recognized deterministically before semantic fallback or clause splitting.

Pure local social/self clauses can be composed across punctuation and the existing coordination forms, bounded to six clauses. Every clause must resolve independently; institutional or unknown clauses keep the message on the knowledge path. Repeated intents are acknowledged once, and composed replies use brief excerpts of existing reviewed persona text.

The bounded social single-edit matcher now accepts scores of **0.80** (previously 0.82), retaining its prefix and substitution safeguards so existing greeting typos no longer need dedicated overrides. Whole configured-phrase matching requires at least **0.82** and at most two edits. The semantic classifier's **0.65 / 0.08** thresholds and factual grounding criteria are unchanged. False-positive controls and the complete social regression suite pass; this is development validation, not held-out calibration.

`thnx` remains unchanged as a token: its nearest configured abbreviation candidates agree on gratitude, so recognition uses **intent consensus**, not an arbitrary spelling substitution. `wat can u do` preserves the known token `u`; complete-phrase matching recognizes the self-capability request without inserting that pronoun into a factual query.

Final recorded plans: `abuot` → `about`, distance **1**, confidence **0.80**; `ofered` → `offered`, distance **1**, confidence **0.857143**. See [after.json](artifacts/spelling/after.json) for all reported inputs and routing metadata.

### Names and conversation state

Development testing exposed a pre-existing issue: a literal staff-name request could receive a differently named vector neighbor. Literal name requests now use exact structured personnel, exact FAQ or exact local staff-name evidence; unsuccessful name lookup cannot identify another person through vector proximity. Role questions retain their existing retrieval paths. No stored name, title, source priority or institutional fact was overwritten.

Spelling clarification preserves the existing conversation anchor, validated pending enrollment/navigation task and language preference. Choices use the existing frontend suggestion protocol. Authenticated history retains the submitted spelling; guest requests remain unsaved even with an authenticated test identity. Default diagnostics do not log query text; the existing rehearsal opt-in still records the **original**, not corrected, input.

## Development evaluation

[corpus.json](artifacts/spelling/corpus.json) was frozen before implementation, using deterministic seed **314159** and the same queries before/after. The corpus hash is checked by the summarizer.

| Group | Sources/examples | Cases |
| --- | ---: | ---: |
| FAQ retrieval | All 138 FAQ questions | 1,104 |
| Staff-name retrieval | All 12 local staff records | 96 |
| Location retrieval | All 6 stored location records | 48 |
| Intent classification | 92 configured examples/forms/aliases and canonical self requests, including 13 knowledge controls | 736 |
| Near-miss factual controls | 11 substantive institutional questions | 11 |

Each source/example receives clean, transposition, deletion, insertion, substitution, doubled-letter, inserted-space, and case variants. Short expressions sometimes produce identical variants or a different valid word. Those cases remain in the denominator. The benchmark uses the cached existing MiniLM model and active PostgreSQL data, without provider calls. It follows routing confirmation decisions: clarification is an abstention, not a retrieval hit.

### Recall and intent accuracy

| Measure | Before | After |
| --- | ---: | ---: |
| FAQ recall@1, 1,104 cases | **671/1,104 — 60.8%** | **867/1,104 — 78.5%** |
| FAQ recall@3 | **762/1,104 — 69.0%** | **869/1,104 — 78.7%** |
| Staff identity recall@1, 96 cases | **41/96 — 42.7%** | **18/96 — 18.8%** |
| Staff identity recall@3 | **45/96 — 46.9%** | **18/96 — 18.8%** |
| Location recall@1, 48 cases | **34/48 — 70.8%** | **33/48 — 68.8%** |
| Location recall@3 | **41/48 — 85.4%** | **39/48 — 81.3%** |
| Intent accuracy, 736 cases | **537/736 — 73.0%** | **665/736 — 90.4%** |
| Clean intent accuracy, 92 cases | **89/92 — 96.7%** | **92/92 — 100%** |
| Queries returning a different person, 96 staff cases | **5** | **0** |
| Near-miss controls captured by a social shortcut | **0/11** | **0/11** |

Staff identity scoring uses the existing `person_key` to ignore honorifics and comma-delimited credential suffixes. It is a benchmark key, not proof that records should be merged. Raw exact-name recall and the one remaining formatting-variant row are separately retained in the comparison artifact.

**The reduced misspelled-name recall is deliberate:** 68/96 cases now request name confirmation and six remain ambiguous. Clean staff recall@1 rises from 8/12 to 9/12; clean recall@3 stays 9/12. Clean location recall@3 remains **6/6**. This is a safety trade-off, not an across-the-board recall improvement.

The only eight FAQ cases entering social handling are the clean/perturbed versions of the stored PAULA self-introduction question. Review of the remaining **1,240 institutional FAQ/staff/location cases** and 11 near-miss controls found **zero social interceptions**. That result applies to this development set, not every future utterance.

### Breakdown by perturbation

FAQ columns show **recall@1 hits / recall@3 hits**, out of **138** per row. Intent columns show correct classifications out of **92**.

| Operation | FAQ before | FAQ after | Intent before | Intent after |
| --- | ---: | ---: | ---: | ---: |
| Clean | 131 / 131 | 136 / 136 | 89 | 92 |
| Transposition | 69 / 86 | 90 / 90 | 64 | 83 |
| Deletion | 65 / 81 | 93 / 93 | 62 | 77 |
| Insertion | 70 / 85 | 129 / 129 | 57 | 83 |
| Substitution | 69 / 81 | 90 / 90 | 48 | 77 |
| Doubled letter | 75 / 94 | 129 / 129 | 62 | 90 |
| Spacing | 61 / 73 | 64 / 66 | 66 | 71 |
| Case | 131 / 131 | 136 / 136 | 89 | 92 |

One clean FAQ remains a source conflict concerning the PBMO director; another is the self-introduction now handled locally. Conflicts were preserved rather than resolved through a spelling rule.

### Latency

Sequential warm **routing + retrieval** development measurements, nearest-rank percentiles, in milliseconds:

| Group | Before p50 / p95 | After p50 / p95 |
| --- | ---: | ---: |
| FAQ | 73.223 / 97.288 | **5.561 / 60.720** |
| Intent | 12.611 / 18.167 | **0.141 / 0.686** |
| Staff | 126.049 / 143.271 | **0.780 / 82.188** |
| Location | 58.749 / 75.020 | **57.425 / 71.762** |

More exact FAQ hits and local exemplar matches avoid embedding work. Fast name/ambiguity abstentions also lower timing; those are **not faster successful answers**. This benchmark excludes HTTP transport, browser rendering, provider inference and load/concurrency testing. It does not establish production p95 targets or a cold-start improvement.

The additional in-process DRF checks run 17 representative cases three times plus a four-turn guest flow: **55/55 pass**. They validate actual API orchestration, suggestions, compound answers and guest persistence boundaries against current stored sources. Per-case timings/stages are in [api.json](artifacts/spelling/api.json); three samples per case are insufficient for a reliable production p95 claim.

## Tests, failures encountered and compatibility

New regression modules: [test_spelling_reproductions.py](chatbot/test_spelling_reproductions.py), [test_spelling.py](chatbot/test_spelling.py). They cover unique/ambiguous edits, protected names/acronyms/codes, cached website-name protection, Unicode, repeat isolation, spacing, all configured exemplars, social/factual composition, matching idempotence, corrected vector input, response-boundary grounding, original authenticated history, guest privacy, rehearsal logging and clarification choices.

Final full commands:

```powershell
docker exec paulibot_web python -B manage.py test chatbot --keepdb --noinput --verbosity 0
npm.cmd test --prefix frontend
```

**471 / 27 passed; zero final suite failures.** Earlier targeted runs caught vocabulary-stem pollution, over-broad social composition, unsafe short repeat matching and replacement-span ordering; those were fixed before final validation. Initial test setup also lacked pgvector after recreating the isolated test database. The extension was restored **only there**, and subsequent runs reused that test database. The application database was not reset.

Three old expectations were intentionally revised to match the requested safety contract:

- `hwo` ties `how`/`who`: preserve it and offer clarification, replacing the old hardcoded choice.
- `wher` ties `when`/`where`: clarify, while retaining a separate unambiguous navigation regression. In the full public vocabulary, `registar` also ties `register`/`registrar`; isolated API validation confirms clarification plus a separate unambiguous navigation success.
- Valid uppercase `ENROL` stays unchanged; existing enrollment grammar already accepts it.

Readiness-test mocks now explicitly stub vocabulary preparation; separate PostgreSQL tests exercise the real public snapshot. Existing context, compound retrieval, navigation, provider failure handling, authentication isolation, suggestions and frontend send-guard suites all remain in the passing full run. No frontend source changes were needed.

An initial API expectation incorrectly assumed `registar` was unique: 45/48 checks passed. After inspecting the actual tied candidates, the expected clarification was retained, and an independently unambiguous navigation case and multi-turn flow were added. The final check is **55/55**; no threshold was relaxed to force a pass.

## Data integrity and files

[Integrity evidence](artifacts/spelling/integrity.json) confirms unchanged full-row hashes/counts for **138 FAQs, 12 staff, 6 locations, 476 web resources, 140 conversations and 177 saved messages**, including stored vectors. Test fixtures/accounts existed only in the isolated PostgreSQL test database. Existing records, manually corrected facts and historical messages were preserved.

Application changes:

- `chatbot/spelling.py` — public immutable vocabulary, edit indexes, protected identifiers and matching plans.
- `chatbot/query_normalization.py` — shared case-preserving normalized view.
- `chatbot/intents.py` — shared spelling facade, removal of typo-specific overrides.
- `chatbot/dialogue.py`, `chatbot/social_normalization.py` — all-intent matching, social-only repeat handling, configured exemplar recognition and bounded composition.
- `chatbot/logic.py` — concise composed replies, confirmation choices and context preservation.
- `chatbot/rag.py` — matching-plan enforcement and exact identity boundary for name requests.
- `chatbot/readiness.py` — cached vocabulary preparation before a worker reports ready.

Test changes: the two new modules above; compatibility/safety expectations and startup mocks in `test_query_understanding.py`, `test_intents.py`, `test_compound_reasons.py`, `test_dialogue.py`, `test_stage2_build.py`.

Verification additions: `scripts/evaluate_spelling.py`, `scripts/summarize_spelling.py`, `scripts/verify_spelling.py`; this report and `artifacts/spelling/`. `after-dev.json` and earlier attempt logs are intermediate evidence; **`after.json`, `comparison.json`, `api.json`, `backend.log` and `frontend.log` are the final results**. The pre-change checkpoint is `checkpoint/pre-spelling-20261109` at `a1eb6c1`.

Changes remain local and uncommitted. The final isolated API process reports base commit `a1eb6c1` with changed backend source digest **`9160df18cc7ec64979aa24795647b356c5af5c1a219073878cc0fcfdebd62f7f`**. A commit hash alone cannot identify uncommitted source changes; this digest records the source loaded for those checks.

To repeat the development evaluation on the completed source without replacing the frozen before/after pair:

```powershell
docker exec paulibot_web python -B manage.py shell -c "import sys,runpy; sys.argv=['evaluate_spelling','--label','recheck']; runpy.run_path('scripts/evaluate_spelling.py',run_name='__main__')"
```

## Remaining limits and stop point

- This is synthetic **development-set** evaluation using source questions/configured examples, not held-out paraphrases, broad multilingual certification, or a general language spelling benchmark.
- Spacing is still the weakest tested perturbation. Repairs that would consume known words are refused. Multiple severe errors, unknown languages and real-word substitutions are not universally recoverable.
- A corpus-derived vocabulary is not a complete dictionary. New ordinary words may be ambiguous; new source words enter the cache after worker restart. Stored answer freshness remains governed by existing database/source retrieval, with no new answer cache.
- The complete snapshot is prepared by the Docker/Gunicorn worker initialization path. Standalone utilities or alternative server entry points must explicitly call `prepare_vocabulary()` before serving equivalent requests; pure utility calls otherwise use the configuration-only fallback. The evaluation/API scripts do this explicitly. A separately launched host `runserver` was not validated.
- Misspelled names require confirmation. A valid literal name can itself be the unintended result of a typo; close known-name collisions are guarded, but no text-only mechanism can infer every such intention. Zero wrong-person cases here is not a universal guarantee.
- Confirmation buttons submit complete questions. A bare `yes` does not choose among tied spelling alternatives; select a choice or retype the intended question.
- Existing institutional source conflicts and name-format differences require institutional review. This change does not establish that every stored website record is current or correct.
- No shared Gunicorn worker reload or deployment was performed. **The currently running service can still serve the previous Stage 2 code until the backend is deliberately restarted.** The API validation above used a separate Docker process loading the changed source; it is not a claim that the shared HTTP service was updated.

The **0.45 cutoff, embedding model/dimensions, providers, grounding thresholds, database models/data and dependencies remain unchanged**. No Stage 3 calibration, model training, infrastructure work or deployment follows this report.
