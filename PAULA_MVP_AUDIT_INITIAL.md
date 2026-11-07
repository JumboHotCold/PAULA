# Initial MVP execution-path audit

Checkpoint: `f2abed9b25467229117b292e70135e32ecd097b6`, local ref `checkpoint/mvp-stabilization-20261107-23ba8e57`. The normal staging area/current branch were preserved. The checkpoint contains application source/configuration/public knowledge and assets, excluding environments, installed dependencies, secrets, media, and databases. Nothing was pushed.

## Actual request path

React `Dashboard.handleSend` → `App.handleSend` → `api/chatApi.sendMessage` → Vite `/api` proxy to Docker 8080 → Django request timing/security/session/CSRF middleware → `chatbot.views.chat_api` → owner/thread validation and bounded signed intent context → `PauliBotLogic.process_query` → `dialogue.route_turn` → local social response or knowledge orchestration → contextual decomposition/rewriting and enrollment/navigation adapters → `RAGSearcher.retrieve/search` → structured personnel/enrollment, exact/equivalent FAQ, or hybrid pgvector/lexical retrieval → `eligible_evidence` → optional evidence-ID selector with a provider deadline → extractive source rendering → per-part attribution → API suggestions and explicit history persistence → JSON → React rendering. Assistant history is intent context, never institutional evidence.

The present frontend proxies to the PostgreSQL-backed Docker service. Legacy Django templates and an optional local port-8000 server are separate interfaces. Active Docker readiness reported three prepared 384-dimensional workers. Migration check passed.

## Confirmed structural defects before application edits

1. **Standard regression discovery is broken.** `docker exec paulibot_web python -B manage.py test chatbot --keepdb --verbosity 0` ran only 22 test entries and failed with **17 relative-import errors**. `chatbot/__init__.py` is absent. Previous explicit module lists ran the suite, but no stable default verification command or CI prevents future omissions.
2. **Tested features are missing from the current Git release tree.** `git status` shows core dialogue/runtime/retrieval modules, tests, and frontend support files untracked. Deploying the original HEAD alone will omit them. The source checkpoint now captures the current application, but publishing a final tested release remains a separate step.
3. **Semantic requests perform maintenance writes.** `RAGSearcher._hybrid_search` calls `ensure_embeddings`, scanning all four knowledge tables and generating/saving every missing vector during an interactive request. Admin changes intentionally clear a vector. This couples a future user request's latency/failure to unrelated KB maintenance and can cause concurrent workers to duplicate indexing. Current coverage is being audited; this is a confirmed code path, not a claim that missing vectors caused today's exact failures.
4. **Infrastructure failures leak and are misrepresented.** `chat_api` and navigation catch arbitrary exceptions and return `str(exc)` to clients. React labels every non-401 error “Network error.” Malformed input, server defects, database failure, missing evidence, and rejected evidence therefore have inconsistent diagnostics/user messages. Errors must be safe and typed, with request correlation rather than sensitive exception strings.
5. **Development/production configuration can diverge.** Base settings silently select SQLite when `USE_POSTGRES` is absent/false; the configured active runtime is PostgreSQL. Missing `.dockerignore` means `COPY . /app` can package local secrets, SQLite, installed dependencies and development artifacts. Standalone Docker CMD omits the semantic readiness hooks used by Compose. These are repeatability risks, not evidence that the active database has switched.
6. **Health and readiness are incomplete.** Existing readiness checks worker/model markers but does not check PostgreSQL connectivity or whether knowledge is empty. A model-ready service can advertise readiness despite an unusable knowledge database. Liveness, worker readiness, and knowledge health need distinct checks.

## Existing safeguards retained

Deterministic social routes, strict FAQ matches, per-part retrieval, .45 raw-cosine cutoff, source/role/year/department validation, bounded provider budgets/cooldowns, evidence-ID-only selection, extractive responses, explicit guest persistence opt-in, owner/thread-bound signed context, authentication isolation, and local privacy-safe timing logs already exist. The audit does not justify replacing these components or the chosen models/providers.

## Initial hypotheses and open verification

Per-record model/revision provenance is not stored alongside vectors; compatible dimensions alone cannot prove the historical encoder for every row. Dependency/image reproducibility, complete live FAQ coverage, source conflicts, deployment security, malformed request behavior, provider availability, and production-like behavior need measured checks. A remote deployment has not been authorized or verified. Full reliability and public deployment approval are not established by the previous passing example queries.

The final audit report will record implemented fixes, validation, remaining risks, and a go/no-go recommendation. This file records findings before stabilization edits to existing application code.
