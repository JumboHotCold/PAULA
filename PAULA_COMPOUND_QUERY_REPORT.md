# PAULA multi-part conversational retrieval implementation

Implementation and verification: 28 October 2026.

## Verified starting state and root cause

Both requested personnel records exist in the active Docker PostgreSQL database:

| Request | Stored website evidence | WebResource ID |
| --- | --- | ---: |
| ICT Director | Engr. Arnold A. Magalona — Director, Information & Communications Technology Systems and Services | 86 |
| CEIT Dean | Dr. Karen T. Plaza — Dean, College of Engineering and Information Technology, Graduate School Faculty, Program Chair | 90 |

The duplicate section cards are retained as supporting provenance. These are
stored website snapshots, not independent confirmation of current appointments.
Neither record was created or changed for this task.

The original failure was reproducible in the actual code:

1. `normalize_query()` preserved “Who is the ICT Director and CEIT Dean?” as one
   question. The conversation resolver returned one standalone query.
2. Personnel lookup required both requested roles and department constraints to
   describe one personnel card. Neither individual card satisfied that query.
3. Hybrid retrieval received the same combined query. `eligible_evidence()`
   rejected both individual cards because neither substantiated both roles.
4. The response boundary correctly rejected unsupported evidence and abstained.
   The missing behavior was independent question planning, not a missing fact
   or a reason to lower the retrieval threshold.
5. The existing comparison loop supported some two-query requests, but an error,
   ambiguity, source conflict, or rejected selection in a later query could
   return early and discard previously supported answers.
6. Enrollment clarification happened before decomposition, so a question naming
   two student categories could incorrectly trigger a single-category prompt.

## Implemented pipeline

`chatbot/compound_queries.py` is a reusable, deterministic planner. It recognizes
clear independent question clauses, coordinated entity slots, shared role noun
phrases, and combinations of those forms. It uses grammatical structure and the
existing interchangeable public entity vocabulary rather than institutional
name/answer constants.

Examples resolved before retrieval:

| Input | Independent retrieval requests |
| --- | --- |
| Who is the ICT Director and CEIT Dean? | Who is the ICT Director? / Who is the CEIT Dean? |
| Who are the deans of CEIT and CHS? | Who are the deans of CEIT? / Who are the deans of CHS? |
| What are the requirements for freshmen and transferees? | Requirements for freshmen / requirements for transferees |
| Where are the Registrar and Finance offices? | Registrar offices / Finance offices |
| What scholarships are available, and how do I apply? | Available scholarships / how to apply for scholarships |
| Who is the University President, and what office handles enrollment? | University President / office handling enrollment |

Conjunctions inside known entity names, quoted titles, and parentheses remain
intact. English `at` remains a preposition; supported Filipino `at`, `pati`, and
`tsaka` can express coordination. Relational questions such as “the relationship
between CEIT and CHS” are not converted into two unrelated factual requests.
Shared dates, qualifiers, and negation are retained in supported expansions.
Unknown future resources can use grammatical `for/about/of` slots without
adding a new knowledge-domain branch.

Each planned part passes through the existing single-question orchestration:
enrollment clarification, navigation routing, structured lookup or hybrid RAG,
source-conflict detection, evidence grounding, optional evidence-ID selection,
and source-text rendering. The raw cosine cutoff remains **0.45**. No knowledge
model, embedding model, vector schema, or provider architecture was replaced.

`PauliBotLogic._process_parts()` combines the results in numbered sections.
Each source receives a matching citation number, part number, and resolved query.
The frontend source accordion displays the citation number. The API also returns
an additive `answer_parts` array with query, status, and source indices.

Statuses distinguish `ok`, `no_match`, `clarification`, `ambiguous`, `conflict`,
and `unavailable`. A failure affects its own section; independently verified
answers remain present. Neither history nor another part's evidence can fill
a missing answer. Provider-authored factual prose remains disallowed.

For two campus destinations, the response offers a directions button for each.
The frontend currently supports one map destination at a time. The combined
response therefore does not fire two competing map actions or invent office
coordinates; its map sources refer to the existing curated campus directory.

## Conversation, isolation, and resource bounds

- Compound processing occurs before enrollment-category clarification. Each
  part retains its own audience, institution, role, dates, and constraints.
- Supported English, Filipino, and Taglish follow-ups resolve independently.
  Qualified references such as a college's dean retain that subject together.
- A signed context token stores the resolved compound user intent. It does not
  retain only the final successful part or an incomplete “How about …” fragment.
  Existing owner, tab/thread, latest-message binding, and expiry remain intact.
- Explicit entity follow-ups may select the one compatible prior part. Plural
  attribute references can re-fetch several subjects. Singular pronouns,
  repeated-role references, or numbered steps after multiple plausible subjects
  ask for clarification rather than choosing the last one.
- Unrelated explicit questions continue to switch topics. Assistant prose is
  never used as a factual source. Bounded user-history replay remains supported.
- Clear requests are limited to **four distinct parts** and **2,000 input
  characters**. Excessive or incomplete decompositions clarify before retrieval.
  Repeated identical questions collapse to one retrieval request.
- Parsing makes **zero LLM calls**. A compound message has a shared allowance of
  **at most one evidence-selector API request**, including provider fallback
  attempts. Once spent, already gated evidence supplies the conservative local
  selection. Existing single-question provider fallback remains compatible.
- Queries run sequentially against the existing public knowledge sources. No
  conversation data is cached globally, no new services are required, and no
  additional accounts, dependencies, or migrations were introduced.
- An authenticated compound message is persisted once as one exchange in its
  owned conversation. Guest processing never saves the component requests or
  the aggregated response as chat history.

## Verification

### Automated tests and frontend build

**196 backend tests passed**, including **43 new compound-query tests**. Django
system checks reported no issues. Existing enrollment, navigation, crawling,
grounding, personnel consistency, conversation, and privacy tests were rerun.

```powershell
docker exec paulibot_web python -B manage.py test chatbot.test_compound_queries chatbot.test_retrieval_consistency chatbot.test_grounding chatbot.test_intents chatbot.test_web_crawler chatbot.test_enrollment chatbot.test_conversation_context chatbot.test_chat_sessions --verbosity 1
```

The new tests cover all six requested query structures, future named topics,
multilingual coordination, contextual lists, role comparisons, topic switches,
shared constraints, quoted names, ambiguous conjunctions/references, duplicates,
complexity bounds, missing evidence, source conflicts, retrieval exceptions,
per-part attribution, selector-call limits, signed context isolation, explicit
guest mode with an authenticated identity, and one-save authenticated grouping.
Fixtures use fictional facts and mocked external providers; these are contract
checks rather than factual certification of the entire SPUS knowledge base.

`npm.cmd run build` passed using the existing frontend dependencies. Vite emitted
its large-chunk warning. No dependency or execution-policy changes were made.

### Before/after active PostgreSQL benchmark

Runner: `scripts/evaluate_compound_queries.py`.
Artifacts: `PAULA_COMPOUND_BASELINE.json`, `PAULA_COMPOUND_AFTER.json`, and
`PAULA_COMPOUND_COMPARISON.json`.

The same seven fixed cases were exercised before and after the implementation.
Each has one initial sample and three warm samples. Providers are disabled,
embedding writes are disabled, and PostgreSQL runs in a read-only transaction.

| Case | Before median ms | After median ms | After outcome |
| --- | ---: | ---: | --- |
| ICT Director and CEIT Dean | 175.07 | 172.46 | Both source-grounded answers |
| CEIT and CHS deans | 130.48 | 153.99 | Both source-grounded answers |
| Freshmen and transferee requirements | 0.56 | 12.78 | Both Registrar answers |
| Registrar and Finance destinations | 0.51 | 1.97 | Two supported map choices |
| Filipino two-role question | 132.59 | 141.92 | Both source-grounded answers |
| ICT Director plus unavailable Mars director | 59.20 | 164.53 | ICT answer retained; missing part identified |
| ICT Director plus conflicting PBMO claim | 130.00 | 164.23 | ICT answer retained; conflict identified |

Targeted response-fragment smoke checks increased from **1/7 to 7/7**. The old
office-selection prompt contained both office names and therefore passed that
one weak smoke check; it did not supply two independent answers. All seven
baseline responses had zero displayed evidence sources.

The after run returned all **12 expected supported parts out of 12**, across
14 total requested parts, with the missing and conflicting parts correctly left
unanswered. Two of those supported parts are curated map destinations, not
vector-retrieved textual office locations. This small diagnostic corpus is not
a general retrieval precision/recall measurement or an institution-wide accuracy
claim. Tests separately cover additional domains and negative cases.

These timings compare different outcomes: fast baseline clarification or
abstention versus successful independent retrieval after the change. They do
**not** establish a general speedup. Additional supported parts add retrieval
work. Lazy MiniLM startup remains expensive: the first vector-search
sample in the missing-knowledge case took tens of seconds in the after runs;
the final warm median for that case was approximately 165 ms. This existing cold-model cost
is excluded from the warm medians and remains a deployment/performance concern.

```powershell
docker exec -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e HF_HUB_DISABLE_PROGRESS_BARS=1 paulibot_web python -B manage.py shell -c "import runpy,sys;sys.argv=['evaluate_compound_queries.py','--output','PAULA_COMPOUND_AFTER.json'];runpy.run_path('scripts/evaluate_compound_queries.py',run_name='__main__')"
```

### Running application and integrity

`scripts/verify_compound_queries_http.py` exercises the Vite proxy and active
Docker backend in guest mode. The JSON result artifact records timings,
responses, per-part statuses, sources, and `saved: false`. It tests the six
requested examples, Filipino phrasing, partial missing/conflicting answers,
focused follow-ups, ambiguous pronouns, and guest-tab isolation.

All **12 live checks passed** against the final active version. The two-role,
two-dean, two-audience, two-map, and Filipino cases each produced two supported
parts. The scholarship case produced a supported scholarship answer and a
`no_match` application-procedure part; missing and conflicting personnel parts
also retained the independently supported ICT answer. The mixed personnel/office
case returned two cited excerpts, with the office-scope limitation noted below.

The live median was **315.73 ms** across the 12 requests. The original two-role
request took **881.65 ms** in this run. The maximum was **38,279.71 ms**, for the
scholarship case on a cold vector-model path. These measurements include real
backend/proxy startup and any selector behavior; they are not warm retrieval-only
timings or a concurrency benchmark.

Final results are recorded in `PAULA_COMPOUND_LIVE_CHECKS.json` and
`PAULA_COMPOUND_INTEGRITY.json`. Complete row fingerprints before and after the
live checks match, including embedding arrays and historical chat contents:
**12 StaffMember, 134 FAQ, 476 WebResource, 139 Conversation, and 176 ChatHistory**
records. All live guest responses reported `saved: false`. No institutional
facts, existing history, or manually corrected personnel data were changed.

```powershell
python -B scripts/verify_compound_queries_http.py
```

This live runner expects Vite at `http://localhost:5173` and the configured Docker
backend. The existing frontend proxy continues to target host port 8080.

## Modified files

| File | Change |
| --- | --- |
| `chatbot/compound_queries.py` | New bounded, domain-independent coordination planner |
| `chatbot/conversation_context.py` | Multi-part resolution, comparisons, dependent references, and multi-turn intent |
| `chatbot/query_normalization.py` | Canonical plural role forms |
| `chatbot/intents.py` | Preserve regular plural query words rather than treating them as spelling errors |
| `chatbot/context_tokens.py` | Optional in-memory answer status/parts metadata; signed token format unchanged |
| `chatbot/logic.py` | Per-part orchestration, partial success, numbered attribution, map choices, and shared selector budget |
| `chatbot/views.py` | Additive `answer_parts` response metadata |
| `frontend/src/components/Dashboard.jsx` | Display citation indices in existing source cards |
| `chatbot/test_compound_queries.py` | 43 new regression tests |
| `scripts/evaluate_compound_queries.py` | Fixed provider-free before/after benchmark |
| `scripts/verify_compound_queries_http.py` | Live compound/guest verification |
| `PAULA_COMPOUND_QUERY_REPORT.md` | This implementation report |
| `PAULA_RESPONSE_GROUNDING.md`, `PAULA_CONVERSATIONAL_RAG.md` | Pointers to the multi-part extension |

Generated artifacts are the baseline, after, comparison, live-check, and integrity JSON files
named above. Earlier dirty files remain in the checkout; this table describes
the current implementation scope. No institutional fact, CSV record, manually
corrected personnel record, account, database schema, or historical chat was
intentionally changed.

## Remaining limitations

- Deterministic parsing handles clear grammar, not every possible coordination
  or pronoun construction. Unknown compound names and ambiguous relationships
  remain atomic for conservative grounding or require clarification. Extending
  the public vocabulary can protect additional formal names without domain-
  specific factual rules.
- Decomposition cannot create missing institutional evidence. Scholarship
  application details, office responsibility, and other clauses can still be
  unresolved when the verified knowledge lacks a suitable supporting entry.
- The live mixed-topic office query returns a relevant stored freshman procedure
  excerpt listing its offices, rather than a concise general office-responsibility
  answer. That source's audience scope remains explicit; no universal enrollment
  responsibility policy is inferred from it.
- Existing personnel/source conflicts remain institutional review tasks. This
  implementation does not infer current appointments or silently correct names.
- Comparisons present independently grounded facts; they do not invent a
  comparative judgment. Complex nested conditions and inferred cross-document
  conclusions require clarification or further work with labeled examples.
- The map continues to support one selected destination at a time; multi-part
  map requests provide choices rather than a multi-stop route.
- The existing chat-history schema/serializer persists response text rather
  than structured source cards or `answer_parts`. Live responses have numbered
  source attribution; reopening a stored exchange does not restore that metadata.
  This implementation does not add a history-schema migration.
- Cold-worker/model loading, production concurrency, and comprehensive
  multilingual precision/recall require broader profiling and evaluation.
  The small benchmark does not justify changing the retrieval cutoff.
