# Compound introduction and enrollment-rationale fix

Verified November 7, 2026, against the active Docker/PostgreSQL backend and the Vite API proxy.

## Reproduced issue

Exact input: `TELL ME ABOUT SPUS AND WHY SHOULD I ENROL`.

Before the fix, the API decomposed it into `TELL ME ABOUT SPUS?` and `WHY SHOULD I enroll?`, then returned two insufficient-information responses with zero sources. The active database already contained both the SPUS overview (FAQ 151) and the choice rationale (FAQ 116). No ingestion was needed.

The lowercase compound question returned the introduction but missed the rationale. `TELL ME ABOUT SPUS` alone failed. `Why should I enroll at SPUS?` also failed, while the existing pronoun form `Tell me about SPUS and why should I choose it?` already worked. These baselines are recorded in `PAULA_COMPOUND_REASON_BEFORE.json`.

## Root causes and changes

1. **Capitalization incorrectly created evidence constraints.** Grounding interpreted uppercase question words such as TELL, ME, and ABOUT as acronyms that must appear in source text. Exact FAQ subject/predicate matching now runs before this acronym check, after department/year/role/faculty safeguards. On hybrid paths, uppercase stopwords are excluded from acronym detection; unknown abbreviations still require source support.
2. **The second clause omitted its subject.** The dependency binder previously recognized a small set of application actions. It now recognizes bounded rationale requests, extracts the explicit object of the prior user clause, and supplies required grammatical prepositions. The exact request resolves to `TELL ME ABOUT SPUS?` and `WHY SHOULD I enroll at SPUS?`.
3. **Recommendation predicates did not match.** Shared FAQ canonicalization now aligns `why enroll at`, `why study at`, and `why attend` with the rationale for choosing the same subject. It retains the full subject, dates, qualifiers, negation, and unhandled modalities. The answer still comes exclusively from the matching stored FAQ, not generated persuasion or institutional facts.
4. **Pronouns needed the same grammatical binding.** Bounded reason references such as `choose it` and `study there` reuse the explicit prior object; `study there` resolves to `study at SPUS`, preserving the required preposition. This mechanism is used for both compound parts and multi-turn follow-ups.

No SPUS facts or response paragraphs are hardcoded in the resolver. Fictional-subject tests cover an academy, library, scholarship, and policy. Previous assistant answers do not establish facts or replace the user's named subject.

An explicitly different institution is preserved. Missing prior subjects and ambiguous coordinated antecedents require clarification rather than guessing. If one part has supported evidence and another does not, the supported part remains visible with its own citations. Conflicting rationale records remain conflicts and are not overwritten.

## Verified result

The exact original input now returns a friendly opening, followed by:

- The overview quoted from `[About SPUS.txt] What is SPUS?`.
- The stored choice rationale quoted from `Why choose SPUS?`.
- Two citations, attributed to parts 1 and 2 separately.

The existing source rationale includes faith-based education, academic excellence, campus life, and the alumni network. This work verifies retrieval/faithfulness to the stored text; it does not independently certify the currency of those institutional claims.

The response was checked through **`http://localhost:5173/api/chat`**: HTTP 200, two sources, both expected excerpts, no insufficient-information text, and `saved: false`. Evidence: `PAULA_COMPOUND_REASON_FRONTEND.json`.

## Tests and measurements

- **368 automated regression tests passed**, including compound parsing, About-SPUS ingestion/lookup, listing retrieval, personnel consistency, grounding, conversational context, dialogue, provider/runtime failure handling, enrollment, web ingestion, admin assets, and session privacy. Deliberately simulated failures produced expected warning logs; the suite completed successfully.
- **17 live guest checks passed**: the reported input, capitalization variants, single overview/rationale requests, pronouns, preserved program retrieval, compound personnel, enrollment clarification, unavailable future-year/unknown-institution information, unknown acronyms, and a multi-turn overview → rationale → enrollment conversation.
- Negative, future-date, comparison, personal-audience, explicit-subject, ambiguous-antecedent, source-conflict, missing-knowledge, and faculty-body safeguards have regression coverage.
- Exact backend request: 384.20 ms before, 146.64 ms after in the recorded individual samples. The frontend-proxy sample was 689.10 ms after readiness. These are individual local observations, not p50/p95 measurements or deployment guarantees.
- The final web-only activation reached all three workers ready after about 60 seconds. Model readiness/startup is separate from those request observations.
- The 0.45 retrieval cutoff, 384-dimensional embeddings, providers, conversation isolation, and source wording were preserved. No additional LLM call is required for the two unique matching FAQ entries.
- Knowledge, stored embeddings, conversations, and historical message fingerprints are unchanged: `PAULA_COMPOUND_REASON_INTEGRITY.json`.
- `git diff --check` passed. No frontend build was necessary because frontend application source was unchanged.

## Modified files

| File | Change |
| --- | --- |
| `chatbot/compound_queries.py` | Extract explicit overview objects; bind bounded reason/action references with grammatical prepositions |
| `chatbot/conversation_context.py` | Reuse dependency binding consistently for compound and follow-up requests |
| `chatbot/query_normalization.py` | Preserve-object rationale predicate equivalence |
| `chatbot/grounding.py` | Case-safe acronym validation with existing grounding safeguards |
| `chatbot/test_compound_reasons.py` | Resolver, grounding, source-conflict, partial-answer, and PostgreSQL-backed regression tests |
| `scripts/verify_compound_reasons.py` | Live API variants, controls, multi-turn and integrity verification |
| `scripts/verify_compound_reason_frontend.mjs` | Exact query through Vite after readiness |

Artifacts: `PAULA_COMPOUND_REASON_BEFORE.json`, `PAULA_COMPOUND_REASON_AFTER.json`, `PAULA_COMPOUND_REASON_FRONTEND.json`, `PAULA_COMPOUND_REASON_INTEGRITY.json`, `PAULA_COMPOUND_REASON_READINESS.json`.

## Limits

The resolver supports bounded grammatical dependencies and unambiguous user-provided subjects. Other elliptical wording can still require clarification. It does not use assistant prose as evidence, infer a new institutional fact, perform live scraping, or promise that every paraphrase is understood. No accounts, knowledge records, embeddings, schema, or database volumes were changed by this fix.
