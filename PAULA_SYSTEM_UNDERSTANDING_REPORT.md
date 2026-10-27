# PAULA System Understanding Report

> This is the initial onboarding snapshot from before the response/runtime
> changes. For current activation and verification status, see
> [PAULA_RUNTIME_UPDATE_AUDIT.md](PAULA_RUNTIME_UPDATE_AUDIT.md).

**Project:** PAULA — Paulinian Artificial User Support and Learning Assistant  
**Former name:** PauliBot  
**Institution:** St. Paul University Surigao (SPUS)  
**Review date:** October 27, 2026  
**Review method:** Read-only repository and source-code analysis

## 1. Executive Overview

PAULA is an SPUS campus information assistant built around a React interface, Django APIs, PostgreSQL with pgvector, and retrieval-augmented AI responses. Its implemented scope also includes persistent student conversations, campus maps, a five-location virtual tour, announcements, profile editing, and administrative analytics and reporting.

The repository contains several generations of the project. Current source code is more extensive than the README and differs materially from older architecture documents.

This report distinguishes source-verified implementation, incomplete integration, and runtime behavior that remains unverified. It documents the existing system; it is not an improvement plan or a production certification.

### Review boundaries

- No application files were changed during the underlying technical review.
- No dependencies were installed or state-changing commands executed.
- No accounts, database records, or PostgreSQL volumes were changed.
- The local `db.sqlite3` file was not inspected or used to infer application data.
- A read-only Docker status query was denied by the execution environment. Container health, live PostgreSQL contents, applied migrations, and external API availability remain unverified.
- Application source, configuration, documentation, and available text/JSON knowledge artifacts were examined. Binary assets were inventoried where relevant; this was not an independent authenticity audit of original institutional documents or a visual audit of every image/PDF.

## 2. Project Purpose and Boundaries

PAULA stands for **Paulinian Artificial User Support and Learning Assistant**. Its current system prompt identifies it as the official AI campus assistant for Saint Paul University Surigao.

The intended purpose is to help students, parents, and visitors find university information without manually searching handbooks, websites, or multiple offices.

Supported knowledge topics include:

- Admissions and enrollment procedures.
- Academic programs and institutional policies.
- Tuition, payments, scholarships, and assistance.
- University personnel and office information.
- Campus locations and navigation.
- Office-specific procedures, including Registrar and PBMO information.

### Target users

| User category | Implemented access |
|---|---|
| Guest | Chat, announcements, map, and virtual tour; no persisted conversation history |
| Authenticated user/student | Chat plus persistent conversation threads and profile editing |
| Administrator | React analytics dashboard for superusers; Django administration for authorized staff |

“Student” is primarily an application identity. No integration was found that validates a registration against official SPUS enrollment records.

Although the name includes “Learning Assistant,” the traced implementation centers on institutional information and campus support. No dedicated tutoring engine, learning management integration, assessment system, or personalized learning workflow was found.

The prompt instructs PAULA to decline unrelated topics and answer only from supplied SPUS context. This is an implemented instruction, not proof that generated answers are always correct.

**Primary source:** [chatbot/logic.py](chatbot/logic.py).

## 3. Repository Organization

| Area | Responsibility |
|---|---|
| `paulibot/` | Django settings, project URL routing, WSGI and ASGI entry points |
| `chatbot/views.py` | Authentication, chat, conversations, profiles, announcements, analytics, and navigation endpoints |
| `chatbot/models.py` | Application and knowledge database models |
| `chatbot/serializers.py` | Registration/login validation and conversation/history serialization |
| `chatbot/backends.py` | Student ID authentication |
| `chatbot/logic.py` | Prompt construction, provider selection, generation, and direct retrieval fallback |
| `chatbot/rag.py` | Embeddings, vector retrieval, ranking heuristics, and live scraping |
| `chatbot/admin.py` | Django administration configuration |
| `chatbot/reports.py` | Analytics aggregation and CSV, PDF, and printable HTML reports |
| `chatbot/campus_nav.py` | Lazy initialization of the campus pathfinder |
| `chatbot/pathfinding_engine.py` | Image-derived walkability grid and A* routing |
| `chatbot/management/commands/` | Knowledge ingestion, seeding, and website scraping |
| `chatbot/migrations/` | Eleven application migrations |
| `chatbot/templates/`, `chatbot/static/` | Older Django-rendered frontend |
| `frontend/src/` | React application, components, API client, styles, and campus node data |
| `frontend/public/images/` | Browser-served map and tour assets |
| `knowledge_base/` | Institutional text, office JSON, extracted guides, and raw extraction artifacts |
| `images/` | Backend routing images, panorama sources, and design assets |
| `scripts/` | Image analysis, routing experiments, and diagnostic scripts |
| `scratch/` | Ad hoc authentication, OCR, and retrieval scripts |
| Root documentation | Setup guides, proposals, UML/use cases, historical walkthroughs, and evaluation text |
| `venv/`, `venv_old/` | Local Python environments; not treated as application architecture |

The repository also contains a standalone SQLite-vector proof of concept, [rag_poc.py](rag_poc.py). The active Django retrieval engine uses PostgreSQL/pgvector instead.

Several files are operational utilities rather than application entry points. In particular, `reset_admin.py` and `scratch/verify_auth.py` contain account/password mutation logic, and `fix_data.py` rewrites source data. They were inspected as text and were not executed.

## 4. System Architecture

### Main application path

```text
React browser application
    → relative /api requests through Vite during development
    → Django REST Framework views
        → Django authentication and PostgreSQL
        → PAULA logic → retrieval → PostgreSQL/pgvector
        → external LLM provider
        → campus pathfinder for route requests
    → JSON response
    → React display
```

A second presentation path remains available:

```text
Browser → Django templates → the same Django application/API layer
```

### Technology stack

| Layer | Source-verified technology |
|---|---|
| Frontend | React 19, Vite 6, Tailwind CSS 4, custom CSS |
| UI libraries | Lucide, custom MaterialIcon component, SweetAlert2 |
| Analytics visualization | Recharts |
| Virtual tour | React Photo Sphere Viewer and markers plugin |
| Backend | Django 4.2.10, Django REST Framework 3.14 |
| Authentication | Django sessions and custom Student ID backend |
| Intended database | PostgreSQL with pgvector |
| PostgreSQL adapter | Psycopg 3 |
| Embeddings | Sentence Transformers, `all-MiniLM-L6-v2` |
| Generation | Groq; OpenAI fallback; conditional Gemini support |
| Navigation | OpenCV, NumPy, SciPy, custom A* implementation |
| Document processing | PyMuPDF, Pillow, Gemini OCR/cleanup paths |
| PDF reports | ReportLab |
| Runtime | Python 3.11 Docker image, Gunicorn, Docker Compose |
| Django administration | django-unfold |

These are declared dependencies and source integrations, not a verified inventory of installed package versions.

The React application uses component state and manual pathname/history handling in `App.jsx`. Although `react-router-dom` is declared, the active application entry does not use it as its router.

The ASGI entry point is standard Django initialization. No application WebSocket or streaming response implementation was found. Chat generation uses ordinary request/response HTTP; Groq explicitly receives `stream=False`.

**Sources:** [frontend/package.json](frontend/package.json), [requirements.txt](requirements.txt), [frontend/src/App.jsx](frontend/src/App.jsx), [paulibot/asgi.py](paulibot/asgi.py).

## 5. Frontend Features and Integration Status

The active React flow is `main.jsx → App.jsx → Dashboard.jsx`, with separate authentication, registration, and administrator views.

| Feature | What the source establishes |
|---|---|
| Student login | Sends Student ID and password to `/api/login` |
| Administrator login | Uses the same login API and checks the returned superuser flag |
| Registration | Creates an account through `/api/register`, then returns to login |
| Guest entry | Creates a frontend guest identity without an account |
| Chat | Sends messages and displays complete responses after the request finishes |
| Conversation history | Lists, loads, and soft-deletes authenticated users’ threads |
| Suggested questions | Parses `[SUGGESTIONS: ...]` into clickable follow-ups |
| Formatting | Custom rendering for bold text, links, and ordered/unordered lists |
| Citations | Displays source titles and optional URLs in an accordion |
| Announcements | Fetches the newest active announcement on dashboard mount |
| Profile | Updates nickname and avatar |
| Theme | Light/dark preference stored in local storage |
| Map | Searchable destinations, origin selection, route overlay, coordinate mapper |
| Virtual tour | Aerial selection and linked 360° panorama nodes |
| Admin dashboard | Metrics, charts, filtered case list, assignments, resolution, report links |

### Integration details

1. **Session restoration:** React restores its displayed identity from `localStorage`, without first verifying the current Django session. Backend authorization remains separate.
2. **Logout:** React sends `DELETE /api/login`, but that endpoint accepts only `POST`. A `logout_user()` function exists but is not routed; `/logout/` is the functioning Django page route. The React logout path clears local state but does not implement successful backend session termination as written.
3. **Historical citations:** `ChatHistory` stores response text, not the returned sources or action metadata. React reloads only message/response text, so historical citation accordions and navigation actions are not reconstructed.
4. **Feedback:** The backend and legacy template support feedback. The active React send path discards `chat_history_id`, and no corresponding feedback submission control was found in the active dashboard.
5. **Alternative components:** `StudentDashboard`, `GuestDashboard`, `LoginPage`, and `ChatContainer` remain in the repository but are not the main dashboard path rendered by the current `App.jsx`.
6. **Response timing:** React adds a 600 ms display delay after receiving a chat response. The typing indicator is not token streaming.

**Sources:** [App.jsx](frontend/src/App.jsx), [Dashboard.jsx](frontend/src/components/Dashboard.jsx), [chatApi.js](frontend/src/api/chatApi.js), [chatbot/urls.py](chatbot/urls.py).

## 6. AI and RAG Implementation

### 6.1 Knowledge storage and embeddings

Four PostgreSQL-backed models participate in retrieval:

| Model | Embedded content |
|---|---|
| `Location` | Name and description |
| `StaffMember` | Name, position, and office |
| `FAQ` | Category, question, and answer |
| `WebResource` | Category, title, and extracted webpage content |

Each has a nullable **384-dimensional vector field**.

`RAGSearcher` loads `all-MiniLM-L6-v2` locally through Sentence Transformers. There is no external embedding API in this path.

Before every search, `ensure_embeddings()` finds records without embeddings, generates vectors, and saves them. Relevant model edits clear the existing embedding, allowing regeneration on a later search.

Consequently, an ordinary chat request can write knowledge embeddings to PostgreSQL. The review did not invoke retrieval.

### 6.2 Retrieval sequence

1. Ensure missing embeddings are populated.
2. Embed the current query.
3. Run separate L2-distance searches over all four knowledge models.
4. Retrieve up to `max(15, limit × 3)` candidates per model.
5. Merge the candidates.
6. Adjust distances using keyword and source-priority heuristics.
7. Sort the adjusted results.
8. Attempt live website retrieval if no candidates exist or the best adjusted distance exceeds `1.25`.
9. Otherwise retain results at or below `1.05`.
10. Return up to five entries to response construction.

The ranking combines vector retrieval with manually coded adjustments. It is not pure semantic similarity or a learned reranker.

Heuristics target admissions, scholarships, fees, calendars, academic programs, and contact information. Office-submitted entries receive a `0.30` distance reduction; website and staff-directory entries receive `0.15`.

The hierarchy biases ranking but does not guarantee that the correct office entry enters the initial candidate pool or wins every conflict.

No declared HNSW or IVFFlat vector index was found in the reviewed models/migrations.

### 6.3 Live website fallback

`live_scrape_query()`:

- Searches the SPUS WordPress search endpoint.
- Selects the first extracted article link.
- Fetches and strips HTML.
- Reuses an existing `WebResource`, or saves truncated content and an embedding.
- Returns the content for immediate response generation.

This makes retrieval partly capable of expanding its own knowledge store. It is not a scheduled synchronization service or a comprehensive search engine.

The live fallback result omits the normal `source_type` metadata, so its context label defaults to the generic verified-knowledge label even when a website URL is present.

### 6.4 Prompt construction

`PauliBotLogic` builds a separate system prompt and a user message containing retrieved context.

Implemented instructions include:

- SPUS-only scope.
- Context-grounded answers and an unknown-information response.
- English, Filipino, and Taglish response matching.
- Focused answers for personnel questions.
- Office → website/directory → handbook source preference.
- Numbered lists for procedural questions.
- Exactly three follow-up suggestions.
- Complete program listings when requested.

Source labels include fixed years such as “2027” for website/directory information. Those labels are generated by code; they do not establish the source’s actual publication date or freshness.

For authenticated conversations, the backend supplies the last five exchanges as context. Guests do not receive equivalent history because their earlier browser messages are not sent in the chat payload.

### 6.5 Provider selection and fallback

| Stage | Actual behavior |
|---|---|
| Groq | Preferred; discovers and probes available models, beginning with Llama 3.3 70B |
| OpenAI | Uses `gpt-4o-mini` when configured and Groq is unavailable or fails |
| Gemini | Initializes `gemini-1.5-flash` only when neither Groq nor OpenAI client initialized |
| Direct retrieval | Extracts and ranks retrieved text if no provider is available or generation fails |

Gemini is not always an available third runtime fallback after Groq and OpenAI fail. Its availability depends on initialization conditions.

The Gemini generation branch does not include the conversation history passed to the Groq/OpenAI branches.

The direct fallback uses keyword scoring, FAQ preferences, extraction, deduplication, and canned suggestions. It does not provide the same language behavior as the LLM prompt; substantial fallback text is English.

### 6.6 Citations and provenance

Returned citations describe retrieved entries, rather than proving which statements the model used. The response sets citation `page` to `None`; page-level handbook citations are not structured into the returned sources.

**Sources:** [chatbot/rag.py](chatbot/rag.py), [chatbot/logic.py](chatbot/logic.py), [chatbot/views.py](chatbot/views.py).

## 7. Knowledge Sources and Ingestion

| Command | Implemented function |
|---|---|
| `seed_knowledge` | Copies legacy locations, staff, and FAQs from `chatbot/data.py` |
| `ingest_knowledge_txt` | Parses selected sections of `knowledge_base/knowledge base.txt` into FAQs |
| `ingest_handbook` | Renders PDF pages and uses Gemini 2.5 Flash for OCR |
| `ingest_text_handbook` | Extracts PDF text with PyMuPDF and uses Gemini for cleanup |
| `ingest_office_faqs` | Parses JSON, CSV, DOCX, PDF, TXT, and Markdown into office FAQs |
| `scrape_spus` | Scrapes configured institutional pages into chunked `WebResource` records |

The website scraper targets SPUS pages and selected institutional Google Sites/library resources. Its chunks target approximately 1,200 characters and retain trailing lines between chunks. Handbook chunks target approximately 900 characters; unstructured office text defaults to 800.

### Office knowledge artifacts

The Registrar JSON contains **8 entries**, covering subject changes, continuing-student enrollment, transferee/freshman procedures and requirements, ID issuance, and approval signatures.

The PBMO JSON contains **14 entries**, covering office services, publication submissions, event coverage, operating hours, online posting, and branding.

Extracted Markdown guides and raw text artifacts also exist under `knowledge_base/office_documents/extracted/`.

### Important distinctions

- Placing or editing a JSON file does not automatically update the retrieval database.
- The office ingestion command must run, or corresponding database records must be edited.
- Office identity and category come from command arguments/defaults; the parser does not automatically adopt all top-level JSON metadata.
- `chatbot/data.py` identifies itself as MVP mock data. Its existence is not evidence that its institutional facts are verified.
- The text-handbook ingestion command does not explicitly set `source_type='handbook'`, unlike the OCR handbook command. Newly created entries can retain the model’s `curated` default.
- DOCX and optional RapidOCR branches import packages that are not explicitly listed in `requirements.txt`.

Ingestion code and available text/JSON artifacts were verified. Whether these sources have been ingested into current PostgreSQL remains unknown. Institutional facts were not independently validated against original signed documents.

**Sources:** [management commands](chatbot/management/commands/), [Registrar knowledge](knowledge_base/office_documents/Registrar/Registrar_knowledge.json), [PBMO knowledge](knowledge_base/office_documents/PBMO/PBMO_knowledge.json), [legacy seed data](chatbot/data.py).

## 8. Database Models and Relationships

The application defines **nine domain models**:

| Model | Role |
|---|---|
| `CustomUser` | Django user plus nullable unique Student ID, nickname, avatar |
| `Conversation` | Owned thread, title, timestamps, active flag |
| `ChatHistory` | User question and bot response, optional thread, timestamp, feedback |
| `Location` | Campus location description and embedding |
| `StaffMember` | Personnel information and embedding |
| `FAQ` | Question/answer, category, source type/office, embedding |
| `WebResource` | URL, title, category, scraped text, timestamp, embedding |
| `StudentNeed` | Student support case, urgency, status, advisor text, description |
| `Announcement` | Active/inactive campus notice |

```text
CustomUser
  ├─ many Conversations
  ├─ many ChatHistory records
  └─ many StudentNeeds

Conversation
  └─ many ChatHistory records
```

These relationships use cascading deletion. Conversation deletion through the API instead sets `is_active=False`, leaving stored messages in place.

Other schema details:

- Student IDs are optional for administrative/staff accounts.
- Staff office and assigned advisor are text fields, not relational links.
- Knowledge entries have no version/approval workflow model.
- Chat records do not store model identity, retrieval scores, token usage, latency, or structured citations.
- Chat history includes timestamp and compound lookup indexes.
- Source metadata is richer for FAQs than for locations/personnel.

The migrations add vectors but do not explicitly create the PostgreSQL `vector` extension. An image containing pgvector does not by itself prove that extension creation occurred in the application database.

**Sources:** [chatbot/models.py](chatbot/models.py), [chatbot/migrations/](chatbot/migrations/).

## 9. Authentication, Authorization, and Security

### Implemented mechanisms

- Django password hashing through `create_user()` and `check_password()`.
- Student ID lookup, with username authentication fallback.
- Session authentication for APIs.
- CSRF middleware and browser CSRF header handling.
- Explicit CORS origins with credentials enabled.
- HTTP-only session cookies.
- Secure session/CSRF cookies when `DEBUG=False`.
- Owner-filtered conversation/history access.
- Explicit superuser checks on React dashboard APIs.
- Django staff/model permissions for administration.
- Environment-based key/database settings and ignored environment files.

### Observed boundaries and incomplete protections

| Area | Source finding |
|---|---|
| Registration | No university enrollment verification or email verification found |
| Password validation | Validators are configured, but the registration serializer does not explicitly call Django password validation |
| Feedback authorization | Anonymous requests are not rejected; ownership is checked only for authenticated callers |
| Student ID backend | Its direct password-success branch does not apply `user_can_authenticate()`; API login separately checks active status |
| CSRF bootstrap | `ensureCsrfToken()` calls a protected conversations endpoint that does not explicitly ensure a CSRF cookie |
| Uploads | Profile API assigns uploaded avatars without explicit size/type validation in that view |
| Error handling | Several endpoints return raw exception strings |
| Case updates | Status/urgency values are assigned without serializer-based choice validation |
| Abuse controls | No application throttling, login lockout, or CAPTCHA configuration found |
| Configuration | Settings include development fallback values for secret/database configuration |
| Operational scripts | Account-reset scripts contain fixed credentials; execution was not attempted |

These findings describe source behavior, not evidence of exploitation or the live deployment’s exposure.

For AI security, context grounding and conflict handling rely primarily on prompting and retrieval heuristics. No separate claim-verification or prompt-injection detection stage was found.

**Sources:** [settings.py](paulibot/settings.py), [backends.py](chatbot/backends.py), [serializers.py](chatbot/serializers.py), [views.py](chatbot/views.py).

## 10. Campus Navigation and Virtual Tour

### Image-based routing

The active map module sends percentage coordinates to Django. The backend:

1. Loads the green-highlighted pathway image.
2. Extracts walkable regions using HSV color thresholds.
3. Applies morphological closing to bridge gaps.
4. Downsamples the mask by four.
5. Builds a distance transform and KD-tree.
6. Snaps endpoints to walkable pixels.
7. Calculates an eight-direction A* path.
8. Returns percentage coordinates for the frontend overlay.

The distance transform influences route cost, favoring wider portions of pathways.

Although frontend graph data and a Dijkstra utility remain, the active `MapModule` calls the Python A* API.

The returned `distance_pixels` is based on path length and scale. The frontend converts it into an approximate walking time using a fixed factor. It is not a verified physical distance or calibrated travel-time model.

### Virtual tour

The tour defines five panorama nodes:

- Cafeteria hallway.
- Administrative hallway.
- Main entrance.
- Main entrance lobby.
- Campus court.

Marker clicks connect these scenes. This is a linked panorama tour rather than a full 3D campus reconstruction. Coordinate mapping and calibration helpers remain exposed in the source.

**Sources:** [campus_nav.py](chatbot/campus_nav.py), [pathfinding_engine.py](chatbot/pathfinding_engine.py), [MapModule.jsx](frontend/src/components/MapModule.jsx), [VirtualTour.jsx](frontend/src/components/VirtualTour.jsx), [campusGraph.js](frontend/src/data/campusGraph.js), [dijkstra.js](frontend/src/utils/dijkstra.js).

## 11. Administration, Analytics, and Reporting

| Surface | Purpose |
|---|---|
| Django `/admin/` | User, knowledge, conversation, feedback, case, and announcement management |
| React admin view | Institutional metrics, charts, case filters/actions, report downloads |

The reporting engine calculates query totals, conversations, feedback satisfaction, case status/urgency distributions, high-priority cases, and keyword-based topics.

### Metric interpretation

- **Total enrolled:** active non-superuser application accounts.
- **At risk:** a student with an open/in-progress High or Critical support case.
- **Pending enrollments:** unresolved Enrollment cases.
- **Satisfaction:** recorded positive/negative feedback; defaults to **100% when no feedback exists**.
- **Trending topics:** substring keyword classification, not an AI classification model.
- A message can count toward multiple topic categories.
- Guest chats are absent from saved-chat analytics.
- Soft-deleted conversations/messages remain represented in several totals.

Student support cases can be managed through Django admin and updated through the React dashboard. No automatic case creation from chat, student-facing case submission endpoint, or advisor notification workflow was found.

One source defect affects case search: `admin_student_needs()` references `models.Q`, but `views.py` does not import `models`.

The React dashboard’s Django-admin link points to `localhost:8000`, which differs from the current Docker host port.

**Sources:** [admin.py](chatbot/admin.py), [reports.py](chatbot/reports.py), [views.py](chatbot/views.py), [AdminDashboard.jsx](frontend/src/components/AdminDashboard.jsx).

## 12. API Surface

Routes are defined in [chatbot/urls.py](chatbot/urls.py).

| Endpoint/group | Purpose and access |
|---|---|
| `POST /api/register` | Public account registration |
| `POST /api/login` | Public session login |
| `POST /api/chat` | Guest/authenticated chat |
| `GET /api/history` | Authenticated user’s saved exchanges |
| `GET, POST /api/conversations` | Authenticated thread listing/creation |
| `GET, DELETE /api/conversations/<id>` | Owner-filtered retrieval/soft deletion |
| `PATCH /api/feedback/<id>` | Feedback update; anonymous authorization gap described above |
| `GET /api/announcements` | Latest active announcement |
| `PATCH /api/profile` | Authenticated nickname/avatar update |
| `POST /api/navigation/route/` | Campus route calculation |
| `/api/admin/campus-pulse/` | Superuser activity heatmap data |
| `/api/admin/trending-confusion/` | Superuser keyword topic counts |
| `/api/admin/metrics/` | Superuser metrics |
| `/api/admin/student-needs/` | Superuser filtered/paginated case list |
| `/api/admin/student-needs/<id>/` | Superuser case updates |
| `/api/admin/reports/data/` | Superuser report dataset |
| `/api/admin/reports/print/` | Superuser printable report |
| `/api/admin/reports/export/csv/` | Superuser CSV exports |
| `/api/admin/reports/export/pdf/` | Superuser PDF exports |

Legacy page routes include `/`, `/chat/`, `/register/`, `/login/`, and `/logout/`. The project URL configuration also exposes Django `/admin/`.

## 13. Development and Deployment

| Component | Configuration |
|---|---|
| PostgreSQL container | `paulibot_postgres`, `ankane/pgvector:v0.5.1`, host port 5432 |
| Django container | `paulibot_web`, host 8080 → container 8000 |
| Web startup | Migrations → static collection → Gunicorn with three workers |
| Persistence | `postgres_data` and `static_volume` |
| Networking | Private Compose bridge network |
| Development mount | Repository mounted at `/app` |
| Vite | Port 5173; `/api` proxy to `http://127.0.0.1:8080` |

PostgreSQL in Docker is the intended runtime under [AGENTS.md](AGENTS.md). The SQLite fallback remains in settings but was not used in this review. Database checks and management commands belong in the Docker web service, and PostgreSQL volumes must be preserved.

Deployment preparation exists, but a complete production serving arrangement is not established by the repository:

- No frontend build/service is included in Compose.
- No reverse proxy, TLS configuration, or production static/media server is defined.
- Gunicorn alone does not establish static/media serving.
- Vite proxies `/api`, not `/media`.
- `OPENAI_API_KEY` is read by settings but not explicitly passed in the Compose environment block.
- The repository listing did not contain an environment file; effective runtime configuration remains unknown.
- No CI pipeline or comprehensive automated test suite was identified.

The bot initializes at module import in `views.py`. Initialization loads the embedding model and may probe Groq models with generation requests. Under multiple Gunicorn workers, initialization can occur per worker.

The frontend `npm start` script and older local setup scripts launch host Python/Django commands and do not match the intended Docker/PostgreSQL workflow.

Ad hoc retrieval and navigation diagnostic scripts exist. They were not executed and do not establish measured system accuracy or production readiness.

**Sources:** [docker-compose.yml](docker-compose.yml), [Dockerfile](Dockerfile), [vite.config.js](frontend/vite.config.js), [frontend/package.json](frontend/package.json), [setup_local.ps1](setup_local.ps1).

## 14. End-to-End Workflows

| Workflow | Traced behavior |
|---|---|
| Student registration | React form → registration serializer → hashed account creation → return to login |
| Student login | Student ID/password → authentication backend → Django session → frontend identity |
| Authenticated chat | Message/thread ID → last five exchanges → retrieval → generation/fallback → save exchange → return response, sources, IDs, action |
| Guest chat | Message → retrieval/generation → return response without conversation/history persistence |
| Conversation loading | Owner-filtered thread → stored exchanges → text reconstruction in React |
| Conversation deletion | Owner-filtered thread → mark inactive |
| Knowledge update | Admin edit or ingestion → invalidate/populate embedding → later retrieval uses database content |
| Map request | Location phrase → keyword destination → open map → select origin → A* API → route overlay |
| Support case management | Existing case → admin filtering → advisor/status update → refreshed metrics |
| Reporting | Superuser request → database aggregation → JSON, printable HTML, CSV, or PDF |

Guest privacy requires precise wording: guest exchanges are not stored in `ChatHistory`, but retrieval can save website content, external providers receive the question/context, and application logging includes query text. “No chat history persistence” is supported; “no data collection anywhere” is not.

## 15. Documentation Compared with Implementation

| Documentation statement | Current implementation |
|---|---|
| Primarily Django templates | React application plus retained Django pages |
| Gemini as main chat provider | Groq preferred, OpenAI fallback, conditional Gemini |
| Gemini 2.5 for chat | 2.5 appears in ingestion; conditional chat uses 1.5 |
| Three retrieved entries | Current logic requests five |
| PostgreSQL 16 Alpine / psycopg2 | Compose uses a pgvector image; requirements use Psycopg 3 |
| Backend host port 8000 | Current Compose exposes 8080 |
| Registration automatically logs in | React API flow returns to login |
| `/api/logout` exists | Function exists but is not routed |
| Guest privacy described absolutely | No persisted guest exchanges, but other processing remains |
| AI “learns” knowledge edits | Database retrieval and embedding regeneration; no model training |
| Production-ready / guaranteed accuracy | Not established by static source review |

`system_design_draft.md.resolved` refers to SPUP in places, whereas the active application identifies SPUS. Older documents contain machine-specific paths and describe previous project stages.

The evaluation document’s acceptance language is repository text, not independently verified institutional approval or measured system validation.

Relevant documentation includes:

- [README.md](README.md)
- [SETUP_GUIDE.md](SETUP_GUIDE.md)
- [LOCAL_DEV_GUIDE.md](LOCAL_DEV_GUIDE.md)
- [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md)
- [SUCCESS.md](SUCCESS.md)
- [Proposed system description](proposed_system_description.md.resolved)
- [System design draft](system_design_draft.md.resolved)
- [Use case specifications](use_case_diagram_and_specifications.md)
- [UML diagrams](uml_diagrams.md.resolved)
- [Historical walkthrough](walkthrough.md.resolved)
- [Evaluation document](evaluation_report.md.resolved)

## 16. Implemented, Partial, and Unverified Capabilities

| Classification | Capabilities |
|---|---|
| Implemented in source | Session login, registration, guest chat, authenticated conversation persistence, vector retrieval, provider generation/fallback, knowledge ingestion, Django knowledge administration, announcements, profile updates, image-based routes, panorama tour, analytics, report exports |
| Partially integrated | React logout, React feedback, session restoration, historical source/action restoration, profile media serving across development origins, case search, conditional Gemini failover |
| Supporting code exists but is not the active path | Django template frontend, alternative React dashboard components, frontend Dijkstra utility, SQLite-vector proof of concept |
| Documented intent or unproven quality target | 24/7 availability, 3–5 second responses, guaranteed factual accuracy, production readiness, campus-wide scalability |
| Not found in traced implementation | Enrollment-system verification, automatic support-case detection/creation, advisor notifications, dedicated tutoring/LMS integration, token streaming, scheduled knowledge synchronization |

Absence from the reviewed implementation does not establish a committed future roadmap. Planned work should be confirmed with the project team rather than inferred from UI labels or dependencies.

## 17. Unknowns and Verification Limits

This review establishes the application’s source architecture and integration paths. It does not establish:

- Running container health or PostgreSQL connectivity.
- Applied migration state or installed vector extension.
- Actual accounts, knowledge counts, cases, announcements, or embeddings.
- Which AI keys/providers currently work.
- Original-document authenticity or current institutional accuracy.
- Browser behavior across devices and deployment origins.
- Retrieval accuracy, multilingual quality, hallucination rate, latency, or concurrent capacity.
- Operational backups, monitoring, hosting, or availability guarantees.

PAULA’s implemented foundation is a database-backed campus assistant with substantial supporting functionality. Its main onboarding distinction is the coexistence of current React/RAG features, older Django workflows, and documentation from earlier stages. This report records those boundaries without treating declarations or historical completion claims as runtime proof.
