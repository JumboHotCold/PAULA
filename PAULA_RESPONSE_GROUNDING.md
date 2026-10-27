# PAULA Response Grounding Changes

> Multi-part queries update (28 October 2026):
> [PAULA_COMPOUND_QUERY_REPORT.md](PAULA_COMPOUND_QUERY_REPORT.md) describes
> bounded decomposition, independent retrieval, partial answers, citations,
> conversational compatibility, measurements and remaining limits.

> Retrieval consistency and CSV provenance update (28 October 2026):
> [PAULA_RETRIEVAL_CSV_REVIEW.md](PAULA_RETRIEVAL_CSV_REVIEW.md) records shared
> normalization, aliases, deduplication, safe fallbacks, conflict handling,
> read-only CSV review, regression results and measured limitations.

> Latest implementation: [PAULA_CONVERSATIONAL_RAG.md](PAULA_CONVERSATIONAL_RAG.md)
> describes the shared conversational resolver, signed guest/authenticated intent
> continuity, cross-domain tests, measured retrieval results and remaining limits.

## Continuing-student clarification fix — 27 October 2026

The exact reported guest exchange succeeded when its two-message clarification
pair was supplied. Source inspection identified two context-loss paths:
authenticated requests without a conversation ID discarded that pair, and React
retained returned conversation IDs only for `STUDENT` users. These findings
identify reproducible code paths; the original browser request was not captured.

- `frontend/src/App.jsx` now retains the conversation ID whenever the API confirms
  that the message was saved, including administrative testing sessions.
- `chatbot/views.py` accepts bounded clarification context for authenticated
  requests without a conversation ID. An owned, active conversation's persisted
  history takes priority. Context remains routing data, never factual evidence.
- `chatbot/intents.py` defines the three actual enrollment button labels centrally.
  Those exact labels recover enrollment-procedure intent when an older client
  loses context. Arbitrary personal statements still require pending context;
  a pending documents question keeps its document-request intent.
- `chatbot/enrollment.py` retrieves the unique matching Registrar office FAQ by
  student category and procedure-versus-documents topic. This supported path
  loads neither MiniLM nor an LLM, and does not depend on cosine thresholds.
  Missing, conflicting, non-office or wrong-category evidence is not substituted.
- Source references such as `(Document URO-PR-016)` are removed when classifying
  the FAQ subject; they do not establish that a procedure is a requirements list.
  College/higher-education and enroll/enrolling terminology is normalized.

The PDF's second physical page was visually rechecked against the existing OCR.
It contains **Academic Advising → Assessment of Fees → Payment → Encoding &
Validation**, assigned respectively to the Dean/Program Chair, Student Accounts,
Cashier and Registrar's Clerk. The printed document code is `URO-PR-0016`; the
existing FAQ uses the shortened `URO-PR-016`. No source PDF, knowledge JSON or
database content was changed for this fix.

**81 regression tests passed**, including explicit category questions, the exact three button labels with
and without history, both broad enrollment question variants, procedure/document
separation, and authenticated requests with mocked persistence. No accounts were
created. The frontend production build passed with the existing bundle-size and
Node deprecation warnings.

```powershell
docker exec paulibot_web python -B manage.py test chatbot.test_grounding chatbot.test_intents chatbot.test_web_crawler chatbot.test_enrollment --verbosity 1
```

Direct PostgreSQL checks returned all three Registrar procedures and confirmed
the embedding model remained unloaded. All **17 live guest frontend API requests
passed**, covering the full two-turn flow for both broad enrollment questions,
the three controls with missing history, document requests, direct old-student
enrollment, and president/CEIT regressions. Live frontend API check results are
recorded in
`knowledge_base/office_documents/extracted/enrollment_flow_verification_2026-10-27.json`.
Authenticated HTTP requests using a real login and visual browser interaction
were not tested; the authenticated API path was exercised with mocked accounts
and storage, without creating replacement users.

> 27 October 2026 update: official website crawling and exact personnel lookup
> are now implemented and live-tested. See
> [PAULA_WEBSITE_KNOWLEDGE_UPDATE.md](PAULA_WEBSITE_KNOWLEDGE_UPDATE.md)
> for the administrator-page refresh, 27-entry CEIT roster, president typo fix,
> source snapshots, PostgreSQL ingestion and current verification results.

## Problem

A CEIT faculty question returned a school calendar. Source inspection found two
general failure mechanisms: relevance thresholds were applied after large
keyword/authority distance adjustments, and the direct fallback could grant
positive scores to FAQs without enough question support. Without the original
request trace, these findings do not prove which provider/fallback produced that
particular recorded answer.

## Response policy

The factual response path now uses **retrieval → relevance gates → evidence
selection → stored excerpts → citations**, with abstention when evidence is
insufficient.

- Raw cosine distance is checked before authority ranking. Existing MiniLM
  vectors remain compatible; no migration or full re-embedding is required.
- Lexical candidates supplement semantic candidates for college acronyms.
- College, personnel, role, topic, audience, and requested-year checks reject
  unrelated matches. A program catalog or dean's office is not a faculty lineup.
- Faculty records require named personnel evidence and appropriate role/scope.
  Mixed-college chunks are refused rather than attributing adjacent names to the
  wrong college. Accepted faculty information is labeled potentially incomplete
  or out of date.
- LLMs select existing evidence IDs through a strictly validated JSON contract.
  Model-authored factual prose is not rendered. Invented IDs, extra answer fields,
  malformed JSON, and invalid types are rejected.
- Responses quote stored answers and cite only displayed entries. Source language
  is preserved instead of generating an unverified translation.
- Retrieval runs once. Provider failures reuse eligible evidence instead of
  repeating search or returning an unrelated default FAQ.
- One supported entry, faculty evidence, greetings, and missing-evidence responses
  do not need an LLM call.
- Groq/OpenAI requests have bounded timeouts and no automatic retries. Startup no
  longer probes multiple models. Gemini selection is attempted when its client is
  available and earlier providers fail.
- Chat no longer automatically scrapes and trusts the first website search hit.
  The existing explicit website ingestion command remains available.
- Old assistant responses are not used as factual evidence. Vague conversational
  follow-ups may require the user to restate the relevant subject.
- Retrieval failure is reported as a temporary availability issue, separately
  from absent knowledge. Logs avoid full student questions and exception details.

This intentionally prioritizes evidence fidelity over free-form conversational
paraphrasing. It reduces opportunities for the model to invent factual content,
but cannot establish that stored institutional material is accurate, complete,
current, or correctly associated with every question. The heuristic gates can
also reject valid paraphrases. This is not a zero-hallucination guarantee.

## Changed files

| File | Responsibility |
|---|---|
| `chatbot/grounding.py` | Pure relevance gates, selection validation, excerpt/citation rendering |
| `chatbot/rag.py` | Cosine and lexical candidate retrieval, followed by eligibility/ranking |
| `chatbot/logic.py` | Single-retrieval response orchestration and provider selection/fallback |
| `paulibot/settings.py` | Configurable cosine threshold and Groq model |
| `chatbot/test_grounding.py` | Offline regression tests using fictional fixtures and mocked providers |
| `scripts/evaluate_grounding.py` | Read-only PostgreSQL retrieval smoke evaluation |

The grounding implementation did not replace institutional knowledge entries,
account records, or database schemas. Later runtime activation added a dedicated
model-cache volume while preserving the existing PostgreSQL container/data.

## Configuration

`RAG_MAX_COSINE_DISTANCE` defaults to `0.45`. It is a conservative initial cutoff,
not a calibrated probability or a benchmarked optimum. Tune it using labeled
SPUS questions, tracking both unsupported answers and unnecessary refusals.

`GROQ_MODEL` defaults to `llama-3.3-70b-versatile`. Provider/model availability must
be verified for the actual account. API selection was tested with mocks, not
live paid generation calls.

Keep configuration and credentials in environment configuration; do not commit
secrets. Compose must expose optional variables, or the Django configuration must
otherwise read them, before changes to those variables affect the container.

## Verification

Initial verification passed **25 offline regression tests** and Django system
checks returned no issues when this workspace's changed modules/settings were
loaded in the existing web container's process memory. Syntax checks also passed
for all six changed/added Python files.

The initial running image lacked the OpenAI SDK. The subsequent complete runtime
audit updated the image against `requirements.txt`, installing the missing
OpenAI, Psycopg 3, and ReportLab dependencies. The active runtime now initializes
both Groq and OpenAI clients, and `pip check` reports no broken requirements.
External provider quotas and live paid failover are separate from SDK readiness.
See [the complete runtime audit](PAULA_RUNTIME_UPDATE_AUDIT.md).

The offline suite covers the reported mismatch, wrong colleges, program catalogs,
faculty-room false positives, missing years/roles/acronyms, provider outages,
malformed/invented model output, citation selection, and missing knowledge.

Read-only checks using the existing PostgreSQL database and cached MiniLM model
showed:

| Question | Retrieval outcome |
|---|---|
| CEIT faculty lineup, English and Filipino | No eligible roster; abstain |
| SPUS programs | Program-related entries accepted |
| Scholarships | Scholarship FAQs accepted |
| Incoming freshman enrollment procedure | Registrar freshman enrollment procedure accepted |
| PBMO office hours | PBMO hours entry accepted |
| School calendar | Calendar entry accepted |
| Exact enrollment dates for 2099 | No eligible evidence; abstain |
| President of Mars | No eligible evidence; abstain |
| Tuition amount | No eligible evidence with the checked data/cutoff; abstain |

This small smoke set is not a quantitative accuracy, recall, latency, or load
benchmark. No accepted roster does not prove that the entire database lacks
faculty information; eligible evidence may also be excluded by thresholds,
chunking, or candidate limits.

Run these commands only after confirming that the web container serves this
checkout:

```powershell
docker exec paulibot_web python -B -m unittest chatbot.test_grounding -v
docker exec paulibot_web python -B scripts/evaluate_grounding.py
```

The first command uses mocks and creates no test database. The second refuses
SQLite, disables embedding writes, requires a cached model, and executes database
queries inside a PostgreSQL read-only transaction. It makes no LLM calls.

## Runtime activation — October 27, 2026

During the initial verification, `paulibot_web` mounted:

```text
C:\Users\ADMIN\OneDrive\DEX CAPSTONE 2026\paulibot → /app
```

The web service has now been recreated to mount the edited workspace:

```text
C:\Users\ADMIN\Documents\GitHub\paulibot
```

The earlier tests used process-memory module injection and did not activate the
website. The live activation now uses this checkout directly. The existing
environment file is reused in place; its credentials were not copied into this
workspace. The PostgreSQL container was preserved, and startup reported no
migrations to apply. Existing MiniLM files were preserved in a new dedicated
`paulibot_model_cache` volume.

To start this workspace's backend with the same existing configuration:

```powershell
.\scripts\start_workspace_backend.ps1 -EnvFile "C:\Users\ADMIN\OneDrive\DEX CAPSTONE 2026\paulibot\.env" -DjangoDebug true
```

The launcher validates the workspace bind mount, PostgreSQL selection, and debug
value, and recreates only the web service. Its explicit local-development debug
setting avoids an inherited host `DEBUG=release` value that Django cannot parse.
It restores its temporary process setting on exit.

Clarification/map requests no longer import Sentence Transformers/PyTorch at
startup. The first retrieval imports them lazily; Gunicorn has a 120-second
worker timeout to accommodate cold loading. Generic enrollment follow-ups also
retain the assistant's implicit SPUS institution context rather than missing a
matching procedure by a narrow vector cutoff.

Backend address: `http://127.0.0.1:8080`. Refresh an already-open chat page so its
JavaScript includes the guest clarification payload. Do not reset the database
or use `docker compose down -v`.

## Knowledge maintenance

If PAULA should answer a current CEIT faculty lineup, supply an institutionally
verified roster with explicit college, names, roles, and effective date, and ingest
it through the existing office ingestion workflow. Do not invent personnel or
infer a complete lineup from a dean or a programs page.

## Enrollment clarification, navigation, and typo handling

The follow-up implementation adds `chatbot/intents.py` and
`chatbot/test_intents.py`, and updates the chat API, active React client, and
legacy chat template's transient guest clarification handling.

- Broad college enrollment/procedure/requirements requests ask whether the user
  is a freshman, transferee, or old/continuing student. Basic-education and
  graduate-level requests are not automatically assigned to those categories.
- A short category reply resolves only the most recent explicit clarification.
  Retrieval then requires the matching audience and question type. A list of
  required documents does not substitute for an enrollment procedure.
- Authenticated users use their own saved thread context. Guests send only the
  last two messages for bounded clarification routing; that context is not saved
  as guest chat history or accepted as factual evidence.
- Map activation requires physical-navigation intent and exactly one known map
  destination. Directions, navigation, location phrases, and Filipino location
  requests work without requiring the word “where.” Online, document, payment,
  and other informational requests do not automatically open the map.
- Missing or multiple destinations produce clarification. Generic “dean,” the
  pronoun “it,” and incidental substrings are not mapped to arbitrary offices.
- Server navigation IDs are validated against frontend node IDs. The map now
  gives exact server node IDs priority over fuzzy alias resolution.
- Common single-edit domain typos and adjacent transpositions are normalized
  before routing/retrieval, for example `enorll → enroll` and
  `registar → registrar`. Ambiguous spellings are not guessed. Acronyms and
  identifiers are preserved; the correction vocabulary contains no personnel.
  This is bounded domain normalization, not guaranteed understanding of all
  misspellings or languages.

The original user message remains the saved/displayed text; normalization is
internal. Typo correction and clarification cannot supply missing institutional
facts. The original runtime checkout mismatch has now been resolved as described above.

The first Registrar recheck used visual comparison. A subsequent automated OCR
run covered all 16 pages of the four Registrar/PBMO PDFs; see
`knowledge_base/office_documents/extracted/ocr_review_2026-10-27/REVIEW_REPORT.md`.
Source discrepancies were documented without replacing the knowledge JSON/database.

Follow-up verification passed 46 combined regression tests, Django system
checks, the frontend production build, and a syntax check of the legacy chat
JavaScript. In read-only PostgreSQL probes, all three short replies (`freshman`,
`transferee`, `old student`) selected their respective Registrar procedure after
the broad enrollment clarification. This verifies the checked flows, not all
possible phrasings, browser interactions, or typos.

```powershell
docker exec paulibot_web python -B manage.py test chatbot.test_grounding chatbot.test_intents --verbosity 1
```

The original 46-test verification used process-memory injection. After runtime
activation, all 47 tests passed directly in the active container, and the actual
HTTP endpoint at `http://127.0.0.1:8080/api/chat` was checked with the exact
question `How do I enroll?` followed by each category. The first response asked
for the category; all three follow-ups returned their respective Registrar
procedures with `saved: false` for guests. The served `/chat/` page was also
checked for the updated guest clarification JavaScript. No accounts or
replacement student records were created for verification.
