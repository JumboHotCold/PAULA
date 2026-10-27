# PAULA Complete Runtime Update Audit

> Historical audit snapshot. The later administrator-page crawl and personnel
> retrieval update changes the source hashes and website record counts below.
> See [PAULA_WEBSITE_KNOWLEDGE_UPDATE.md](PAULA_WEBSITE_KNOWLEDGE_UPDATE.md)
> for the latest website ingestion and live verification.

**Date:** October 27, 2026.  
**Scope:** All changes made during the system review, grounding work, enrollment/navigation work, OCR rerun, and runtime activation.

## Which folder is active?

The active application source is now:

```text
C:\Users\ADMIN\Documents\GitHub\paulibot
```

Docker mounts this local repository at `/app`. The old OneDrive source folder is
no longer the application code mount. Docker Compose originally used OneDrive
because the existing web service had been started from that older checkout; it
did not automatically switch when another copy was opened in the IDE.

The only remaining OneDrive configuration dependency is the existing private
environment file:

```text
C:\Users\ADMIN\OneDrive\DEX CAPSTONE 2026\paulibot\.env
```

It is reused in place. Secrets were not copied into this repository or printed.
The local folder named `GitHub` is a checkout, not the GitHub cloud service.
Docker uses local files; a GitHub push is not required to activate them. No
commit or push was performed for these changes.

## Use the correct interface

| Address | Role |
|---|---|
| `http://localhost:5173` | Current React/Vite application: chat, maps, tour, and React dashboards |
| `http://127.0.0.1:8080` | Docker Django backend, APIs, administration, and retained legacy pages |

Vite currently listens on IPv6 localhost (`::1`), which explains why checking
`127.0.0.1:5173` alone incorrectly suggested it was stopped. Its running process
uses this GitHub checkout. The React API proxy reaches the Docker backend on 8080.

Refresh an existing browser tab to load the latest JavaScript. The Django
`/chat/` page also has updated guest clarification handling, but it does not
contain the React map/tour modules.

## Audit results by change group

| Change group | Current evidence |
|---|---|
| Entire checked source set | SHA-256 comparison matched workspace and Docker bytes for 26 files, including logic, retrieval, views, settings, frontend changes, tests, helpers, knowledge JSON, and review documents |
| Grounding/retrieval | Current cosine-distance gate, entity/topic/audience checks, authority tie-breaking, and rejection of unrelated evidence are active |
| Reported CEIT failure | Live request through React's proxy abstained; no calendar response or citations were returned |
| Response/fallback logic | Stored-excerpt rendering, validated evidence-ID selection, single retrieval, provider-outage fallback, and selected-source citations are active; regression tests exercise invalid output and provider failures |
| Enrollment clarification | Live `How do I enroll?` asks category; freshman, transferee, and old-student replies return their respective Registrar procedures |
| Typo handling | Live `enorll` enrollment and `Wher ... registar` navigation cases passed |
| Navigation/disambiguation | Live Registrar/Finance navigation actions and multiple-destination clarification passed; online-payment question did not open a map |
| Actual A* routing | A live route from Main Entrance to Registrar returned 780 path points; this verifies calculation, not physical accessibility or calibrated walking time |
| React changes | Current App, API client, and MapModule sources were fetched from Vite; latest production build passed |
| Map/tour assets | Map image and all five referenced panorama images returned HTTP 200 |
| Guest clarification | Current React and legacy payload support is active; live guest checks returned `saved: false`; regression test verifies no guest chat creation |
| Runtime dependencies | All declared package specifications match installed versions; `pip check` reports no broken requirements |
| Missing dependency repair | Persistent runtime-image update installed OpenAI 2.54.0, Psycopg 3.3.6/binary, and ReportLab 5.1.0 from existing requirements |
| Provider initialization | Groq and OpenAI clients initialize successfully; Gemini is not configured in the current environment |
| PDF report dependency | Actual report generation succeeded with a valid PDF header; no report contents were exposed |
| PostgreSQL | Active driver is Psycopg 3; pgvector extension is present; no pending migrations; no missing knowledge embeddings |
| Existing office JSON vs database | All 22 Registrar/PBMO entries match their existing JSON answers/source metadata |
| Automated OCR | All four PDFs/16 pages processed; 106 review artifacts are present; source PDF hashes remain unchanged |
| Regression suite | All 47 tests passed directly through the active Docker/Django service; Django system checks found no issues |

The live proxy audit contains 11 passing cases. Additional checks cover served
modules/assets, an A* route, client initialization, PDF generation, source
hashes, schema status, office JSON consistency, and OCR integrity.

## What Docker does and does not update automatically

| Change | Required activation |
|---|---|
| Python source in this bind-mounted repository | Files become visible immediately, but Gunicorn workers need reload/restart to import changed code |
| React source | Vite serves updates; refresh stale browser tabs. A deployed frontend needs a rebuilt bundle |
| Python dependencies | Rebuild/update the runtime image, then recreate the web service |
| Database models/schema | Explicit Django migrations through the Docker web service |
| FAQ/office JSON/PDF content | Explicit, reviewed ingestion or database edits; changing a file does not automatically replace database knowledge |
| OCR review outputs | Review artifacts only; they are not automatically ingested |

PostgreSQL data lives in its Docker volume, independently of whether application
source is under OneDrive or the GitHub checkout. Source-code changes do not
belong inside database tables. The existing database/container was preserved.

## OCR corrections remain a separate review step

The 22 database/JSON matches establish synchronization with the **existing
JSON**, not factual approval of every answer. The OCR recheck found unresolved
name/credential, publication, branding-exception, historical-claim, and document
identifier/requirement issues. Those were deliberately not silently applied to
JSON or PostgreSQL.

See [OCR findings](knowledge_base/office_documents/extracted/ocr_review_2026-10-27/MANUAL_REVIEW_NOTES.md).
The reviewed source PDFs, original knowledge JSON, and existing student/account
records were not replaced. No replacement accounts were created.

## Runtime-image and configuration details

The dependency update reused the installed application image and installed the
current `requirements.txt` in a new image layer. Its build context contained only
the requirements file. Application code in this development runtime is supplied
by the GitHub bind mount; this was not a fresh production-image certification.

The existing environment file stays outside this checkout. Startup explicitly
sets the local Django debug mode, avoiding an inherited `DEBUG=release` collision.
MiniLM downloads persist in `paulibot_model_cache`. Clarification/navigation paths
do not import Sentence Transformers/PyTorch; first retrieval loads it lazily.
Gunicorn's worker timeout is 120 seconds to accommodate cold loading.

## Reproduce the checks

```powershell
.\scripts\start_workspace_backend.ps1 -EnvFile "C:\Users\ADMIN\OneDrive\DEX CAPSTONE 2026\paulibot\.env" -DjangoDebug true
docker exec paulibot_web python -B manage.py test chatbot.test_grounding chatbot.test_intents --verbosity 1
docker exec paulibot_web python -B -m pip check
docker exec paulibot_web python -B scripts/audit_runtime_state.py
docker exec paulibot_web python -B scripts/evaluate_grounding.py
```

The state audit enforces a read-only PostgreSQL transaction and does not print
credentials or account records. The retrieval smoke evaluation disables
embedding writes and makes no LLM calls. Use PostgreSQL in Docker; do not switch
to SQLite or remove PostgreSQL volumes.

Supporting snapshots:

- [PAULA_RUNTIME_AUDIT.json](PAULA_RUNTIME_AUDIT.json): package, source, schema, office-data, and OCR-artifact checks.
- [PAULA_LIVE_AUDIT.json](PAULA_LIVE_AUDIT.json): live proxy cases and results.

## Limits of this audit

Passing these checks does not establish zero hallucinations, institutional source
authenticity/currency, complete browser interaction coverage, production
readiness, or provider quotas. Provider failure behavior was exercised with
mocks; paid external failover/quota availability was not tested. Existing issues
outside the session's changes remain separate from this activation audit.
