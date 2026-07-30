# Severity Module

Psychiatrist-facing PANSS Severity assessment for INSIGHT. The module remains an
independently runnable Node.js and Express service with a dependency-light
browser UI.

## Current Behavior

- Renders all 30 PANSS items with native keyboard-operable 1-7 buttons.
- Accepts canonical Patient and Encounter UUID context only from the host.
- Uses the gateway-relative PANSS v2 API and cookie credentials.
- Revalidates Authentication for every assessment request and sends signed
  double-submit CSRF tokens on writes.
- Uses idempotent creates and ETag-protected updates.
- Shows local completion progress but renders scores and evaluation state only
  from the server response.
- Keeps passed/skipped, completed, and error states textually distinct.
- Keeps errors visible until a later server action succeeds.
- Does not use patient aliases, URL/query state, `localStorage`, or
  `sessionStorage`.
- Supports reduced motion, visible focus, semantic status announcements, and
  44px interaction targets.

## Host Integration

`public/severity-ui.js` exports `mount` and `unmount` and also publishes the
frozen `window.InsightSeverity` lifecycle API.

```js
const handle = await window.InsightSeverity.mount({
  root: document.getElementById("severity-workspace"),
  context: {
    patientId: "<canonical Patient UUID>",
    encounterId: "<canonical Encounter UUID>",
    assessmentId: "<optional existing Assessment UUID>"
  },
  onAssessmentChange: ({ assessmentId, status }) => {
    // The host may retain the non-PHI assessment reference in its own state.
  }
});

handle?.unmount();
```

The host owns navigation, browser history, session state, and patient lookup.
The module renders only within the supplied root and aborts active requests,
removes listeners, and clears its DOM on unmount. `apiBasePath` may override the
default `/api/severity/v2`, but it must remain a root-relative gateway path.

When opened directly, `public/index.html` reads optional in-memory context from
`window.__INSIGHT_SEVERITY_CONTEXT__`. Without valid UUID context it displays a
persistent error and disables clinical actions; it does not offer alias lookup.

## API

PANSS v2 is canonical. Machine-readable artifacts are in `contracts/`, with
discovery at `GET /api/severity/v2/contract`.

- `GET /api/severity/v2/csrf`
- `POST /api/severity/v2/assessments`
- `GET /api/severity/v2/assessments/{assessmentId}`
- `PUT /api/severity/v2/assessments/{assessmentId}`

All assessment operations require a current authorized psychiatrist session.
Writes require `X-Schema-Version: 2.0.0`, `X-CSRF-Token`, and either an
`Idempotency-Key` create header or an `If-Match` update header. Completed totals
are recomputed by the server. `skipped` contains no ratings or scores and never
means absent, normal, or favorable.

Legacy patient-code routes return `410 SEVERITY_LEGACY_IDENTITY_UNMAPPED` and
cannot persist unverifiable identity.

## Runtime

Requirements:

- Node.js 22 or compatible runtime with `node:sqlite`.
- `SEVERITY_DB_PATH` for module-owned SQLite persistence.
- `SEVERITY_AUTH_BASE_URL` for Authentication REST verification.
- `SEVERITY_CSRF_SECRET` with at least 32 characters in production.
- Optional comma-separated exact origins in `SEVERITY_ALLOWED_ORIGINS`.

Run:

```sh
npm install
npm start
```

`GET /healthz` is dependency-free liveness. `GET /readyz` checks configuration,
SQLite integrity and migration state, and Authentication reachability with safe
errors.

## Verification

```sh
npm test
```

The suite covers repository migration/import behavior, configuration, server
evaluation, auth, CSRF, CORS, concurrency, idempotency, legacy failure, UI host
lifecycle/privacy scans, accessibility contracts, and UI-client completion,
pass, and error behavior over real HTTP.

## Boundaries

- Severity owns PANSS assessment data and scoring behavior.
- Browser calculations do not establish authoritative clinical scores.
- Patient and Encounter identity remain owned by Add New Patient and arrive only
  as host-provided canonical UUID context.
- The module does not mutate host navigation or persist clinical context in the
  browser.
