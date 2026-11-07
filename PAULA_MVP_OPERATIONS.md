# PAULA MVP operations and demonstration checklist

Use the validated Git source, the existing PostgreSQL data volume, and the pinned 384-dimensional MiniLM revision together. Local tests are not remote deployment approval. Django 4.2.10 is still installed; follow [the separate LTS upgrade plan](PAULA_DJANGO_LTS_UPGRADE_PLAN.md) before public deployment.

## Before the demonstration

1. Open this GitHub workspace, not another checkout. Keep credentials in the existing external environment file. Never copy `.env` into the repository or Docker image.
2. Keep `paulibot_postgres` running with its existing volume. If the web container is already present, start it with `docker start paulibot_web`. To recreate **only** the development web service from this workspace, use `scripts/start_workspace_backend.ps1 -EnvFile '<existing env file>'`; it checks the mount and PostgreSQL container identity. The launcher does not rebuild an image or upgrade dependencies.
3. Wait for `http://127.0.0.1:8080/api/health/ready`: `ready=true`, all expected workers ready, `database_ready=true`, `knowledge_available=true`, `index_complete=true`. Cold preparation takes roughly a minute in this workstation; do this before the demonstration. `/api/health/live` only checks process liveness.
4. Run `powershell -File scripts/verify_mvp.ps1`. It runs Django checks/test fixtures in Docker PostgreSQL, reads active KB health, and tests/builds React. It never indexes or changes active knowledge. Docker must permit creation/use of Django's separate test database; it never substitutes SQLite or creates replacement application accounts.
5. In the frontend terminal, run `npm run dev` from `frontend`, then open `http://localhost:5173/`. Vite proxies `/api` to Docker port 8080. Do not start a second `manage.py runserver` against a different environment.
6. Sign in through React `/admin` for Institutional Analytics and admin map editing. Django content management is `http://localhost:8080/admin/`. Guests/students must not see map editing controls; signing into Django and a saved React guest identity are separate states until the explicit session handoff is used.
7. Run `powershell -File scripts/verify_mvp.ps1 -Live` after readiness for the repeatable live guest matrix. It includes typo/social requests, FAQs, personnel, multi-part questions, navigation, enrollment continuity, Filipino follow-ups, and unsupported questions. Providers may be called; no live messages are saved. An after-run fails if any scripted check fails. Artifacts contain synthetic public questions and responses, not user conversations.

## Knowledge and index maintenance

```powershell
docker exec paulibot_web python -B manage.py audit_knowledge --strict
docker exec paulibot_web python -B manage.py index_knowledge
docker exec paulibot_web python -B manage.py prepare_embedding_model
```

The strict read-only gate checks the PostgreSQL backend, vectors, exact FAQ conflicts, and source self-matches. Self-matching is an index regression measure, not independent institutional truth or multilingual recall. Readiness exposes missing-vector counts but allows exact FAQ paths to continue during partial indexing. `index_knowledge` is a dry run by default. After a reviewed import, use `index_knowledge --apply` explicitly to fill **missing** vectors only. It never refreshes existing embeddings automatically. Admin source edits index that record; a failed index leaves the fact saved and displays a warning. Other batch/crawler workflows must complete explicit maintenance and the strict audit before release.

Never run the legacy `seed_knowledge` against existing data; the command now refuses a nonempty knowledge database. Its old starter facts are not the reviewed current corpus. Raw office files and supplementary CSVs are not automatically imported by startup. Preserve manual corrections and review conflicts.

For a new environment, use an approved source snapshot and matching model revision. Export only the public knowledge tables using Django `dumpdata` through the Docker web service into a protected artifact location outside Git; separately retain the database backup, encoder revision, vector dimensions, counts, source-review manifest, and checksums. Test restoration on an isolated PostgreSQL instance before any cutover. Do not run `loaddata` or a full backup restore against the active development database as a routine setup step. Full backup/restore and cloud cutover are not validated by this pass.

On a fresh model-cache volume, `prepare_embedding_model --download --verify` is an explicit network preparation step for the pinned MiniLM revision. It is never performed by a chat request or implied by the default cache check. The normal readiness hooks load/warm one compatible cached model per worker; do not use Gunicorn preloading to fork an already-initialized Torch runtime. Choose worker count using measured memory on the deployment host.

## Failure diagnosis

* A 200 reply with `answer_status=no_match` means no eligible evidence was returned; `clarification`, `ambiguous`, `conflict`, `selection_rejected`, and `unavailable` identify other outcomes. Compound replies retain per-part status. Do not label all of them a model hallucination or network failure.
* Operational JSON logs include request/worker IDs, stage times, SQL counts and provider outcomes without prompts, identities, answers, SQL text, or credentials. Match the UI request to `X-Request-ID`; inspect provider cooldown/timeouts before changing models or thresholds.
* Database exceptions at the API boundary return a safe 503; exceptions caught by the retrieval layer produce an explicit temporary-unavailability answer. Unexpected API errors return a safe 500. Navigation failure is isolated from FAQ responses. Frontend chat delivery has a 30-second deadline covering JSON reading, and never retries a saved message automatically.
* The browser timing is transport time; startup readiness is measured separately. Never present an unverified streamed answer to make latency appear lower.

## Repeatable release and rollback

1. Review/commit **all** required source files, including currently new modules/tests, frontend assets, `images/` pathfinder inputs, migrations and configuration. Record the commit and approved KB fingerprint. A working directory and a GitHub release are different things.
2. Run CI using the isolated `docker-compose.ci.yml`, separate PostgreSQL fixtures and no provider keys. Local Compose syntax/tests pass; the new remote Actions run and fresh dependency/image build still need execution on the published candidate. Do not substitute the current bind-mounted development image for a validated immutable release.
3. Build a clean image with `.dockerignore`; prepare the pinned cache explicitly. The Dockerfile selects the existing CPU Torch version and Gunicorn readiness hooks. Verify the built image, package inventory, assets, static collection and readiness; the Dockerfile default does not perform migrations automatically. Apply reviewed migrations as a deliberate deployment step.
4. Configure `DJANGO_SETTINGS_MODULE=paulibot.settings_production`, `DEBUG=false`, a strong secret, PostgreSQL credentials, explicit hosts, HTTPS frontend origin, CORS and CSRF origins. The supplied development Compose does **not** switch to these settings automatically. Only trust forwarded HTTPS headers behind a controlled proxy that removes client-supplied headers. Same-origin frontend `/api` routing is simplest for current session cookies; cross-site hosting needs separate cookie/CSRF verification.
5. Validate HTTPS, authenticated and guest switching, admin assets and map editing on the actual host. Re-run the live guest matrix against that host and test simultaneous users on the target resources. The current local scripts' base URL is configurable; the operational PowerShell wrapper assumes the local Docker service.
6. Preserve the preceding release image/source and a verified PostgreSQL backup. Before rollback, inspect differences and retain a checkpoint of newer work. Roll back reviewed application paths/release images selectively; never `git reset --hard`, delete volumes, or restore an old DB just to undo these source-only fixes. This stabilization creates no schema migration.
7. Keep Django, dependency security review, admin/login rate limiting, student-registration policy, upload validation/media isolation, monitoring and a tested backup/restore process on the public-release checklist. A local smoke pass does not certify these controls or RA 10173 compliance.

## Demonstration cases

Use real knowledge responses, not replacement canned facts:

| Flow | Input/action | Expected behavior |
| --- | --- | --- |
| Social and typo | `ty`, `thankyoui`, `THANK YOU`, `salamat kaayo` | Friendly local response, no institutional claim/source or provider needed |
| Identity | `who you?` | PAULA identity and usable suggested questions |
| Overview and rationale | `TELL ME ABOUT SPUS AND WHY SHOULD I ENROL` | Two separately supported stored answers |
| Programs | `What programs are offered?` | Stored program FAQ, not missing-information fallback |
| Personnel | `Who is the ICT Director and CEIT Dean?` | Independently supported identities and sources |
| Enrollment | `How do I enroll?` → continuing student → `How about transferee?` → `Ano naman ang requirements?` | Ask category; retrieve correct procedure, retain category for document follow-up |
| Navigation | `Where is the Registrar office?` | Open map; choose start and compute route; no editing for guests |
| Missing/partial knowledge | President in an unsupported future year; overview plus UnknownXYZ Academy | Abstain on unsupported facts; preserve independently supported portion |
| Source consistency | Run strict knowledge audit | No missing/invalid/zero vectors or conflicting equivalent FAQs |
| Privacy | Guest chat, sign in, new/resumed threads, sign out | Guest turns never persist; authenticated history grouped and isolated by owner/thread; automated fixtures cover switching and ownership |

Browser interactions, target-device navigation/360 tour, real authentication switching, and concurrency must also be rehearsed manually on the intended demonstration device. The new transport tests are not a fresh comprehensive mobile/browser accessibility audit.
