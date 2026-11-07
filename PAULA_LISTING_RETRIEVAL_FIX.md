# Short-question and scoped FAQ retrieval fix

Verified November 7, 2026, against the active Docker/PostgreSQL backend and Vite API proxy.

## Reproduced failure

`What programs are offered?` returned insufficient information with no sources. The full `What programs are offered at SPUS?` returned the catalog. This was a retrieval failure, not absent source data.

The active database contains a standalone program catalog FAQ (record 146) attributed to the Registrar, plus other program records. Its contents and embedding were preserved.

Trace of the short request:

1. Dialogue routing classified it as a knowledge request; conversation resolution left it standalone.
2. Shared lexical terms correctly resolved to `program`.
3. Exact FAQ matching did not equate the short question with the source question ending in `at SPUS`.
4. MiniLM retrieval's nearest FAQ distance was **0.5588**, outside the existing **0.45 maximum cosine distance**. Other catalog candidates were also outside the cutoff.
5. Grounding accepted the catalog's subject, but no vector result survived the distance filter. The response therefore abstained before generation.
6. Suggested questions used a separate public FAQ catalog. Their appearance did not mean the answer pipeline had accepted any evidence.

All four knowledge-model embedding coverage checks reported zero missing embeddings. No ingestion or regeneration was required. Details: `PAULA_SHORT_RETRIEVAL_DIAGNOSIS.json` and `PAULA_PROGRAM_RETRIEVAL_BEFORE.json`.

## Implemented behavior

- A deterministic, source-backed grammatical matcher recognizes equivalent listing requests before vector search: e.g. `What … are offered?`, `Which … are available?`, `What … does SPUS offer?`, `List …`, and supported Filipino/Taglish forms.
- It reuses shared lexical aliases, including courses/programs, rather than inserting a fixed answer or a program-specific fallback. Tests cover scholarships, services, facilities, and a fictional future research-grant subject.
- Subject and scope terms must match **equally**, not merely overlap. CEIT, graduate, online, another institution, and other qualifiers are not silently discarded.
- Negative, dated, comparison, completeness, and other constrained forms remain on the existing retrieval path. They do not get broadened into a generic catalog request.
- Complete single-question FAQ entries take precedence over combined labels. If no such match exists, up to four explicit alternate questions in an FAQ label may be considered. Only the matching question supplies the grammatical scope; the full source title and record identity remain attached.
- `matched_question` accompanies an alternate-label result so response-boundary grounding validates the same scope as retrieval. This fixes the separately discovered `What programs are offered at CEIT?` failure without a CEIT-specific answer branch.
- Identical equivalent answers retain supporting provenance. Different answers among equivalent candidate records report conflict and do not reach generation. Literal matches do not hide conflicts among equivalent single-question entries.
- Known grammatical equivalence is accepted consistently during FAQ lookup and grounding, including Filipino inflections. Other department, role, year, faculty, body-presence, and evidence constraints remain in place.
- The **0.45 cutoff, 384-dimensional embeddings, model/providers, source text, authentication, and guest persistence behavior are unchanged**. A unique supported FAQ answer needs neither a new embedding nor an LLM selection call.

## Validation

**271 affected regression tests passed** through Docker's PostgreSQL test database, including query normalization, grounded retrieval, duplicate/conflict handling, contextual follow-ups, topic switches, multi-intent queries, enrollment, dialogue, suggestions, and guest/session isolation.

Warm-request benchmark: the same 16 public questions, repeated three times before and after activation. Ten questions are catalog variants; the other six cover scoped CEIT retrieval, scholarships, enrollment clarification, missing future-year knowledge, an unsupported degree, and a compound personnel query.

| Catalog subset: 10 variants × 3 rounds | Before | After |
| --- | ---: | ---: |
| Supported catalog responses | 9/30 | 30/30 |
| Warm p50 HTTP latency | 247.72 ms | 128.99 ms |
| Warm p95 HTTP latency | 3,096.09 ms | 360.01 ms |

Variants include the exact reported question, the full SPUS wording, alternate English wording, a program typo, Filipino, and Taglish. Success checks require source attribution and multiple expected entries from the stored catalog. This is retrieval success on a small targeted matrix, **not a system-wide factual accuracy score or a production performance guarantee**.

The six other benchmark controls passed after the fix. Live multi-turn checks passed for `What programs are offered at CEIT?` → `How about CHS?` → `How do I enroll?`. The CHS answer did not inherit CEIT's Mining Engineering entry; enrollment still asked for student category.

The exact reported query also passed through `http://localhost:5173/api/chat`: HTTP 200, one source, stored undergraduate catalog, `saved: false`.

The final web-only restart reached three-worker readiness; measured worker wait was about 56 seconds, separately from warm-request latency. PostgreSQL/volumes were preserved. Knowledge, embeddings, conversations, and historical message fingerprints remained unchanged. No dependencies, institutional facts, schema, or frontend files were changed for this task.

## Modified files

| File | Purpose |
| --- | --- |
| `chatbot/query_understanding.py` | Generic, constrained listing signatures |
| `chatbot/rag.py` | Equivalent FAQ matching, bounded alternate-label fallback, provenance/conflict handling |
| `chatbot/grounding.py` | Same equivalence at the evidence boundary; Filipino noun inflections |
| `chatbot/test_listing_retrieval.py` | New pure and PostgreSQL-backed regression cases |
| `scripts/diagnose_short_retrieval.py` | Read-only distance/grounding diagnostics |
| `scripts/benchmark_listing_retrieval.py` | Identical before/after public guest requests |
| `scripts/verify_listing_release.py` | Benchmark controls, live conversation, integrity checks |

Evidence: `PAULA_LISTING_BENCHMARK_BEFORE.json`, `PAULA_LISTING_BENCHMARK_AFTER.json`, `PAULA_LISTING_RETRIEVAL_VERIFICATION.json`, `PAULA_LISTING_DATA_INTEGRITY.json`, and `PAULA_LISTING_READINESS.json`.

## Remaining limits

Matching is deliberately bounded to recognized grammatical forms. Other paraphrases still use existing hybrid retrieval, and ambiguous fragments can require clarification. Strict answer comparison can flag differently written but compatible sources for review. This work verifies faithfulness to stored records, not whether every institutional fact in those records is independently current. The stored catalog describes undergraduate offerings; a request explicitly requiring a complete current catalog across all education levels needs its own sufficiently supported source.
