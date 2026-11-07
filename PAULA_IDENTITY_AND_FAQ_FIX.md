# PAULA introductions and relevant suggested FAQs

Implemented and active in Docker, 4 November 2026.

## Root causes

1. Self-introduction routing recognized a narrow set of complete phrases.
   `who you?` and `tell me about yourself?` reached institutional retrieval.
2. `RAGSearcher.search()` routed any question containing `announcements` to the
   announcements table before checking FAQs. That table had zero active rows,
   although the reported PBMO question had an exact office FAQ: record 127.
3. When suggestion scores were all zero, selection fell back to unrelated
   high-authority office questions. Catalog selection also lacked source-body
   validation and favored some technical procedures over useful office locations.

The original failures are reproduced in `PAULA_IDENTITY_FAQ_BEFORE.json`.

## Behavior now

PAULA recognizes whole-message self-reference grammar including `who you?`,
`who are u?`, `tell me about yourself`, `introduce yourself`, `what are you?`,
`what is your purpose?`, `Sino ka ba?`, and `Pakilala ka naman`. Mixed greetings
are handled. Requests about university personnel or mixed institutional facts
do not get swallowed by the self-introduction route.

The introduction explicitly identifies PAULA as an AI assistant, expands its
name, and explains its scope in ordinary language. It uses a fixed application
description, not an invented institutional answer or a provider call. A pending
task remains intact through the introduction.

Introductions and capability requests can offer:

- **What programs are offered at SPUS?** — requires a supported exact FAQ.
- **How do I enroll at SPUS?** — requires the existing grounded enrollment
  procedures for all three student categories; clicking asks the category.
- **Where is the Registrar office?** — uses the verified existing map action.

These are ordinary related questions, so already-asked entry points disappear.
Required category choices remain available when PAULA asks a clarification.
Other casual replies do not start loading the FAQ catalog.

Institutional follow-ups use concise stored FAQ questions, limited to 110
characters, ranked using the current/resolved query, source category,
responsible office, and existing entity vocabulary. Responsibility metadata
helps rank the office's location above less relevant internal procedures.
Audience, college, year, duplicate-answer and seen-question exclusions remain.

The selector returns fewer than three suggestions when appropriate. It does
not pad zero-relevance results with random FAQs. Legacy headings such as
`What is the courses information?`, document-code headings, multi-question
titles, malformed controls and conflicting matches are excluded.

The public FAQ catalog now includes source bodies for local grounding checks,
plus digests for **all** matching records so excluded duplicates cannot hide a
conflict. Embedding arrays, user accounts and conversation records are not
loaded by this catalog. Personnel identity suggestions require more than an
FAQ claim and are excluded from this selector; typed personnel questions retain
their existing structured retrieval/conflict checks.

The PBMO question now checks exact evidence and conflicts before announcement
listing. An empty announcement result can continue through existing hybrid
retrieval. Active announcement requests still work. No similarity cutoff was
relaxed.

## Verified examples

`who you?` and `tell me about yourself?` return the introduction and the three
supported entry points above. After the program button is used, only enrollment
and Registrar location remain under another introduction.

`What programs are offered at SPUS?` offers, in a fresh conversation:

- Does SPUS offer Graduate School programs?
- Why choose SPUS?
- Where is the registrar office?

`How are announcements and promotional materials broadcast across the SPUS campus?`
returns the exact PBMO answer describing the Unified Multimedia Communication
Network and cites that office FAQ. Its recommendations concern PBMO review and
submission of materials. They are not replaced with unrelated enrollment FAQs.

## Validation

| Check | Result |
|---|---|
| Explicit backend regression suite | 333 passed, including 23 new tests |
| Existing frontend suggestion/transport tests | 9 passed |
| New live HTTP/click sequence through Vite | 26 passed, including 10 related FAQ clicks |
| Native Chrome React guest scenario | 5 passed |
| Existing suggestion replay | 6 passed |
| Existing typo/short-query checks | 18 passed |
| Existing compound/partial/conflict/isolation checks | 12 passed |
| PostgreSQL conversation-session checks | 11 passed; all temporary writes rolled back |
| Cited excerpt verification against PostgreSQL | 14/14 preserved verbatim |
| Full-row data fingerprints, including embeddings/history | Unchanged |

The PostgreSQL session checks used existing accounts and a fixture retriever;
the HTTP/click checks used the actual running knowledge database. No replacement
accounts were created. The dedicated browser profiles were removed after testing.

One initial `manage.py test chatbot` command failed discovery with 13 relative
import errors in the existing namespace-package layout. The explicit qualified
module command below runs all 333 regressions successfully. Package-layout
cleanup was left outside this task. An exploratory parser check also initially
omitted its required vocabulary argument; rerunning with the existing vocabulary
confirmed that the PBMO questions are parsed as single requests.

Final service activation took 61.38 seconds including startup, with all three
workers ready. This is an operational observation, not a startup optimization
claim. Individual request timings are recorded in the after artifact; this
small functional replay is not a p50/p95 load benchmark.

## Files

Production changes:

- `chatbot/dialogue.py`: self-reference grammar and mixed-greeting handling.
- `chatbot/social_responses.py`: explicit, friendly AI introduction.
- `chatbot/rag.py`: exact FAQ/conflict precedence and announcement fallback.
- `chatbot/suggestions.py`: supported entry points, source-body checks,
  conflict-aware grouping, concise labels and stricter relevance ranking.

Tests and verification:

- `chatbot/test_identity_suggestions.py` (new).
- `scripts/verify_identity_faq_http.py` (new).
- `scripts/verify_identity_faq_integrity.py` (new).
- `scripts/verify_dialogue_browser.mjs` (adds an optional `--identity-faq` scenario).

Proof artifacts:

- `PAULA_IDENTITY_FAQ_BEFORE.json`
- `PAULA_IDENTITY_FAQ_AFTER.json`
- `PAULA_IDENTITY_FAQ_BROWSER.json`
- `PAULA_IDENTITY_FAQ_INTEGRITY.json`
- `PAULA_IDENTITY_FAQ_STARTUP_FINAL.json`

Reproduce backend tests through Docker PostgreSQL:

```powershell
docker exec paulibot_web python -B manage.py test chatbot.test_identity_suggestions chatbot.test_query_understanding chatbot.test_dialogue chatbot.test_suggestions chatbot.test_about_spus_ingestion chatbot.test_performance chatbot.test_compound_queries chatbot.test_retrieval_consistency chatbot.test_grounding chatbot.test_intents chatbot.test_web_crawler chatbot.test_enrollment chatbot.test_conversation_context chatbot.test_chat_sessions --keepdb --verbosity 1
python -B scripts/verify_identity_faq_http.py
```

No institution facts, knowledge embeddings, historical chats, dependencies,
migrations, provider configuration, frontend production code, or database volumes
were changed in this phase. Suggestions use a request-local catalog read rather
than an extra LLM call or a stale answer cache. The existing 0.45 retrieval cutoff
and 384-dimensional embeddings remain unchanged.

## Limits

Suggestions are supported entry points and source-derived questions, not a
guarantee that all future wording or source conflicts are understood. Related
questions use lexical/entity/category relationships; no universal semantic
recommendation accuracy is claimed. Source-excerpt preservation does not verify
the current truth of institutional records. Uncertain or incomplete knowledge
continues to require clarification or an honest fallback.
