# PAULA admin and development runtime

Verified: November 7, 2026.

## Which interface to use

| Address | Interface | Purpose |
| --- | --- | --- |
| http://localhost:5173/ | React PAULA | Current chatbot, campus map, virtual tour, and student/guest interface |
| http://localhost:5173/admin | React Institutional Analytics | Existing campus-wide student needs dashboard, reports, and monitoring |
| http://localhost:8080/admin/ | Django Unfold | Knowledge records, users, announcements, conversations, and other administrative records |
| http://127.0.0.1:8000/ | Separate local `runserver`, if started | Unnecessary for the intended Docker development setup |

React sends `/api` requests through Vite to `http://127.0.0.1:8080`. Docker maps host port 8080 to Django's internal port 8000. **Docker's internal port 8000 and a separate Windows `runserver` on host port 8000 are different servers.**

Django's root `/` and `/chat/` routes still render legacy templates. Their appearance does not represent the current React UI. These routes/files have been preserved; use port 5173 for the application.

## Normal startup

1. Start Docker Desktop. Ensure `paulibot_postgres` and `paulibot_web` are running. They run in the background; no Django terminal is needed.
2. Stop the separate `python manage.py runserver` process with **Ctrl+C in its terminal**. Do not stop or remove the database volume.
3. In a frontend terminal:

   ```powershell
   cd C:\Users\ADMIN\Documents\GitHub\paulibot\frontend
   npm run dev
   ```

4. Open `http://localhost:5173/`. After a backend restart, wait for readiness before testing semantic queries:

   ```powershell
   Invoke-RestMethod http://localhost:8080/api/health/ready
   ```

   Expect `ready: true` and all three workers ready. The latest measured worker initialization was approximately 47–48 seconds; this is startup time, not a guarantee for future starts or request latency.

`npm start` now starts Vite only, too. It no longer launches a second Django process or kills processes using port 8000.

Existing stopped containers can also be started with `docker start paulibot_postgres` and then `docker start paulibot_web`. For a deliberate web recreation using the existing environment configuration, use the workspace launcher:

```powershell
.\scripts\start_workspace_backend.ps1 -EnvFile '<path to your existing environment file>'
```

Run that from the repository root, supplying the real environment-file path. The launcher verifies PostgreSQL remains enabled, preserves its container, verifies this workspace's code mount, and waits for all workers. Credentials were reused in place during this change, not copied into the repository or this guide.

## Administrator workflow

1. Open `http://localhost:5173/admin` and sign in using an existing administrator account.
2. Keep using **Institutional Analytics** for monitoring, student needs, and reports.
3. Select **Knowledge & User Administration** to open Unfold at `http://localhost:8080/admin/`.
4. Use Unfold's **PAULA Workspace** links to return to Institutional Analytics or the assistant/map.
5. In React, select **Back to Chat**, then **Campus map**. A verified administrator sees **Map tools**.

Use `localhost` consistently in the browser. `localhost` and `127.0.0.1` are different cookie hosts. Cookies are not scoped by port, so consistent hostnames allow the two interfaces to use the same Django session. Opening React `/admin` now restores a verified existing superuser session even if the saved frontend profile is missing or still says guest. An ordinary guest page stays in guest mode and offers **Switch to administrator** when that session is available. The explicit switch clears guest messages/context. Refreshing guest UI no longer logs out an administrator signed in elsewhere; deliberately choosing **Continue as Guest** still ends the previous authenticated session.

React administrative features continue to use the existing superuser policy. Unfold retains Django's existing staff/model permission checks. No account privileges were changed.

## What was fixed

- **Unstyled Unfold:** its stylesheet existed, but Gunicorn returned 404 for it. WhiteNoise now serves collected public static assets, including with `DEBUG=False`, using compressed manifest storage.
- **Broken logo:** replaced a relative image path with Django's static URL helper. Added a university crest to Unfold's existing login template, preserving its forms, CSRF handling, and theme behavior.
- **Branding:** PAULA title/header/favicon and official green/gold accents. Light and dark themes remain available.
- **Navigation:** retained Institutional Analytics; linked both admin interfaces; normalized React analytics refresh at `/admin` and `/admin/`; navigation to analytics updates the browser URL.
- **Role restoration:** the restored React role now comes from the matching Django session, rather than trusting a saved superuser flag.
- **Map Tools:** guests/students do not see the mapper. Admin tools appear only after `/api/session` confirms an authenticated, matching superuser account. Pending, failed, mismatched, and late responses fail closed. Normal navigation stays available.

### Map editing boundary

The existing Coordinate Mapper previews coordinates in component memory and exports JSON to the clipboard. It **does not save map coordinates to PostgreSQL or automatically publish routing changes**. Its admin panel now explains this. No coordinate-write endpoint was added; server-side persistence and routing synchronization would be separate work. Client visibility checks are not authorization for any future write API.

## Docker/static-file persistence

WhiteNoise 6.12.0 is pinned in `requirements.txt`, so normal future Dockerfile builds install it. The active local `paulibot-web:latest` image was also updated with a small dependency layer over the existing image, using an empty build context. This avoided rebuilding/downloading the existing 16 GB AI stack or sending workspace files/secrets as build context. The earlier image is retained as `paulibot-web:before-admin-static`.

The web container was recreated from the updated image and its image ID was verified against the local tag. PostgreSQL and all data/model/static volumes were preserved. Startup `collectstatic` prepares the public assets before Gunicorn starts. No pending migrations were present before recreation; no schema changes were introduced by this work.

For deployment, set `PAULA_FRONTEND_ORIGIN` to the actual React origin. In debug development its default is `http://localhost:5173`; production defaults to relative links when no origin is configured. Separate frontend hosting needs an explicit correct origin. This work does not deploy the application.

WhiteNoise configuration follows its [Django integration guide](https://whitenoise.readthedocs.io/en/stable/django.html). The incremental image operation uses Docker's supported [empty build context](https://docs.docker.com/build/concepts/context/#empty-context).

## Validation of the initial admin styling changes

| Check | Result |
| --- | --- |
| Focused Django admin/static, chat-session privacy, and performance tests | **33 passed** |
| Existing frontend transport, suggestions, backend URL, and map viewport tests | **14 passed** |
| Browser checks: real Unfold login/assets/themes/mobile plus isolated map/App role and route fixtures | **20 passed** |
| Real admin index rendering | Passed using an existing administrator in a read-only transaction; no HTTP login/account creation |
| Static assets referenced by real admin index/login | **14/14 HTTP 200**, correct non-HTML content types |
| Static delivery with `DEBUG=False` | Passed for CSS, JS, font stylesheet, and logo |
| Web image recreation/readiness | Updated dependency present; all **3 workers ready**; PostgreSQL container preserved |
| Knowledge and conversation fingerprints | Unchanged across StaffMember, FAQ, WebResource, Conversation, ChatHistory, including stored embeddings |
| Frontend production build | Passed; existing large-chunk and Node deprecation warnings remain |
| `git diff --check` | Passed |

Browser role/account cases use isolated synthetic sessions and component/App fixtures; they do not claim a real credential-based student/admin login test. Initial browser attempts exposed the missing login crest, overlapped intentional backend downtime, and revealed a fixture remount issue; these were corrected and the final complete run passed. Physical-device testing and production-host verification remain outstanding.

Evidence: `PAULA_ADMIN_MAP_UI_VERIFICATION.json`, `PAULA_ADMIN_RUNTIME_VERIFICATION.json`, and `PAULA_ADMIN_DATA_INTEGRITY.json`. Screenshots: `PAULA_ADMIN_LOGIN_DESKTOP.png`, `PAULA_ADMIN_LOGIN_MOBILE.png`, `PAULA_ADMIN_MAP_TOOLS.png`.

## Files changed for this task

| File | Change |
| --- | --- |
| `requirements.txt` | Pin WhiteNoise |
| `paulibot/settings.py` | Static middleware/storage, frontend origin, Unfold branding/workspace links |
| `docker-compose.yml` | Pass optional frontend origin |
| `chatbot/admin.py` | Select branded Unfold login template |
| `chatbot/templates/chatbot/admin_login.html` | Extend Unfold login with university crest |
| `frontend/package.json` | Remove obsolete local-Django startup command |
| `frontend/src/App.jsx` | Normalize admin route and restore role from Django |
| `frontend/src/components/AdminDashboard.jsx` | Clear administrative link label; retain analytics |
| `frontend/src/components/Dashboard.jsx` | Pass current identity to map |
| `frontend/src/components/MapModule.jsx` | Verify mapper eligibility and explain export-only behavior |
| `chatbot/test_admin_assets.py` | Admin/static/branding/access regression tests |
| `scripts/verify_admin_map_ui.mjs` | Real admin login and isolated map/App browser checks |
| `scripts/verify_admin_runtime.py` | Read-only runtime asset and database integrity checks |

This list describes this task's changes; the workspace also contains earlier PAULA enhancements. No knowledge ingestion, historical-record cleanup, map-coordinate updates, account creation, or database-volume removal was performed.

## Follow-up: Map Tools missing after admin login

The subsequent session-handoff fix and its additional tests are documented in [PAULA_ADMIN_SESSION_HANDOFF_FIX.md](PAULA_ADMIN_SESSION_HANDOFF_FIX.md). This includes the exact React admin login → Back to Chat → Campus map flow, stale guest profiles, and a real Docker-session verification. The main React login now also retains the server-provided superuser role.
