# Dashboard API Contract: INSIGHT Workspace

Dashboard exposes one primary INSIGHT contract: an authenticated workspace shell with role-scoped module links. Dashboard verifies identity through Authentication over REST, creates a Dashboard-local session, and returns only navigation metadata. Dashboard does not import Authentication code, decode JWTs, read Authentication storage, or implement patient, treatment, logs, backup, user-management, guideline, Bayesian model, or downstream module workflows.

Backend: Python FastAPI. Local state: Dashboard sessions plus optional workspace events. Dashboard does not duplicate Authentication users or profiles. Standalone mock auth is in-memory dev/test behavior, not persisted schema.

## Primary INSIGHT Flow

1. Host app calls `POST /internal/dashboard/session` with valid Authentication credentials.
2. Dashboard calls `GET /api/auth/v2/session` and ignores request-body identity fields.
3. Dashboard creates a local Dashboard session bound to verified `user.id`, `role`, and Authentication session id.
4. UI calls `GET /internal/dashboard/workspace`.
5. Dashboard re-validates local session and calls `GET /api/auth/v2/session` again.
6. Dashboard returns INSIGHT workspace metadata and explicit destination states.

Protected Dashboard endpoints accept Dashboard session id through either:

- query: `?session={dashboardSessionId}`
- header: `X-Dashboard-Session: {dashboardSessionId}`

## Auth Verification Contract

Dashboard verifies identity by calling Authentication:

```http
GET /api/auth/v2/session
```

Dashboard forwards caller credentials when present:

- `Authorization`
- `Cookie`
- `X-Auth-Session`
- `X-Auth-Session-Id`

Expected success response:

```json
{
  "authenticated": true,
  "authorized": true,
  "interfaceVersion": "2.0.0",
  "session": {
    "id": "720705d7-97bc-4d40-a4ac-59bdfcc65501",
    "active": true,
    "expiresAt": "2026-07-30T19:30:00Z"
  },
  "user": {
    "id": "f2af6c59-6856-4dcc-bcf6-8569e009d58b",
    "username": "Mina Rahimi",
    "role": "psychiatrist"
  },
  "gates": {
    "passwordChangeRequired": false,
    "disclaimerRequired": false,
    "disclaimerVersion": "2026-07-06"
  },
  "compatibility": {"legacyUserId": 2, "legacyRole": "user"}
}
```

Accepted provider roles are lowercase:

- `psychiatrist`
- `admin`

Dashboard requires `X-Schema-Version: 2.0.0`, exact v2 fields, UUID
`session.id` and `user.id`, `authenticated: true`, `authorized: true`,
`session.active: true`, a future RFC 3339 UTC `expiresAt` ending in `Z`, and
both gates set to false. Dashboard translates the validated lowercase role to
its existing uppercase local workspace role; uppercase or legacy provider
roles are rejected.

Rejected Authentication states:

- missing auth session id
- unauthenticated response
- inactive session
- expired session or past `expiresAt`
- `authorized: false`
- password-change gate
- disclaimer-required gate
- missing or unsupported interface/schema version
- malformed or non-UUID identity
- unsupported role
- missing user id

Authentication `401` or `403` maps to Dashboard `authentication_session_required`. Authentication transport failures, missing endpoint config, or non-2xx/non-auth failures map to `authentication_session_unavailable`.

Config:

| Variable | Meaning |
| --- | --- |
| `AUTH_SESSION_URL` | Exact Authentication session URL. |
| `AUTH_BASE_URL` | Base URL; Dashboard appends `/api/auth/v2/session`. |
| `DASHBOARD_MOCK_AUTH` | `1` enables standalone mock auth; `0` disables it. |
| `DASHBOARD_DB_PATH` | SQLite path; defaults to `dashboard.sqlite3`. |

When neither `AUTH_SESSION_URL` nor `AUTH_BASE_URL` is set, standalone mock auth is enabled unless `DASHBOARD_MOCK_AUTH=0`.

## Create Dashboard Session

```http
POST /internal/dashboard/session
```

Headers: valid Authentication credentials.

Body:

```json
{
  "device": "Clinic desktop"
}
```

Identity fields in body are ignored. Authentication response is source of truth.

Success: `201`

```json
{
  "sessionId": "dashboard-session-uuid",
  "dashboardUrl": "/dashboard/?session=dashboard-session-uuid",
  "user": {
    "id": "f2af6c59-6856-4dcc-bcf6-8569e009d58b",
    "role": "PSYCHIATRIST",
    "fullName": "Mina Rahimi",
    "title": "Dr.",
    "disclaimerAcceptedAt": null
  }
}
```

Errors:

| Status | Error | Cause |
| --- | --- | --- |
| `401` | `authentication_session_required` | Authentication rejected, missing, expired, blocked, or unsupported. |
| `502` | `authentication_session_unavailable` | Authentication endpoint unavailable, failed, or misconfigured. |

## INSIGHT Workspace Response

```http
GET /internal/dashboard/workspace?session={dashboardSessionId}
```

Alias:

```http
GET /internal/dashboard/summary?session={dashboardSessionId}
```

Before returning workspace metadata, Dashboard:

1. verifies Dashboard session exists and is active
2. calls `GET /api/auth/v2/session`
3. rejects if Authentication `user.id` differs from Dashboard session `userId`
4. refreshes local role and Authentication session id from verified identity

Common response:

```json
{
  "user": {
    "id": "f2af6c59-6856-4dcc-bcf6-8569e009d58b",
    "role": "PSYCHIATRIST",
    "fullName": "Mina Rahimi",
    "title": "Dr.",
    "disclaimerAcceptedAt": null,
    "displayName": "Dr. Mina Rahimi"
  },
  "displayName": "Dr. Mina Rahimi",
  "currentDateTime": "2026-07-06T10:30:00.000000Z",
  "workspace": {
    "kind": "PSYCHIATRIST",
    "title": "Workspace",
    "buttons": [
      {
        "id": "add-new-patient",
        "title": "Add New Patient",
        "state": "available",
        "reason": "Destination available.",
        "href": "/modules/add-new-patient"
      }
    ]
  },
  "requiresDisclaimer": true,
  "disclaimer": {
    "acceptedAt": null,
    "text": "This workspace is a research prototype. It is not a substitute for clinical judgment, emergency care, or licensed guideline review."
  }
}
```

Response rules:

- `workspace.title` is always `Workspace`.
- `workspace.kind` is verified role: `PSYCHIATRIST` or `ADMIN`.
- `displayName` equals `Dr. {fullName}` for `PSYCHIATRIST`.
- `displayName` equals `{fullName}` for `ADMIN`.
- Psychiatrist-only responses include `requiresDisclaimer` and `disclaimer`.
- Every destination is present with state `available`, `unavailable`, or
  `unauthorized` for the currently verified role.
- Only `available` destinations include a gateway-relative `href`.
- Responses contain no patient lists, treatment data, drafts, follow-ups, oversight module data, guideline revisions, Bayesian models, backup payloads, or module implementation payloads.

Role button sets:

| Role | Button ids | Button titles |
| --- | --- | --- |
| `PSYCHIATRIST` | `add-new-patient`, `patient-follow-up`, `list-of-patients`, `setting` | `Add New Patient`, `Patient Follow-up`, `List of Patients`, `Setting` |
| `ADMIN` | `add-new-user`, `logs`, `backup`, `list-of-users` | `Add New User`, `Logs`, `Backup`, `List of Users` |

Errors:

| Status | Error | Cause |
| --- | --- | --- |
| `401` | `dashboard_session_required` | Dashboard session missing, invalid, inactive, or signed out. |
| `401` | `authentication_session_required` | Authentication rejected, missing, expired, blocked, or unsupported. |
| `401` | `authentication_session_mismatch` | Authentication user differs from Dashboard session user. |
| `502` | `authentication_session_unavailable` | Authentication endpoint unavailable, failed, or misconfigured. |

## Module Destinations

Dashboard returns one navigation-only catalog. Current destination support is:

| Destination | Authorized role | State when authorized | Gateway route |
| --- | --- | --- | --- |
| `add-new-patient` | `PSYCHIATRIST` | `available` | `/modules/add-new-patient` |
| `patient-follow-up` | `PSYCHIATRIST` | `available` | `/modules/patient-follow-up` |
| `list-of-patients` | `PSYCHIATRIST` | `unavailable` | none |
| `setting` | `PSYCHIATRIST` | `unavailable` | none |
| `add-new-user` | `ADMIN` | `available` | `/modules/auth/accounts/new` |
| `logs` | `ADMIN` | `unavailable` | none |
| `backup` | `ADMIN` | `unavailable` | none |
| `list-of-users` | `ADMIN` | `available` | `/modules/auth/accounts` |

A destination belonging to the other role has state `unauthorized`. Dashboard
does not invent routes for unavailable destinations and does not copy any
downstream payload.

Discovery endpoint:

```http
GET /internal/dashboard/module-routes/{moduleId}
X-Dashboard-Session: {dashboardSessionId}
```

Dashboard verifies Dashboard session and Authentication before route discovery,
then distinguishes unknown, unauthorized, unavailable, and available destinations.

Available success:

```json
{
  "moduleId": "add-new-patient",
  "title": "Add New Patient",
  "href": "/modules/add-new-patient",
  "state": "available",
  "reason": "Destination available."
}
```

Target modules own data, mutations, permissions beyond entry, UI, and workflow
implementation. Dashboard returns no module payload in destination discovery.
The account destinations route directly to Authentication's owner-hosted UI;
Dashboard does not proxy, cache, or persist account data.

Errors:

| Status | Error | Cause |
| --- | --- | --- |
| `401` | `dashboard_session_required` | Dashboard session missing, invalid, inactive, or signed out. |
| `401` | `authentication_session_required` | Authentication rejected, missing, expired, blocked, or unsupported. |
| `401` | `authentication_session_mismatch` | Authentication user differs from Dashboard session user. |
| `403` | `module_route_unauthorized` | Destination belongs to another role. |
| `404` | `module_route_not_available` | Destination id is unknown. |
| `503` | `module_route_unavailable` | Authorized destination has no supported route. |
| `502` | `authentication_session_unavailable` | Authentication endpoint unavailable, failed, or misconfigured. |

## Disclaimer Acceptance

```http
POST /internal/dashboard/disclaimer/accept
X-Dashboard-Session: {dashboardSessionId}
```

Allowed for verified `PSYCHIATRIST` sessions only. Returns updated INSIGHT workspace response.

Errors:

| Status | Error | Cause |
| --- | --- | --- |
| `401` | `dashboard_session_required` | Dashboard session missing, invalid, inactive, or signed out. |
| `401` | `authentication_session_required` | Authentication rejected, missing, expired, blocked, or unsupported. |
| `401` | `authentication_session_mismatch` | Authentication user differs from Dashboard session user. |
| `403` | `psychiatrist_only` | Verified role is not `PSYCHIATRIST`. |
| `502` | `authentication_session_unavailable` | Authentication endpoint unavailable, failed, or misconfigured. |

## Sign Out

```http
DELETE /internal/dashboard/session
X-Dashboard-Session: {dashboardSessionId}
```

Dashboard verifies Dashboard session and Authentication, then marks local Dashboard session inactive.

Success:

```json
{ "ok": true }
```

Errors:

| Status | Error | Cause |
| --- | --- | --- |
| `401` | `dashboard_session_required` | Dashboard session missing, invalid, inactive, or signed out. |
| `401` | `authentication_session_required` | Authentication rejected, missing, expired, blocked, or unsupported. |
| `401` | `authentication_session_mismatch` | Authentication user differs from Dashboard session user. |
| `502` | `authentication_session_unavailable` | Authentication endpoint unavailable, failed, or misconfigured. |

## Health And Readiness

```http
GET /healthz
```

Success:

```json
{ "ok": true }
```

```http
GET /readyz
```

Returns `200` with `{ "ok": true }` when DB adapter can run trivial query. Returns `503` with `{ "ok": false, "error": "..." }` when DB readiness fails.

