# PAULA mobile UI and UX improvements

Implemented in the existing React/Vite frontend. No dependencies were installed.

## Findings and changes

### Campus navigation

The previous mobile location picker covered much of the map. The floating close
button overlapped navigation controls, touch targets were small, and landscape
phones could inherit the desktop map/chat split.

The map now has a separate toolbar and selection area. Portrait phones use a
map above the picker; short landscape screens use a compact side panel.
Modules occupy the workspace through the tablet breakpoint rather than squeezing
chat beside them. Desktop retains the split workspace.

- Added bounded 1–4× zoom, pinch zoom, drag-to-pan, zoom buttons and a fit control.
- Image, route overlay and markers resize together; original percentage-based
  campus coordinates and backend routing are unchanged.
- Location search/list controls provide readable alternatives to densely packed
  map dots. Primary controls and list rows have at least 44 px touch targets.
- Destination selection, starting-point selection and destination changes are
  distinct. Route loading, no-match search and recoverable route errors appear
  in the interface rather than browser alerts.
- Ignore stale route responses when selections change or the module closes.
- Retained the coordinate preview tool under “Map tools”; normal navigation is
  the initial mode. Preview edits remain local and do not write campus data.
- Removed the uncalibrated walking-minute calculation from route pixels.
  The route summary states that the route is ready instead of suggesting a
  measured walking time.

### Chat, navigation and forms

- Added a direct campus-map button beside the existing tour action.
- Put module close/back controls in the layout, outside map and tour overlays.
- Kept header controls reachable in narrow split panels and on 320 px phones.
- Added dynamic/visual viewport height handling, safe-area padding and
  `interactive-widget=resizes-content` without disabling browser zoom.
- Prevented long answers, citations and FAQ buttons from expanding the page.
- Improved composer, send, source, FAQ and history-action touch targets.
- Kept the history drawer inside the viewport, made closed compact drawers inert,
  and added focus containment/Escape handling and focus restoration.
- Made the profile trigger a button. Profile dialogs have an accessible title,
  close action, bounded scrolling, keyboard focus handling and smaller mobile
  spacing. Background updates do not recreate the close callback and reset focus.
- Improved login spacing, password autofill hints, 16 px mobile fields, narrow
  registration name fields and footer spacing.
- Respected reduced-motion preferences for the main UI animations.

### Tour and administration

- Moved tour controls outside the panorama area and added five direct location
  buttons, so users can enter a location without accurately tapping a small pin.
- Kept aerial/panorama return controls reachable on phones.
- Ordinary background taps no longer open the developer coordinate alert.
  Deliberate Alt-click calibration remains available in development.
- Wrapped admin actions and filters, adapted metric cards, and kept wide tables
  and heatmaps scrollable inside their cards instead of expanding the page.
- Increased heatmap label readability and fixed the admin reports card's
  dark-mode background fallback.
- Replaced hardcoded `localhost:8000` admin/avatar links. Development now uses
  the current hostname with Docker's backend port 8080. Separately hosted builds
  may set `VITE_BACKEND_ORIGIN`; same-origin production remains the default.

## Validation

| Verification | Result |
|---|---|
| Production frontend build | Passed |
| Frontend unit/transport/suggestion checks | 14 passed |
| Complete native Chrome mobile workflow suite | 48 checks passed |
| Restricted-screen fixture follow-up | 11 checks passed |
| Unexpected browser calibration dialogs | 0 |
| Existing campus graph source | Unchanged |
| Audited PostgreSQL knowledge, vectors and historical chats | Unchanged |

Viewport coverage: 320×568, 375×812, 390×844, 430×932, 768×1024,
1024×768, 1280×900, plus 812×375 landscape and a 375×420 reduced-height viewport.

The full browser suite covers entry/chat containment, theme switching, composer
visibility, map/picker separation, touch pinch and pan, fit/reset, actual backend
route rendering, recovery from a simulated route-network failure, destination
changes, five available tour destinations, entry into one panorama and return,
student history, profile scrolling/Escape, registration, and admin table scrolling.

**Evidence boundaries:** guest navigation and route requests use the actual
running backend. Student/profile/admin layouts use isolated synthetic component
fixtures and fixture admin GET responses in a dedicated browser tab. No accounts
are created, no student/admin mutations are submitted, and no real account is
impersonated on the backend. These checks do not replace authenticated device
testing or certify every panorama asset and screen-reader interaction.

The harness was corrected during validation for boolean DOM readiness checks,
Vite module interop, fixture viewport setup and realistic multi-frame touch
gestures. Instant synthetic flicks had suppressed the next compatibility click;
the final suite uses complete, separated gestures. Real fixes include proper
touch capture cleanup and explicit non-delayed button touch behavior.

The final build still reports the existing large main-chunk warning
(approximately 1.32 MB before gzip, 374 KB gzipped), and Node reports a tooling
deprecation. The build succeeds; bundle splitting/dependency upgrades were not
introduced as part of the mobile layout work.

## Modified files for this task

- `frontend/index.html`: mobile viewport metadata.
- `frontend/src/App.jsx`: visual viewport sizing.
- `frontend/src/main.jsx`: load the responsive stylesheet.
- `frontend/src/responsive.css` (new): workspace, module, form, tour and admin
  responsive styles and touch sizing.
- `frontend/src/components/Dashboard.jsx`: module toolbar, map shortcut,
  compact history drawer, accessible actions and source controls.
- `frontend/src/components/MapModule.jsx`: viewport controls and route UX.
- `frontend/src/hooks/useMapViewport.js` (new): scoped pan/pinch/zoom behavior.
- `frontend/src/utils/mapViewport.js` and `.test.mjs` (new): geometry contracts.
- `frontend/src/components/VirtualTour.jsx`: mobile controls/location selection.
- `frontend/src/components/AuthPage.jsx`: mobile form hints.
- `frontend/src/components/RegisterPage.jsx`: responsive name row hook.
- `frontend/src/components/EditProfileModal.jsx`: sizing, scrolling, focus and
  backend media URLs.
- `frontend/src/components/AdminDashboard.jsx`: action wrapping, table/heatmap
  usability and backend admin URL.
- `frontend/src/components/UserAvatar.jsx`: backend media URL handling.
- `frontend/src/components/MaterialIcon.jsx`: map-tools and fit icons.
- `frontend/src/utils/backendUrl.js` and `.test.mjs` (new): portable backend URLs.

Existing unrelated workspace edits, backend RAG/authentication logic, routes,
institutional records and database volumes were preserved.

## Review artifacts and reproduction

- `PAULA_MOBILE_BEFORE.json`, `PAULA_MOBILE_AFTER.json`: baseline/layout measurements.
- `PAULA_MOBILE_VERIFICATION.json`: complete workflow checks and dimensions.
- `PAULA_MOBILE_FIXTURE_VERIFICATION.json`: fixture-only checks when run separately.
- `PAULA_MOBILE_DATA_INTEGRITY.json`: read-only PostgreSQL fingerprint proof.
- `PAULA_MOBILE_ENTRY_FINAL.png`, `PAULA_MOBILE_MAP_FINAL.png`,
  `PAULA_MOBILE_ROUTE_FINAL.png`, `PAULA_MOBILE_TOUR_FINAL.png`,
  `PAULA_MOBILE_REGISTER_FINAL.png`, `PAULA_MOBILE_ADMIN_FINAL.png`: visual review.
  The admin image contains synthetic fixture data.

```powershell
cd frontend
npm run build
node --test src/utils/mapViewport.test.mjs src/utils/backendUrl.test.mjs src/suggestions.test.mjs src/api/chatApi.test.mjs
```

Browser scripts are `scripts/mobile_browser.mjs`, `scripts/audit_mobile_ui.mjs`
and `scripts/verify_mobile_ui.mjs`. They require a dedicated Chrome debugging
profile on localhost:9340. The temporary profile used here is closed and removed
after validation. Continue using `npm run dev` with Docker on port 8080; no Django
restart is required for this frontend work.

## Remaining practical checks

Physical Android/iOS Safari testing remains necessary for real soft keyboards,
notches, browser bars, touch momentum and device GPU behavior. The reduced-height
checks simulate layout pressure, not an operating-system keyboard. Django's
separate authenticated Unfold administration interface was not redesigned.
