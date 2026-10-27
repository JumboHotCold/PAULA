# PAULA chat-session privacy and personnel correction

Completed 28 October 2026 using the Docker PostgreSQL database. Historical chat
records were preserved, as explicitly requested.

## Personnel correction

- Removed the single active `StaffMember` entry for Leo Nicholas Zotomayor.
- Added **Khen Malaque — JSIT Moderator**, based on the project owner's correction.
- Did not infer an instructor title or office address for Khen. The new office
  field is empty; response formatting omits unknown office information.
- Updated the seed dataset so a future seed also contains Khen's moderator role.
- Regenerated the personnel embedding from the existing cached MiniLM model;
  there are zero missing personnel embeddings.
- Added a reusable exact staff-position lookup, so a locally maintained role can
  answer directly even if the website directory does not yet contain that role.
  This does not override an existing exact official-website personnel answer.
- Archived source snapshots and historical chat responses were not rewritten.

## Root causes

1. React logout sent `DELETE /api/login`. That endpoint accepts login POST;
   the Django authentication session was not cleared by the logout action.
2. Guest entry changed only local React identity. Browser requests still included
   a previous student's authentication cookie.
3. Backend persistence depended on `request.user.is_authenticated` alone. It
   could therefore save a guest-labelled UI request under an old student login.
4. Missing conversation IDs created new conversation rows. The client had no
   stable per-chat server grouping key to recover the same thread after losing
   that ID or refreshing the page.
5. The legacy chat view preloaded every message instead of opening one selected
   conversation. Pending frontend requests also needed invalidation on identity
   and thread changes.

## Current behavior

### Authenticated conversations

`Conversation.client_session_id` is a nullable UUID with a database uniqueness
constraint on `(user, client_session_id)`. Existing conversation/message records
were not merged, reassigned, or deleted. Existing rows retain a null session UUID.

The frontend keeps an authenticated chat UUID and selected conversation ID in
per-tab session storage keyed by account. Each New Chat rotates the UUID. The
backend reuses the owned thread for that UUID if a prompt omits the conversation
ID. Concurrent first messages cannot create duplicate rows for the same UUID and
account. An explicitly supplied foreign/missing thread returns 404; a deleted
session returns 409 rather than being silently recreated.

Multiple `ChatHistory` message rows remain inside that single conversation. These
rows are needed for message display and contextual answers; they are not separate
sidebar conversations. Page refresh resumes the selected owned thread, including
older threads that lack a UUID. A prior owned thread can also be selected/resumed.

### Guest privacy and authentication isolation

- Chat requests save only when mode is explicitly `authenticated` **and** Django
  confirms a logged-in user. Missing mode defaults to guest/no saving. An old
  cookie alone cannot opt a request into persistence.
- Explicit guest mode skips all authenticated conversation/history reads and
  writes, even if an authenticated cookie and conversation ID are supplied.
- Guest browser chat requests use `credentials: 'omit'` as an additional layer.
- Guest entry and authenticated logout use the real `POST /api/logout` endpoint.
  Guest entry waits for logout to complete before displaying guest mode.
- Session restoration checks `GET /api/session`, rather than trusting a cached
  localStorage identity. A request can carry its expected account ID; if a
  different account has signed in in another tab, Django rejects the stale tab's
  authenticated save instead of assigning it to the new account.
- Identity/New Chat/thread changes invalidate pending responses and delayed
  display callbacks. Old responses cannot populate a different chat or identity.
- Guest transcripts/context remain in memory. No guest conversation or message
  is inserted into the database. Existing signed intent-token owner/tab binding
  remains in effect.
- The legacy Django chat client also sends explicit mode and a per-chat UUID.

The new authenticated API contract requires `mode: "authenticated"`; integrations
that omit mode now deliberately receive unsaved guest behavior. This is a privacy
default, not an inference of identity from localStorage. New frontend clients also
send `chat_session_id` and `account_id`.

## Historical data and investigation limits

The before/after counts remain **139 conversations and 176 messages**. The audit
found 85 active single-message threads, but a single-message thread is not proof
of guest misattribution. Old rows do not record the browser's guest/authenticated
mode, so no individual historical conversation was reliably identified as wrongly
attributed. None was automatically deleted, reassigned, or merged. A separate
investigation needs identifiable test times/conversations or equivalent evidence.

The additive migration is `0012_conversation_client_session_id`; it was reviewed
with `migrate --plan`, checked against model state, and applied through Docker.
The PostgreSQL volume was preserved. No replacement accounts were created.

## Verification

- **123 backend regression tests passed**, including guest mode with a forced
  authenticated session, missing-mode fail-closed behavior, stable session reuse,
  invalid/foreign/deleted thread handling and stale browser identity rejection.
- A Node transport test passed: guest requests omit cookies, authenticated
  requests retain their session key, and logout is POST to the correct endpoint.
- The frontend production build passed with the existing bundle-size/Node warnings.
- The legacy template JavaScript passed a syntax check.
- **18 actual Django/PostgreSQL session integration checks passed**, using two
  existing accounts and real session/CSRF middleware inside a fully rolled-back
  transaction. The checks cover grouped messages, new/resumed conversations,
  refresh recovery metadata, authenticated-cookie guest requests, logout,
  guest-to-authenticated switching, cross-account read/write protection and
  session identity restoration and public CSRF-cookie initialization. The bot answer was mocked to avoid external LLM
  calls; persistence and authentication were real.
- Every temporary message, conversation, session and last-login update from that
  integration run rolled back. The output contains no account identities,
  passwords, session keys or historic chat text.

Results: `PAULA_CHAT_PRIVACY_VERIFICATION.json`.

```powershell
docker exec paulibot_web python -B manage.py test chatbot.test_grounding chatbot.test_intents chatbot.test_web_crawler chatbot.test_enrollment chatbot.test_conversation_context chatbot.test_chat_sessions --verbosity 1
docker exec paulibot_web python -B manage.py shell -c "import runpy; runpy.run_path('scripts/verify_chat_privacy.py', run_name='__main__')"
cd frontend
node --test src/api/chatApi.test.mjs
npm.cmd run build
```

## Modified files

| File | Change |
| --- | --- |
| `chatbot/models.py` | Stable conversation session UUID and per-user uniqueness |
| `chatbot/migrations/0012_conversation_client_session_id.py` | Additive PostgreSQL migration |
| `chatbot/serializers.py` | Return chat-session metadata with conversation lists |
| `chatbot/views.py` | Explicit persistence mode, ownership/session grouping, identity checks and isolated legacy chat rendering |
| `chatbot/urls.py` | Logout and session-status endpoints |
| `chatbot/data.py` | Owner-confirmed Khen Malaque moderator seed |
| `chatbot/rag.py` | Generic exact local-position lookup and omission of unknown office text |
| `frontend/src/App.jsx` | Server-verified restore, per-chat grouping, mode switches, refresh/resume and stale-response guards |
| `frontend/src/api/chatApi.js` | Explicit mode/account/session transport, guest cookie omission and real logout |
| `frontend/src/components/AuthPage.jsx`, `frontend/src/components/LoginPage.jsx` | Use the server's canonical account identifier after login |
| `chatbot/templates/chatbot/chat.html` | Explicit mode and per-chat session UUID |
| `chatbot/test_chat_sessions.py` | Persistence/privacy regressions |
| `chatbot/test_enrollment.py`, `chatbot/test_conversation_context.py` | Explicit authenticated-mode contract in existing tests |
| `frontend/src/api/chatApi.test.mjs` | Cookie/session/logout transport verification |
| `scripts/verify_chat_privacy.py` | Real session integration with complete rollback |
| `PAULA_CHAT_PRIVACY_VERIFICATION.json`, this report | Verification and change documentation |

Remaining limits: full interactive browser click automation was not performed;
frontend transport/build and real Django sessions were tested separately. Browser
tabs share Django login cookies, so logging out or entering guest mode can expire
another authenticated tab; that tab must log in again and cannot silently save as
another user. Already deployed/cached clients must reload to receive the new UI.
