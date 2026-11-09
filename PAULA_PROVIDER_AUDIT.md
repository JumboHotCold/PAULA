# PAULA provider audit — Stage 1, November 9, 2026

Stage 1 records existing behavior. No provider, model, settings, credentials, application code, or database records were changed. `CONFIRMED` means source inspection and/or the named reproduction supports the statement; `HYPOTHESIS` identifies an unverified explanation or account capability. Model-documentation findings are dated and linked separately from account access.

## Actual responsibilities

| Status | Task | Current implementation and evidence |
| --- | --- | --- |
| CONFIRMED | Intent routing | Local rules, abbreviation/typo matching, then optional local MiniLM exemplar similarity. No Groq/OpenAI classifier call: `chatbot/dialogue.py:189`, `chatbot/social_normalization.py:36`. |
| CONFIRMED | Embeddings | Local `sentence-transformers/all-MiniLM-L6-v2`, pinned revision, CPU, 384 dimensions. Neither Groq nor OpenAI computes them: `chatbot/embedding_runtime.py:12`, `chatbot/embedding_runtime.py:55`, `chatbot/rag.py:39`. |
| CONFIRMED | Retrieval decision/execution | Python orchestration and structured/exact/hybrid PostgreSQL lookup: `chatbot/logic.py:334`, `chatbot/logic.py:428`, `chatbot/rag.py:164`. There is no OpenAI agent deciding whether to retrieve. |
| CONFIRMED | Context editing | Optional **Groq-only** edit for unresolved follow-ups. Returns one literal anchor/replacement pair; local validation checks it before retrieval: `chatbot/logic.py:128`, `chatbot/conversation_context.py:371`. |
| CONFIRMED | Evidence selection | Groq primary; conditional OpenAI fallback; conditional legacy Gemini fallback. Providers return evidence IDs, not institutional answer prose: `chatbot/logic.py:168`. |
| CONFIRMED | Validation | Local department/role/date/topic gates, conflict checks, bounded evidence-ID schema and literal context-edit validation: `chatbot/grounding.py:96`, `chatbot/grounding.py:222`, `chatbot/conversation_context.py:371`. The LLM may reject eligible candidates, but is not the final factual validator. |
| CONFIRMED | Final institutional response | Stored answer excerpts and attribution rendered locally: `chatbot/grounding.py:251`, `chatbot/logic.py:106`. Friendly framing is separate: `chatbot/response_style.py:23`. |

**CONFIRMED:** the `openai/` prefix in Groq's model name identifies the model family, not an OpenAI API call. Runtime Groq calls use the Groq SDK. The separate OpenAI SDK client is disabled in the audited Docker configuration. References: `chatbot/logic.py:58`, `chatbot/logic.py:63`, `artifacts/stage1/audit.json` → `runtime`.

**CONFIRMED:** inspected tracked application/script call sites contain no Agents SDK `Agent`/`Runner`, Responses retrieval tool loop, or tool/function declarations controlling retrieval. The conditional request to remove agent-controlled retrieval therefore does not apply to this implementation. Changing extractive answers into LLM-generated final prose would be a separate architecture/grounding change, not a necessary Stage 1 action.

## Every Groq/OpenAI request site in the inspected source

| Status | Call site / entry point | Provider/model | Request settings / role |
| --- | --- | --- | --- |
| CONFIRMED | `chatbot/logic.py:147`, `_context_edit` | Groq, `settings.GROQ_MODEL` | Literal context edit; temperature 0. For `openai/gpt-oss-*`, strict JSON schema, max completion tokens 512, reasoning effort `low`, reasoning omitted. |
| CONFIRMED | `chatbot/logic.py:184`, `_select` Groq branch | Groq, `settings.GROQ_MODEL` | Evidence selection with the same GPT-OSS settings, schema restricted to evidence IDs. |
| CONFIRMED | `chatbot/logic.py:184`, `_select` OpenAI branch; model defined at `chatbot/logic.py:178` | OpenAI API, literal `gpt-4o-mini` | Temperature 0, max tokens 128, JSON-object mode; local ID validation remains mandatory. No OpenAI context-edit, embedding, or routing request exists in this path. |
| CONFIRMED | `scripts/evaluate_groq_selectors.py:38` | Groq `models.list()` | Manual evaluation-only model discovery; client timeout 4 s, retries 0. No discovery call occurs in normal chat startup or each user prompt. |
| CONFIRMED | `scripts/evaluate_groq_selectors.py:50` | Groq `openai/gpt-oss-20b` and `openai/gpt-oss-120b` | Manual fixture evaluation, temperature/schema from `completion_options`; client timeout 4 s and retries 0. It blocks a model for the remaining script run on 401/403/404/429 and sleeps 1 s between attempts. This script was not run during Stage 1. |
| CONFIRMED | `scripts/smoke_mvp_provider.py:16` | Calls the existing `_select` | Manual synthetic live probe using the same runtime call sites; not a separate provider implementation and not run during this audit. |

**CONFIRMED:** production clients are initialized at `chatbot/logic.py:60` and `chatbot/logic.py:66` with explicit `max_retries=0`. The shared policy limits each actual call to `min(remaining_budget, call_timeout)`: `chatbot/providers.py:138`. Audited settings are **3 s per call / 4 s generation budget**, with the latter starting at the first provider use, not at initial HTTP arrival. They are not a bound on all database/frontend work. Definitions/clamps: `paulibot/settings.py:38`, `paulibot/settings.py:39`.

## Existing fallback and concurrency rules

**CONFIRMED:** a single-result verified FAQ, direct structured result, navigation action or recognized social intent can answer without a provider. For other eligible multi-result evidence, ordinary selection tries **Groq → enabled OpenAI → configured Gemini → strongest already-gated stored excerpt**. A valid empty evidence-ID array is an explicit veto and returns immediately; it does not trigger an attempt to make another model invent an answer. Invalid JSON/schema or a provider failure may advance to the next provider. References: `chatbot/logic.py:175`, `chatbot/logic.py:188`, `chatbot/logic.py:208`, `chatbot/logic.py:458`.

**CONFIRMED:** multi-part questions have an additional **one actual selector-call budget** shared across parts. If Groq consumes that attempt and fails, OpenAI is skipped even when time remains. If Groq was skipped by cooldown before consuming an attempt, another available provider may use it. This is a latency/cost constraint on the apparent fallback chain, not three guaranteed attempts. References: `chatbot/logic.py:213`, `chatbot/providers.py:126`, `chatbot/providers.py:136`; existing regression `chatbot/test_compound_queries.py:254`.

**CONFIRMED:** unresolved context editing has only a Groq path. Failure preserves the unresolved result and leads to clarification, rather than OpenAI editing. References: `chatbot/logic.py:136`, `chatbot/logic.py:155`, `chatbot/logic.py:372`.

**CONFIRMED:** the executor admits at most two in-flight provider tasks per process and does not queue more when saturated. A deadline cancels an unstarted future but cannot forcibly stop an already-running SDK request; the slot remains occupied until completion. Budget exhaustion/busy/cooldown skips are logged as provider outcomes. References: `chatbot/providers.py:17`, `chatbot/providers.py:129`, `chatbot/providers.py:141`, `chatbot/providers.py:149`.

## Failure modes: internal handling and actual user experience

The following are **CONFIRMED** in `chatbot/providers.py:80` and the eight isolated fake-SDK fault probes in `artifacts/stage1/audit.json` → `provider_faults`. No real account failure was induced and no active worker cooldown was changed.

| Failure | Policy outcome / cooldown | User-visible behavior when gated evidence exists |
| --- | --- | --- |
| HTTP 401/403 | `credentials_unavailable`, 3,600 s | Try an available fallback within budgets; otherwise display the stored excerpt. No key or permission details exposed. |
| Model project/org permission block | `model_permission_blocked`, 3,600 s | Same grounded fallback; normal next requests skip the unusable provider during cooldown. |
| Missing/decommissioned model / HTTP 404 | `model_unavailable`, 3,600 s | Same grounded fallback. |
| Exhausted credits/quota codes | `credits_exhausted`, 3,600 s | Same grounded fallback; no repeated primary call during cooldown. |
| HTTP 429 without exhausted-credit code | `rate_limited`, default 30 s; numeric `retry-after` clamped to 1–60 s | No blocking retry sleep. Try a permitted fallback or the stored excerpt. The synthetic audit used a 2-second Retry-After. |
| Timeout | `timeout`, 15 s | Deadline/call timeout bounds waiting; fallback to eligible stored evidence. |
| Other API/server error | `api_error`, 30 s | Same grounded fallback. |
| Invalid JSON/evidence IDs | Local selection validation fails; not a provider circuit failure | Next selector if allowed, then stored excerpt. The current code does not apply a cooldown specifically for repeated schema-invalid payloads. |
| Valid `{"evidence_ids":[]}` | Explicit rejection; no provider failure cooldown | `selection_rejected`: “I found related information, but I cannot verify a complete answer. Could you specify the office or topic?” |
| Provider failure during unresolved context edit | Context remains unresolved | A clarification question, not a provider error or fabricated answer. |

**CONFIRMED:** all eight fake-provider failures preserved the synthetic stored answer. They verify safe fallback behavior, not real account availability or timeout duration under network stress. Tests already covering provider deadlines/fallbacks passed in the 409-test baseline.

**CONFIRMED:** the application does **not** currently expose a distinct user message for every provider failure reason. Several are deliberately invisible when a grounded answer can be delivered. Without any eligible evidence it returns the no-match message; retrieval errors return temporary unavailability. A database error caught by `RAGSearcher.retrieve` becomes `unavailable`, while one reaching the view returns a safe storage 503. These distinctions are coarser than the requested future taxonomy. References: `chatbot/logic.py:88`, `chatbot/rag.py:160`, `chatbot/views.py:415`, `chatbot/api_errors.py:18`. No behavior was changed to hide this gap.

## API keys and environment boundaries

**CONFIRMED:** runtime loading prefers a nonempty process environment key, then Django settings; empty keys and `your_...` placeholders are ignored. Keys are not sent to React. Django uses `python-decouple` environment/config lookup; Docker Compose passes backend environment values from its selected environment file. Definitions: `chatbot/logic.py:48`, `paulibot/settings.py:31`, `paulibot/settings.py:34`, `paulibot/settings.py:45`, `docker-compose.yml:74`. `.env.example` contains placeholders only; `.dockerignore` excludes environment files.

| Status | Audited Docker configuration | Observed result |
| --- | --- | --- |
| CONFIRMED | Groq enabled, non-placeholder key configured | Client constructed; model `openai/gpt-oss-20b`. The 45 HTTP audit requests required **zero external provider calls**, so this is not a fresh account-access probe. |
| CONFIRMED | OpenAI key configured, `PAULA_OPENAI_ENABLED=false` | No OpenAI client constructed and no OpenAI call in the normal audited path. |
| CONFIRMED | Gemini key is a placeholder | No Gemini client constructed. A nonempty environment value alone would have been misleading evidence of availability. |
| HYPOTHESIS | OpenAI account has usable credits and access | Not verified. No activation or paid API probe was performed. |
| HYPOTHESIS | The same environment is used by an independently started port-8000 server or a future deployment | Not verified. The actual audited application is Docker PostgreSQL on 8080 with Vite on 5173. |

## Model lifecycle check

| Status | Model string | Finding as checked November 9, 2026 |
| --- | --- | --- |
| CONFIRMED — official documentation | Groq `openai/gpt-oss-20b` | Listed among supported production models; not identified as retired in the checked Groq deprecation page. This does not prove project permission or quota. [Groq models](https://console.groq.com/docs/models), [deprecations](https://console.groq.com/docs/deprecations). |
| CONFIRMED — official documentation | OpenAI `gpt-4o-mini` | Marked deprecated; the underlying listed snapshot has scheduled shutdown **January 14, 2027**. The fallback is currently disabled. No replacement was chosen or applied. [OpenAI model page](https://developers.openai.com/api/docs/models/gpt-4o-mini), [official deprecations](https://developers.openai.com/api/docs/deprecations). |
| CONFIRMED — source and official changelog | Gemini `gemini-1.5-flash` | Still named by the conditional runtime fallback at `chatbot/logic.py:73`, `chatbot/logic.py:196`; Google states it shut down **September 29, 2025**. Currently inactive because the key is a placeholder, so it did not cause the reproduced failures. [Official changelog](https://ai.google.dev/gemini-api/docs/changelog), `artifacts/stage1/google_model_lifecycle.json`. |
| CONFIRMED — source only | Gemini `gemini-2.5-flash` | Separate manual handbook OCR/cleanup model, not the live chat fallback. No ingestion or live model-availability test was run. References below. |

## Additional external-model paths outside live chat

**CONFIRMED:** `chatbot/management/commands/ingest_handbook.py:104` constructs Gemini 2.5 Flash and calls `generate_content` at line 139 for OCR. `ingest_text_handbook.py:100` constructs the same model, calls it at line 134, and retries ResourceExhausted up to **3 attempts with 65-second sleeps** at line 130. These commands do not use the live chat provider policy; explicit temperature/per-call timeout are not supplied at these call sites, so SDK defaults apply and were not exercised. They are not evidence of a per-user chat retry delay and were not run or changed.

## Proposed Stage 2 scope, awaiting “continue”

The following are **HYPOTHESIS / proposed work**, not implemented improvements:

1. Preserve deterministic routing/retrieval and source-only responses; fix the reproduced social-wrapper and noun-phrase context failures, and synchronous duplicate-submit protection.
2. Introduce the requested data-driven persona/lexicon/exemplar configuration with explicit regression coverage, rather than growing phrase-specific application branches.
3. Add safe, observable distinctions for classifier errors, retrieval errors and unsupported knowledge; retain grounded degraded-mode answers instead of displaying a provider error unnecessarily.
4. Review the disabled deprecated OpenAI fallback and inactive retired Gemini fallback before any activation. Provider/model changes require a separately reviewed decision; do not silently switch models during stabilization.
5. Calibrate thresholds only against the Stage 3 labeled/golden set. The current Stage 1 measurements do not justify loosening the .45 retrieval cutoff or claiming model quality improvements.
