# Admin session handoff and Map Tools

Verified November 7, 2026. The reported path was React admin (`localhost:5173/admin`) followed by the campus map. The screenshot showed a guest warning and Login button, demonstrating that React was displaying guest identity rather than the intended administrator identity.

## Verified defects

- `App.jsx` previously restored a saved guest profile on every route, called `/api/logout`, and selected chat. A stale guest profile could therefore override the React admin route and invalidate a valid Django session on refresh.
- With no saved profile, App did not check the existing backend session. A valid server login could be missed.
- `AuthPage.jsx` always emitted a student identity after login and discarded the backend `is_superuser` value. This was a separate defect affecting the main login form.
- MapModule intentionally required a matching, backend-verified administrator identity. It correctly hid the mapper when supplied with guest/student identity; bypassing this check would not fix the login problem.

The earlier browser fixtures confirmed a correctly formed admin identity but did not submit the React login form starting with stale guest state. New tests cover that missing path. The screenshot alone does not establish which exact browser/session event caused the saved guest state; these code defects and their corrected behavior were reproduced and verified.

## Behavior after the fix

1. Opening `/admin` or `/admin/` checks Django's session. A verified superuser is restored even when local storage says guest or contains no profile. If no administrator is authenticated, the admin login form remains accessible instead of being replaced by guest chat.
2. React admin login → Back to Chat → Campus map keeps the admin identity and reveals Map Tools after its independent backend verification. Refresh preserves the authenticated identity.
3. Both React login forms retain the role returned by Django. Saved frontend flags alone never grant privileges.
4. Ordinary guest pages remain guests, even when a valid admin session is available. They offer **Switch to administrator**. The explicit switch re-verifies the current account, clears guest messages, and creates a fresh authenticated chat context; it does not save the guest thread.
5. Returning focus to a guest/landing page checks for an administrator session created in another tab. This uses focus/visibility events, with no background polling or additional LLM calls.
6. Refreshing an existing guest view no longer sends a destructive logout request. Explicitly selecting Continue as Guest still logs out the previous authenticated session. Guest chat requests continue to omit cookies and use unsaved guest mode.
7. Cancelled/stale initialization responses cannot replace a newer identity. Map Tools still fails closed for unverified/mismatched sessions and is preview/export only.

## Validation

- **21 frontend tests passed**, including seven new identity-restoration cases plus existing transport, suggestions, URL, and viewport tests.
- **11 new browser flow checks passed** using actual React forms/App/map with isolated API fixtures: admin login from saved guest state, Back to Chat, map controls, refresh, main login, explicit guest/admin transitions, guest request credentials, and clearing guest messages.
- **4 real Docker/Vite checks passed**: an existing active superuser restored analytics despite stale guest storage, saw Map Tools after Back to Chat, opened the coordinate mapper, and retained authorization after refresh.
- **20 prior admin/browser regressions passed** again, including static assets/themes/mobile and role/account mismatch cases.
- **8 backend guest/history isolation tests passed**.
- New guest/admin notice checked at **375×812**: no horizontal overflow, at least 44px action target, composer within viewport.
- Frontend production build and `git diff --check` passed. Existing bundle-size/Node deprecation warnings remain.
- Knowledge and historical-chat fingerprints remained unchanged. See `PAULA_ADMIN_HANDOFF_INTEGRITY.json`.

The real-session test created one five-minute session for an existing administrator and removed that exact session afterward. It did not create an account, change a password, update last-login via a login signal, or send real chat messages. Actual password submission is tested with synthetic API fixtures; the live test validates the server session/proxy/UI integration without knowing or recording the user's password. No backend changes, restarts, schema changes, knowledge ingestion, or map-coordinate updates were needed for this follow-up.

## Files

- `frontend/src/App.jsx`: route-aware restoration, explicit admin handoff, safe focus refresh, cancellation.
- `frontend/src/authIdentity.js` and `authIdentity.test.mjs`: shared server identity mapping and restoration policy.
- `frontend/src/components/AuthPage.jsx`: retain superuser role; accessible administrator link.
- `frontend/src/components/AdminSessionNotice.jsx`, `Dashboard.jsx`, `responsive.css`: explicit administrator switch with responsive layout.
- `scripts/verify_admin_handoff.mjs`: form and transition browser regressions.
- `scripts/verify_admin_handoff_live.mjs`: real ephemeral-session verification and cleanup.
- `scripts/verify_admin_map_ui.mjs`: guest route fixture updated to distinguish ordinary guest access from explicit `/admin` access.
- `PAULA_ADMIN_AND_RUNTIME_GUIDE.md`: updated session workflow.

Evidence: `PAULA_ADMIN_HANDOFF_BROWSER.json`, `PAULA_ADMIN_HANDOFF_LIVE.json`, `PAULA_ADMIN_HANDOFF_INTEGRITY.json`; synthetic UI screenshot `PAULA_ADMIN_HANDOFF_MAP.png`.

## Using it

Open `http://localhost:5173/admin` and refresh. If asked, sign in with the existing superuser. Select **Back to Chat**, then **Campus map**. Map Tools should appear after session verification. If you are intentionally viewing guest chat with an administrator session available, use **Switch to administrator** first. Use the same `localhost` hostname for both interfaces; cookies from `127.0.0.1` do not authenticate `localhost`.
