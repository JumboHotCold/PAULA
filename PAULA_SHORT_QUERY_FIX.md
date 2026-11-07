# Short questions, spelling repair, and friendly clarification

## Cause

The recommendation FAQ was already present in Docker PostgreSQL. The request
`why spus?` did not match the stored `Why choose SPUS?` FAQ key. The normal hybrid
path then returned no eligible evidence, and the existing fallback suggested
the very FAQ that should have answered the question. A before-change live
reproduction is recorded in `PAULA_SHORT_QUERY_BEFORE.json`.

The existing typo corrector covered a small institutional vocabulary but ran
after social routing. Short question-word errors such as `wht` were not covered;
`helo` entered factual retrieval. Unclear fragments received the same formal
missing-knowledge response as a complete factual question.

## Changes

- Complete omitted actions using **stored FAQ question labels**. `Why SUBJECT?`
  and `Bakit SUBJECT?` can resolve to a unique stored question such as
  `Why choose SUBJECT?`, `Why use SUBJECT?`, or `Why apply for SUBJECT?`.
  This is not an SPUS-specific answer template. The subject must match exactly.
- Prefer an explicitly stored short FAQ over inferred wording. If two actions
  fit, ask which question the user means. Conflicting answers still reach the
  existing conflict checks.
- Use the completed query for retrieval, evidence validation and signed context.
  Actual institutional answers remain source excerpts; no facts are generated
  by the query completer.
- Correct unambiguous question-leading typos and one-edit institutional terms,
  including regular plural forms. Normalize before social routing. Preserve
  acronyms, identifiers, names protected by existing rules, numerical conditions
  and negation. This remains conservative spelling repair, not a universal
  spellchecker.
- Recognize whole-message greeting typos such as `helo` and explicit repair
  messages such as `sorry typo` and `maling pindot`.
- Respond to punctuation-only or unmatched incomplete input with a friendly
  request to rephrase. Preserve the previous task and pending category during
  repair, including history-only continuation.
- Keep missing factual knowledge distinct: do not fabricate an answer. The
  fallback now also invites the user to rephrase or provide more detail.

Examples verified through the Vite proxy:

| Input | Behavior |
|---|---|
| `why spus?` | Cites the stored recommendation FAQ |
| `why choos SPUS?` | Corrects the clear typo and returns that FAQ |
| `bakit SPUS?` | Retrieves the same source, with Filipino framing |
| `wht is spus?` | Retrieves the stored institutional overview |
| `What progrms are offered at SPUS?` | Retrieves the program information |
| `hwo do I enorll at SPUS?` | Asks the student category |
| `Wher is the registar?` | Opens the Registrar map destination |
| `helo` | Friendly greeting |
| `sorry typo` / `???` | “No worries! Could you retype or rephrase what you'd like to ask?” |
| `asdasdasd` | “I'm not sure what you mean yet. Could you rephrase or add a little more detail?” |
| `why SPUS in 2030?` | Does not invent future information |

The live enrollment sequence `How do I enroll?` → `sorry typo` → `asdasdasd` →
`I am a transferee` still retrieves URO-PR-017.

## Validation

- 310 backend regressions passed, including 25 new short-query/typo tests.
- 9 existing frontend transport/suggestion tests passed.
- 18 new live short-question, typo, repair and continuity checks passed.
- Existing live dialogue (20), compound/partial/conflict/isolation (12), and
  About SPUS (14) checks passed during this change.
- 11 PostgreSQL session-isolation checks passed using existing accounts and a
  fixture retriever; temporary chat/session changes were rolled back.
- `PAULA_SHORT_QUERY_INTEGRITY.json` records full-row before/after fingerprints,
  including vectors, and verifies cited excerpts against their stored bodies.

An intermediate test exposed missing plural typo correction (`progrms`). The
general correction vocabulary now includes regular plural candidates; all final
backend tests pass. Two additional regressions protect an explicitly stored
short question from being overridden by inferred wording.

The baseline contains one request per example, not a p50/p95 benchmark. Live
durations are recorded in `PAULA_SHORT_QUERY_AFTER.json`; no general performance
or universal accuracy improvement is inferred from these small samples. The
completion path adds one bounded read of public FAQ labels for eligible short
reason questions and avoids vector/provider work when exact evidence suffices.

## Files

New:

- `chatbot/query_understanding.py`
- `chatbot/test_query_understanding.py`
- `scripts/verify_short_queries_http.py`
- `scripts/verify_short_query_integrity.py`

Updated:

- `chatbot/intents.py`: bounded spelling correction and plural candidates.
- `chatbot/dialogue.py`: normalize before routing; greeting and repair handling.
- `chatbot/social_responses.py`: friendly non-factual repair replies.
- `chatbot/rag.py`: source-backed completion from public FAQ labels.
- `chatbot/logic.py`: apply completed queries, clarify ambiguity, preserve task
  context and distinguish incomplete input from missing knowledge.
- `chatbot/conversation_context.py`: omit failed input-repair turns from replay.

The existing 0.45 retrieval cutoff, embedding dimensions, authentication guards,
institutional records, and PostgreSQL volumes are preserved. No packages, API
services, migrations, or institutional fact changes were introduced. The web
service is restarted to activate Python changes; Vite continues to proxy Docker
on port 8080.

## Limits

Uncertain spellings, ambiguous acronyms, personal names and novel phrasing are
not guessed. Some requests will still need clarification. Omitted-action
completion currently uses FAQ labels; subjects found only in website text still
use the existing RAG path. These regression results do not guarantee perfect
language understanding or establish the current truth of every stored source.
