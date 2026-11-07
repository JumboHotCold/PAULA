# PAULA performance phase 1 — implementation and validation

29 October 2026. Authorized scope: priorities 1–4 only.

## Result and validation status

Request tracing, offline embedding readiness, provider deadlines/cooldowns, and
immediate frontend delivery are implemented and active in Docker. No knowledge
facts, stored embedding arrays, accounts, or historical conversations were
replaced. No new packages, paid services, database migrations, approximate vector
indexes, response caches, retrieval batching, streaming, or Gunicorn worker-count
changes were introduced.

**The project-permission blocker is resolved.** Both candidates passed all 16
checks in the controlled selector corpus. `openai/gpt-oss-20b` was selected for
its lower observed p95 and is active through Groq with `PAULA_GROQ_ENABLED=true`.
`PAULA_GROQ_MODEL_EVALUATION.json` records the successful results and validated
choice. This small corpus does not establish universal factual accuracy.

The GPT-OSS model is served by Groq, not the OpenAI API. OpenAI is disabled with
`PAULA_OPENAI_ENABLED=false` because the prior audit returned
`credit_balance_exhausted`. Existing deterministic and semantic retrieval,
source gating, extractive responses, clarification, navigation, and contextual
conversations continue to use the existing grounding safeguards.

## 1. Structured timing and privacy

`chatbot/performance.py` adds request-local tracing through `ContextVar` and a
middleware wrapper. Every chat request gets a server-generated UUID and worker
PID in `X-Request-ID` and `X-PAULA-Worker`. `Server-Timing` reports server-total
and SQL-execution time. Browser requests record `paula.chat.http` Performance API
entries containing correlation IDs and durations, not conversation content.

JSON stdout events record normalization, context resolution, public-vocabulary
access, structured personnel/enrollment retrieval, hybrid retrieval, query
encoding, evidence grounding, provider selection/calls, response rendering,
SQL counts/timing, status, and total server processing. Startup emits separate
per-worker import, model-load, warmup and readiness events.

No prompt, response body, account identity, conversation ID, cookies, context
tokens, SQL statements/parameters, API keys, or raw provider error messages are
included in these timing records. Request IDs are generated rather than trusting
incoming headers. Tests cover payload exclusion and concurrent trace isolation.

Each span includes `inclusive_ms` and `self_ms`. Recursive orchestration and
nested retrieval overlap; inclusive durations must **not** be summed to estimate
wall time. SQL execution time is nested inside retrieval and excludes some
fetching/deserialization work. Middleware totals exclude browser transport and
time spent waiting before a worker accepts a request.

`PAULA_PERFORMANCE_STAGE_SAMPLES.json` contains seven sanitized records matched
to the benchmark's response IDs. For example, the recorded compound personnel
request took **157.92 ms** server-side: two structured lookups took **152.68 ms**,
final and intermediate grounding totaled **4.71 ms**, and rendering took
**0.06 ms**. It made no embedding or provider call. A calendar request took
**73.98 ms**, including **14.38 ms** query encoding and **24.28 ms** SQL execution.

## 2. Model and worker readiness

`chatbot/embedding_runtime.py` maintains one locked model instance per process.
The existing cache snapshot is pinned to:

```text
sentence-transformers/all-MiniLM-L6-v2
1110a243fdf4706b3f48f1d95db1a4f5529b4d41
384 dimensions, CPU, original encode defaults
```

The loader reads this local snapshot with `local_files_only=True`. It checks
the declared dimensions and a finite 384-element warmup encoding. It does not
download a replacement model or regenerate knowledge vectors. Independent
`RAGSearcher` instances reference the same process model. Existing management
and evaluation scripts may initialize their own offline process; web requests
cannot perform cold initialization or retry a failed startup model load.

`paulibot/gunicorn_conf.py` prepares the model in `post_worker_init`, after fork,
before that worker accepts its first request. Torch/model encoding is not
preloaded in the master. The existing **three synchronous workers and 120-second
worker timeout remain unchanged**.

Operational readiness markers are isolated by a new boot UUID under temporary
container storage. `/api/health/live` indicates the process is reachable;
`/api/health/ready` returns 200 only when the serving worker's model is prepared
and all expected live worker markers are ready. Old boots, duplicate PIDs,
dead workers and failed models cannot satisfy aggregate readiness. The master
removes only the exited worker's marker, without importing Django or Torch.
This is semantic-worker readiness, not a general audit of all external systems.

Compose adds a readiness healthcheck. The existing workspace launcher now waits
for all workers rather than announcing the backend immediately after the
container starts. It still recreates only the web service and verifies that the
PostgreSQL container and workspace mount are preserved.

Measured startup and lifecycle behavior:

- Initial web activation to all-worker readiness: **42.41 seconds**, including
  Compose/container startup, existing migration/static startup commands and
  model preparation.
- A subsequent restart reached all-worker readiness in **26.57 seconds**.
  Worker initialization was approximately **15.7–15.9 seconds** in that run.
- The provider-disabled activation reached all-worker readiness in **28.17 seconds**. The first
  concurrent semantic requests in that final run took **345–361 ms** and visited
  all three workers. See `PAULA_STARTUP_AFTER_FINAL.json`.
- First concurrent semantic requests after that readiness barrier completed in
  **676–688 ms**, across all three workers, with correct cited results.
- Gracefully replacing one idle worker made aggregate readiness unavailable
  during preparation. It recovered in **25.66 seconds** with the replacement
  worker present and the old PID absent.
- Observed web-container memory was approximately **1.46 GiB**, with a Docker VM
  total of approximately **3.5 GiB**. No worker-count or Torch-thread tuning was
  applied. Sampled idle CPU was low; this is not a peak-concurrency memory test.

Artifacts: `PAULA_STARTUP_AFTER.json`, `PAULA_STARTUP_AFTER_FINAL.json`,
`PAULA_WORKER_RECYCLE.json`.
The final provider-enabled activation took **38.89 seconds** to aggregate
readiness, including approximately **22.3–22.7 seconds** per worker initialization.
First concurrent semantic requests then took **352.74–354.91 ms**, visiting all
three workers. See `PAULA_STARTUP_WITH_GROQ.json`. A final idle resource sample
was **1.471 GiB / 3.498 GiB**, **0.09% CPU**, with 164 container PIDs/threads;
this remains an observation rather than a peak-load capacity result.
Startup still costs time. The change moves preparation before semantic readiness;
it does not promise an instant cold container or sleeping free-tier instance.

## 3. Provider policy and the access blocker

`chatbot/providers.py` implements a shared request generation budget. Context
editing and answer selection, including compound parts, share a default
**four-second overall generation window**. Individual SDK operations receive a
default three-second timeout and retries remain zero. A bounded executor enforces
the caller's wait deadline even when an SDK operation is slow. Late operations
retain SDK timeouts, and a two-slot limit per worker prevents unbounded background
work. Late results cannot become answers.

Provider failure categories receive cooldowns: missing models, denied access and
exhausted credits are not repeatedly called; temporary rate limits, timeouts and
other API errors have shorter cooldowns. Operational state is shared across web
workers within the boot through atomic temporary files. It contains only reason
and expiry, not credentials or request content. Restarting or recreating the web
service starts fresh boot state. Known-skipped providers do not consume the
compound message's existing one-call selection allowance.

OpenAI/Gemini fallback support remains conditional. Calls respect the same
budget and continue to accept only validated evidence IDs. With no usable
provider, the strongest already-gated stored excerpt remains the fallback;
there is no model-memory answer or provider-authored factual prose.

The candidate comparison uses eight fictional evidence-selection cases, with
English, Filipino, Taglish, personnel, enrollment, scholarship, policy, source
priority, missing information and prompt-injection coverage. GPT-OSS candidates
use low reasoning effort, suppressed reasoning output, a 512-token cap and
strict JSON schemas with allowed evidence IDs. Local evidence validation remains
in place independently of schema constraints.

The initial access checks failed with `model_permission_blocked_project`.
The initial evaluation was stopped after repeated denied requests; the evaluator
was corrected to stop immediately on access/rate-limit failures. Those failure
timings were not generation measurements. After the user updated the correct
project's allowed models, fresh requests succeeded and the full comparison ran.

| Candidate | Correct selections | Overall p50 ms | Overall p95 ms | Warm p95 ms |
| --- | ---: | ---: | ---: | ---: |
| `openai/gpt-oss-20b` | 16/16 | 1028.80 | 1912.39 | 1847.73 |
| `openai/gpt-oss-120b` | 16/16 | 698.75 | 2782.53 | 2782.53 |

Warm statistics omit the first successful request for each model (15 samples).
Both models correctly abstained for missing knowledge and source injection.
120B had the better median, but 20B had the lower measured tail. The evaluation
client allowed four seconds; these are successful response measurements rather
than observations censored by the original two-second serving limit. Selection
followed the predefined full-corpus correctness requirement and p95 criterion
rather than model size. Cloud latency varies and this sample is small.

The first provider-enabled application run used the original two-second SDK
limit and observed a generic provider failure after about 2.09 seconds, followed
by shared cooldown skips. That record did not include the exception class, so
its precise cause was not established. SDK-specific timeout classification and
safe exception-type/HTTP-status telemetry were added. The final serving limit
allows three seconds per call while preserving the four-second overall window;
late results still cannot enter the response. The initial run is retained in
`PAULA_PERFORMANCE_WITH_GROQ_INITIAL.json` rather than being described as a fully
successful healthy-provider benchmark.

For future access errors, select the API key's project in Groq Console, open
[Settings → Projects → Limits](https://console.groq.com/settings/project/limits),
allow both candidate models and save. Organization restrictions take precedence.
The observed code and this workflow are described in
[Groq's model-permissions documentation](https://console.groq.com/docs/model-permissions).

To repeat the comparison:

```powershell
docker exec paulibot_web python -B manage.py shell -c "import runpy,sys;sys.argv=['evaluate_groq_selectors.py'];runpy.run_path('scripts/evaluate_groq_selectors.py',run_name='__main__')"
```

The evaluator recommends a model only after every case in both rounds passes,
then ranks qualifying candidates by observed p95. This is a small selector
corpus, not institution-wide factual certification or free-text translation
evaluation. Live grounded-answer checks also passed after activation. The
deployment uses `PAULA_GROQ_ENABLED=true` and the validated default
`PAULA_GROQ_MODEL=openai/gpt-oss-20b`. Future model overrides should undergo the
same comparison before web-service recreation.
No secrets should be committed or copied into a report.

## 4. Frontend delivery

The artificial 600 ms `setTimeout` in `frontend/src/App.jsx` is removed. Validated
JSON responses enter React state immediately. Loading indicators remain active
while the request is outstanding. Existing account/session epoch checks remain
before updates, so a response from an earlier account or guest session cannot
be appended after a mode switch. The chat API records only operational browser
timing metadata and bounds its retained performance entries.

This removes a deterministic display delay. Browser paint was not independently
measured, and the HTTP results below do not include React rendering time. No
streaming or progressive unverified text was introduced.

## Before-and-after benchmark

`scripts/benchmark_performance_phase1.py` uses the same seven queries, endpoint,
20 measured samples per case and two separately recorded initial samples in both
runs. Every request explicitly uses guest mode and asserts `saved: false`.
These are sequential local HTTP measurements through the Vite proxy, using
nearest-rank p95. After-run responses were observed across all three workers.

| Case | Before p50 ms | Before p95 ms | After p50 ms | After p95 ms |
| --- | ---: | ---: | ---: | ---: |
| ICT Director | 106.28 | 3888.10 | 95.28 | 114.19 |
| ICT Director and CEIT Dean | 183.42 | 234.01 | 171.12 | 200.32 |
| Freshmen and transferee requirements | 43.76 | 61.15 | 45.73 | 85.88 |
| Semantic school-calendar query | 109.97 | 20153.28 | 91.43 | 110.12 |
| Available scholarships | 714.93 | 1627.81 | 91.58 | 106.64 |
| SPUS Quality Policy | 749.18 | 982.15 | 90.58 | 110.28 |
| Scholarships plus school calendar | 335.06 | 408.34 | 151.94 | 169.52 |

Interpretation is essential:

- The before run includes requests reaching workers whose models were not yet
  initialized. Excluding two initial samples did not guarantee every worker was
  warm. The after run began only after all-worker readiness. The large calendar
  tail improvement demonstrates removal of request-time initialization, not a
  180-fold improvement in vector arithmetic.
- Before-run selectors attempted an unavailable Groq model and an unusable
  OpenAI fallback. That after run deliberately disabled external providers while
  project permissions were unresolved. Scholarship/policy gains include avoiding
  failed calls. These are **not healthy-LLM latency measurements**.
- Retrieval thresholds, source priorities and institutional facts are unchanged.
  Enrollment tail latency increased slightly in this small run; no uniform
  speedup is claimed. All measured after-run p95 values were below the requested
  objectives for this deployment mode.
- The original table above records the provider-disabled phase. A separate
  provider-enabled benchmark is recorded in `PAULA_PERFORMANCE_WITH_GROQ.json`.
  Larger samples, controlled cold-host runs and a concurrency sweep would be
  required for production service guarantees. Priorities 5–8 were not deployed.

Artifacts: `PAULA_PERFORMANCE_BEFORE.json`, `PAULA_PERFORMANCE_AFTER.json`,
`PAULA_PERFORMANCE_COMPARISON.json`, `PAULA_PERFORMANCE_STAGE_SAMPLES.json`.

```powershell
python -B scripts/benchmark_performance_phase1.py --output PAULA_PERFORMANCE_AFTER.json --samples 20
```

### Final provider-enabled benchmark

The final run uses Groq `openai/gpt-oss-20b`, a three-second SDK timeout and a
four-second shared generation deadline, with OpenAI disabled. The same seven
queries, Vite endpoint, guest assertions and 20 measured samples per case were
retained. Two initial requests per case are recorded separately. All three
workers were ready before testing.

| Case | Warm p50 ms | Warm p95 ms | Observed p95 objective |
| --- | ---: | ---: | ---: |
| ICT Director | 107.30 | 130.67 | ≤ 1500 ms |
| ICT Director and CEIT Dean | 171.56 | 197.19 | ≤ 2000 ms |
| Freshmen and transferee requirements | 36.22 | 60.41 | ≤ 2000 ms |
| Semantic school-calendar query | 90.94 | 110.80 | ≤ 5000 ms |
| Available scholarships | 1071.86 | 2216.21 | ≤ 5000 ms |
| SPUS Quality Policy | 1017.04 | 1875.95 | ≤ 5000 ms |
| Scholarships plus school calendar | 1021.69 | 1633.18 | ≤ 8000 ms |

All **154 request IDs** (140 measured plus 14 initial) were matched to structured
server traces. The **66 Groq calls all returned successfully**, with no provider
error, timeout or cooldown skip. The four structured/single-excerpt cases made
no external calls. Every response retained sources; all compound answer parts
reported `ok`. These operational checks and the separate regression/live checks
do not constitute independent human verification of every knowledge-base fact.

Representative measured-stage medians:

| Case | Retrieval ms | Query embedding ms | Grounding ms | LLM ms |
| --- | ---: | ---: | ---: | ---: |
| ICT Director and CEIT Dean | 156.84 | — | 4.82 | — |
| Semantic school calendar | 73.41 | 13.97 | 2.11 | — |
| Available scholarships | 72.82 | 14.32 | 4.53 | 972.69 |
| SPUS Quality Policy | 78.26 | 15.06 | 4.19 | 919.62 |
| Scholarships plus calendar | 129.69 | 27.58 | 6.80 | 849.02 |

Query encoding is included within retrieval. Grounding can occur inside and
after retrieval; columns overlap and medians must not be added. The compound
query uses one successful evidence-selection call, not one call per part.
The provider now dominates the tested standard RAG cases. Existing embedding
coverage checks still contribute approximately 18–23 ms; changing them belongs
to deferred work.

To respect the observed free-tier token allowance, the diagnostic harness waited
five seconds between selector-bearing requests. These pauses are **outside**
the timed requests and are not application response delays. The original runs
were unpaced, so this is not a controlled throughput comparison. Healthy cloud
inference is slower than the provider-disabled extractive path. The p95
objectives were met in this sequential local pilot; concurrent load, cloud
variability and free-tier limits can change results. Maximum scholarship latency
was 3267.18 ms, despite its lower p95.

Artifacts: `PAULA_PERFORMANCE_WITH_GROQ.json` and the privacy-safe complete
correlation `PAULA_PERFORMANCE_WITH_GROQ_TRACES.json`. The separate initial
two-second-limit run remains available for failure analysis.

```powershell
python -B scripts/benchmark_performance_phase1.py --output PAULA_PERFORMANCE_WITH_GROQ.json --samples 20 --selector-interval 5
```

## Tests and data integrity

- **216 backend tests passed**, including 20 phase-1 tests for timing isolation,
  private-data exclusion, offline loading, dimensions, shared model instances,
  all-worker/boot readiness, master cleanup, provider cooldowns, hard wait
  deadlines, nested request budgets and strict evidence-ID schemas.
- All previous 196 tests were rerun, covering retrieval consistency, personnel,
  enrollment, scholarships/policies and generic domains, compound questions,
  multilingual context, conflicts, missing evidence, guest privacy and sessions.
- **12 live compound/context/guest checks passed** against the active backend.
- **18 existing Django/PostgreSQL/CSRF/session integration checks passed** using
  existing accounts. All temporary auth/session/chat row changes were rolled
  back, and no replacement account was created.
- The existing frontend API transport test passed. The frontend production build
  passed and retained its large-chunk warning; no dependency changes were made.
- The permission failures were resolved. Both candidates passed 16/16 selector
  checks; 20B is active. Multilingual selection and grounded rendering were
  evaluated, not unconstrained translation or institution-wide factual accuracy.

`PAULA_PERFORMANCE_INTEGRITY.json` compares complete rows, including embedding
arrays, before and after validation. It confirms unchanged **12 StaffMember,
134 FAQ, 476 WebResource, 139 Conversation and 176 ChatHistory** records. The
6 Location embeddings were not regenerated; no embedding dimension/model-space
change was introduced. The manually corrected JSIT moderator remains untouched.

```powershell
docker exec paulibot_web python -B manage.py test chatbot.test_performance chatbot.test_compound_queries chatbot.test_retrieval_consistency chatbot.test_grounding chatbot.test_intents chatbot.test_web_crawler chatbot.test_enrollment chatbot.test_conversation_context chatbot.test_chat_sessions --verbosity 1
node --test frontend/src/api/chatApi.test.mjs
```

## Modified source and tooling

| File | Purpose |
| --- | --- |
| `chatbot/performance.py` | Private-data-free request/stage tracing and middleware |
| `chatbot/embedding_runtime.py` | Offline pinned process model and readiness guard |
| `chatbot/readiness.py` | Aggregate boot/worker readiness markers |
| `chatbot/providers.py` | Request generation deadline, bounded calls, outage state and model options |
| `paulibot/gunicorn_conf.py` | Post-fork preparation and master-safe worker cleanup |
| `paulibot/settings.py` | Phase-1 settings, middleware and operational logging |
| `docker-compose.yml` | Startup hook, healthcheck and explicit provider flags |
| `chatbot/logic.py` | Shared provider policy, timing and compatible grounded fallback |
| `chatbot/rag.py` | Prepared model reference and retrieval/encoding timings |
| `chatbot/personnel.py`, `chatbot/enrollment.py`, `chatbot/grounding.py` | Retrieval/grounding timings |
| `chatbot/intents.py`, `chatbot/conversation_context.py` | Normalization/context timings |
| `chatbot/views.py`, `chatbot/urls.py` | Liveness and semantic-readiness endpoints |
| `frontend/src/App.jsx` | Immediate validated response display |
| `frontend/src/api/chatApi.js` | Browser HTTP correlation/timing without payloads |
| `scripts/start_workspace_backend.ps1` | Wait for semantic readiness; preserve PostgreSQL |
| `scripts/benchmark_performance_phase1.py` | Repeatable identical HTTP benchmark |
| `scripts/evaluate_groq_selectors.py` | Fail-fast candidate-access/selector evaluation |
| `scripts/measure_worker_readiness.py` | Separate startup and first-ready request measurements |
| `scripts/verify_worker_recycle.py` | Graceful replacement/readiness validation |
| `chatbot/test_performance.py` | Phase-1 regression tests |
| `PAULA_PERFORMANCE_PHASE1.md` | This report |
| `PAULA_RESPONSE_GROUNDING.md`, `PAULA_COMPOUND_QUERY_REPORT.md` | Pointers to this phase's measured results |

Generated phase-1 JSON artifacts are named above. Existing live-compound and
chat-privacy result files were also regenerated by their existing verification
scripts. Earlier unrelated dirty files in this checkout were preserved.

## Deployment considerations and next step

Keep the pinned model cache available. A new host without the cached snapshot
will remain unready rather than silently downloading a different revision during
a user request. Prepare the exact public model snapshot before starting service.
The cache volume persists across web recreation; PostgreSQL volumes are never
reset by the launcher.

Use the readiness endpoint or the updated launcher to determine when startup has
finished. Health reporting now reflects a warming replacement worker as well as
initial startup. In-memory provider tasks are bounded; requests can return a
grounded fallback when a deadline expires instead of waiting indefinitely.

The raw cosine cutoff remains **0.45**. Existing request-time missing-embedding
maintenance, metadata fetching, database connection policy, worker count/thread
settings, and JSON delivery remain otherwise unchanged. Their optimization is
outside this approved phase.

The project-permission dependency has been resolved and the validated 20B model
is active. OpenAI remains disabled pending usable credits. The original
provider-disabled measurements and the subsequent provider-enabled measurements
are retained separately. Priorities 5–8 still require their own evaluation and
authorization; they were not implemented as part of this phase.
