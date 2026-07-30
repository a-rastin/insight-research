# INSIGHT Authentication v1 Contract

Status: deprecated compatibility contract; successor is Authentication v2
Last updated: 2026-07-06

This document is the public contract for the Authentication module. Downstream
INSIGHT modules must depend on this HTTP contract, not on Python internals,
SQLite tables, or decoded JWT claims.

New consumers must use `GET /api/auth/v2/session` and the versioned
[`Authentication v2 Contract.md`](Authentication%20v2%20Contract.md). The v1
session route remains a time-bounded compatibility adapter.

## Scope

Authentication v1 owns:

- the standalone sign-in page at `/`;
- all implemented API routes under `/api/auth/*`;
- username/password credential verification;
- temporary password rotation before dashboard access;
- default admin seeding;
- admin-only account creation;
- admin-only account listing and lifecycle management;
- role validation;
- session cookie issuance and expiration;
- disclaimer gating for psychiatrist accounts;
- SQLite schema migrations for auth-owned persistence;
- session verification for downstream modules.

Authentication v1 does not own dashboard rendering. Dashboard routes belong to
other modules at `/dashboard/admin` and `/dashboard/user`.

## Roles

The canonical wire-level roles returned by v1 are:

| Wire role | Product role | Meaning |
| --- | --- | --- |
| `admin` | Administrator | Can access the admin dashboard and create accounts. |
| `psychiatrist` | Psychiatrist | Can access the psychiatrist dashboard after accepting the disclaimer. |

For compatibility with existing clients and stored data, v1 also accepts
`user` anywhere a request body role is accepted. Authentication normalizes that
alias to `psychiatrist`, migrates stored `user` rows to `psychiatrist`, and
returns `psychiatrist` in new session responses.

The selected login role must match the stored account role. A stored `admin`
cannot sign in as `psychiatrist`, and a stored `psychiatrist` cannot sign in
as `admin`.

## Current API Routes

All current API routes are mounted under `/api/auth`.

| Method | Route | Status | Auth required | Purpose |
| --- | --- | --- | --- | --- |
| `GET` | `/api/auth/csrf` | Current | No | Safe bootstrap route that sets the readable CSRF cookie and returns the token for write requests. |
| `POST` | `/api/auth/login` | Current | No | Verify credentials, create a server-side session, issue the session cookie, and return the next auth step. |
| `POST` | `/api/auth/password/change` | Current | Temporary or accepted session | Replace the current password and return the next auth step. |
| `GET` | `/api/auth/session` | Current | Valid accepted session | Verify the browser cookie and server-side session for downstream modules. |
| `GET` | `/api/auth/disclaimer` | Current | Pending or accepted psychiatrist cookie | Return current disclaimer content, active version, and caller acceptance state. |
| `POST` | `/api/auth/disclaimer/accept` | Current | Pending or accepted psychiatrist cookie | Persist disclaimer acceptance and return the psychiatrist dashboard redirect. |
| `POST` | `/api/auth/logout` | Current | No | Revoke the current server-side session and expire the configured session cookie. |
| `POST` | `/api/auth/register` | Current | Accepted `admin` session | Create an `admin` or `psychiatrist` account. |
| `GET` | `/api/auth/admin/users` | Current | Accepted `admin` session | List accounts without password hashes. |
| `POST` | `/api/auth/admin/users/{user_id}/disable` | Current | Accepted `admin` session | Disable an account and revoke its sessions. |
| `POST` | `/api/auth/admin/users/{user_id}/enable` | Current | Accepted `admin` session | Re-enable a disabled account. |
| `POST` | `/api/auth/admin/users/{user_id}/reset-password` | Current | Accepted `admin` session | Set or generate a temporary password and revoke sessions. |
| `PATCH` | `/api/auth/admin/users/{user_id}/role` | Current | Accepted `admin` session | Update an account role when policy allows it. |
| `GET` | `/api/auth/docs` | Current diagnostics | No explicit auth | FastAPI interactive docs for local/internal development. Not a product API. |

Unknown `/api/auth/*` routes return FastAPI `404` and are not part of v1.

All `POST` and `PATCH` routes require CSRF verification. Browser clients must
first call `GET /api/auth/csrf`, then echo the returned token in the
`X-CSRF-Token` header on every write. Missing, mismatched, expired, or unsigned
CSRF tokens return `403`.

## Planned v1 Routes

There are no additional planned runtime routes for Authentication v1. The
following account-lifecycle capabilities are intentionally outside the v1 HTTP
contract and must not be assumed by downstream modules:

- anonymous or self-service registration;
- anonymous or unauthenticated password reset;
- account deletion;
- audit log retrieval;
- refresh tokens;
- session introspection beyond `/api/auth/session`.

If any of these capabilities are added after v1, they must be documented in a
new versioned contract before downstream modules consume them.

## `POST /api/auth/login`

Request body:

```json
{
  "username": "Admin",
  "password": "Admin",
  "role": "admin"
}
```

Validation:

- `username`: non-empty string, maximum 64 characters;
- `password`: non-empty string, maximum 256 characters;
- `role`: exactly `admin`, `psychiatrist`, or legacy alias `user`.

Success response for an admin:

```json
{
  "ok": true,
  "next": "/dashboard/admin",
  "disclaimer_required": false,
  "password_change_required": false
}
```

Success response for an accepted psychiatrist account:

```json
{
  "ok": true,
  "next": "/dashboard/user",
  "disclaimer_required": false,
  "password_change_required": false
}
```

Success response for a psychiatrist account that has not accepted the
disclaimer:

```json
{
  "ok": true,
  "next": null,
  "disclaimer_required": true,
  "password_change_required": false
}
```

Success response for an account that must rotate a temporary password:

```json
{
  "ok": true,
  "next": null,
  "disclaimer_required": false,
  "password_change_required": true
}
```

Login always creates a server-side session row and sets the configured
HTTP-only session cookie after successful credential and role verification.
For a pending psychiatrist, that cookie
exists only to complete the disclaimer flow; `/api/auth/session` still returns
`401` until the disclaimer is accepted.
For an account that must rotate a temporary password, the cookie exists only
to complete `POST /api/auth/password/change`; `/api/auth/session` returns
`401` until the password is changed.

Errors:

- `401` when the username or password is wrong;
- `401` with the same body when repeated failures temporarily block the
  username/client tuple;
- `403` when credentials are valid but the selected role does not match the
  stored role;
- `422` when the request shape fails validation.

Credential and role failures intentionally use the same generic user-facing
message: `Wrong username or password`. Successful login clears the local
failed-attempt counter for that username/client tuple.

## `POST /api/auth/password/change`

This route supports forced password rotation after an admin resets an account
password. It requires a valid temporary-password or accepted-session cookie and
CSRF verification.

Request body:

```json
{
  "current_password": "temporary-or-current-password",
  "new_password": "new-password"
}
```

Validation:

- `current_password`: non-empty string, maximum 256 characters;
- `new_password`: at least 8 characters, maximum 256 characters;
- `new_password` must differ from `current_password`.

On success, Authentication clears the account's `must_change_password` flag,
revokes existing sessions for that account, issues a fresh session cookie, and
returns the next auth state using the same response shape as login. A
psychiatrist who has not accepted the disclaimer receives
`disclaimer_required: true`; an accepted user receives a dashboard `next`.

Errors:

- `401` when the cookie is missing/invalid or the current password is wrong;
- `403` for invalid CSRF;
- `422` when validation fails.

## `GET /api/auth/session`

This is the only v1 session verification route for downstream modules.

Request:

- send the browser cookie exactly as received from Authentication;
- for same-origin browser calls, use normal browser credential behavior;
- for server-side module checks, forward the incoming `Cookie` header.

Success response:

```json
{
  "ok": true,
  "user_id": 1,
  "username": "Admin",
  "role": "admin",
  "display_role": "Administrator",
  "disclaimer_status": "not_required",
  "expires_at": 1783388800,
  "message": "admin",
  "clinical_role": null,
  "legacy_role": null
}
```

or:

```json
{
  "ok": true,
  "user_id": 2,
  "username": "doc1",
  "role": "psychiatrist",
  "display_role": "Psychiatrist",
  "disclaimer_status": "accepted",
  "expires_at": 1783388800,
  "message": "psychiatrist",
  "clinical_role": "psychiatrist",
  "legacy_role": "user"
}
```

The `role` value is the active canonical v1 wire role. `display_role` is safe
for dashboards to show in UI. `disclaimer_status` is `not_required` for admins
and `accepted` for active psychiatrist sessions. `expires_at` is a Unix
timestamp in seconds for the current session cookie expiry. `message` mirrors
`role` for compatibility with older callers. `legacy_role: "user"` is included
only on psychiatrist sessions to make the compatibility mapping explicit.

Failure response:

- `401` for no cookie, invalid JWT, expired JWT, missing or revoked server-side
  session, deleted account, disabled account, role mismatch against current
  database state, pending password change, or pending disclaimer.

Downstream modules must treat only `200` with `ok: true` and a recognized role
as authenticated. They must not decode the JWT, read Authentication's SQLite
database, call `/api/auth/disclaimer` as an authorization substitute, or accept
pending-disclaimer users.

## Session Payload Shape

The external session response is deliberately small:

```json
{
  "ok": true,
  "user_id": 1,
  "username": "Admin",
  "role": "admin | psychiatrist",
  "display_role": "Administrator | Psychiatrist",
  "disclaimer_status": "not_required | accepted",
  "expires_at": 1783388800,
  "message": "admin | psychiatrist",
  "clinical_role": "psychiatrist | null",
  "legacy_role": "user | null"
}
```

The external response does not expose the JWT, signing secret, `sub`, `iat`,
`exp`, or `jti` claims. Downstream modules should use `user_id` and
`expires_at` instead of depending on internal token claim names.

The signed JWT is an internal cookie payload. Its current claims are:

```json
{
  "sub": "1",
  "role": "admin",
  "iat": 1783360000,
  "exp": 1783388800,
  "jti": "opaque-random-id"
}
```

JWT claims are not a downstream authorization contract. Authentication also
requires a live row in its server-side `sessions` table. Authentication may
change internal token details in a later version as long as
`GET /api/auth/session` preserves its versioned contract.

Inside the Authentication module, a resolved session currently has:

```json
{
  "sub": "1",
  "role": "admin",
  "username": "Admin",
  "must_change_password": false,
  "disclaimer_signed": true,
  "expires_at": 1783388800
}
```

This internal shape is for Authentication routes only. Downstream modules must
not depend on it.

## Admin Account Management

All routes in this section require an accepted `admin` session. Anonymous
callers, psychiatrists, pending-disclaimer users, stale sessions, and disabled
admins receive `401`.

### `GET /api/auth/admin/users`

Success response:

```json
{
  "ok": true,
  "users": [
    {
      "id": 1,
      "username": "Admin",
      "role": "admin",
      "disabled": false,
      "must_change_password": false,
      "disclaimer_signed": true,
      "created_at": "2026-07-06 16:00:00"
    }
  ]
}
```

The response never includes `password`, `password_hash`, JWTs, or session
tokens.

### `POST /api/auth/admin/users/{user_id}/disable`

Disables the target account and revokes all of its server-side sessions.
Disabled accounts cannot log in, and any still-present cookies fail
`GET /api/auth/session`.

Errors:

- `403` when an admin attempts to disable their own account;
- `404` when the target account does not exist;
- `409` when disabling the target would remove the final active admin.

### `POST /api/auth/admin/users/{user_id}/enable`

Re-enables the target account. This does not issue a session; the user must log
in again.

Errors:

- `404` when the target account does not exist.

### `POST /api/auth/admin/users/{user_id}/reset-password`

Request body:

```json
{
  "temporary_password": "optional-admin-chosen-temp-password"
}
```

If `temporary_password` is omitted, Authentication generates one. The stored
password hash is replaced, `must_change_password` is set to `true`, all
target-account sessions are revoked, and the temporary password is returned
once:

```json
{
  "ok": true,
  "user_id": 2,
  "temporary_password": "returned-temporary-password"
}
```

The target user can authenticate with the temporary password, but login returns
`password_change_required: true` and `/api/auth/session` continues to return
`401` until `POST /api/auth/password/change` succeeds.

Errors:

- `404` when the target account does not exist;
- `422` when the supplied temporary password is empty or longer than 256
  characters.

### `PATCH /api/auth/admin/users/{user_id}/role`

Request body:

```json
{
  "role": "admin"
}
```

Accepted roles are `admin`, `psychiatrist`, and legacy alias `user`, which is
normalized to `psychiatrist`. Role updates revoke all target-account sessions.
Changing an account to `psychiatrist` resets disclaimer acceptance so the
psychiatrist disclaimer must be accepted before the account has a downstream
session.

Errors:

- `403` when an admin attempts to change their own role;
- `404` when the target account does not exist;
- `409` when demoting the target would remove the final active admin;
- `422` when the requested role is invalid.

## Disclaimer Behavior

The disclaimer gate applies only to the `psychiatrist` role.

Rules:

- admins are seeded and treated as already accepted;
- the current disclaimer content and version are owned by Authentication;
- a new `psychiatrist` account starts with no acceptance record for the active
  disclaimer version;
- successful pending-psychiatrist login sets the cookie and returns
  `disclaimer_required: true`;
- if password rotation is also required, `password_change_required` is returned
  first and the disclaimer flow follows after the password is changed;
- pending users may call only `GET /api/auth/disclaimer` and
  `POST /api/auth/disclaimer/accept`;
- pending users do not have an active downstream session;
- `POST /api/auth/disclaimer/accept` stores `user_id`, timestamp, and the
  active disclaimer version, then returns `next: "/dashboard/user"`;
- changing the active disclaimer version makes previously accepted
  psychiatrists pending again until they accept the new version;
- after acceptance, `/api/auth/session` returns `200` with
  `role: "psychiatrist"`.

`GET /api/auth/disclaimer` responses:

```json
{
  "ok": true,
  "version": "2026-07-06",
  "title": "Research Prototype Disclaimer",
  "content_html": "<p>...</p>",
  "acknowledgement": "I have read and understand the disclaimer...",
  "accepted": false,
  "accepted_version": null,
  "accepted_at": null,
  "message": "Disclaimer pending acceptance."
}
```

or:

```json
{
  "ok": true,
  "version": "2026-07-06",
  "title": "Research Prototype Disclaimer",
  "content_html": "<p>...</p>",
  "acknowledgement": "I have read and understand the disclaimer...",
  "accepted": true,
  "accepted_version": "2026-07-06",
  "accepted_at": "2026-07-06 19:22:00",
  "message": "Disclaimer already accepted."
}
```

Admins, anonymous callers, invalid cookies, and stale cookies receive `401`.

## Dashboard Redirect Behavior

Authentication v1 returns only these product dashboard redirects:

| Condition | Response behavior |
| --- | --- |
| Accepted `admin` login | `next: "/dashboard/admin"` |
| Accepted `psychiatrist` login | `next: "/dashboard/user"` |
| Temporary-password login | `next: null`, `password_change_required: true` |
| Pending `psychiatrist` login | `next: null`, `disclaimer_required: true` |
| Disclaimer accepted | `next: "/dashboard/user"` |

The standalone sign-in page at `/` calls `/api/auth/session` on load. If the
session is valid, it redirects `admin` to `/dashboard/admin` and
`psychiatrist` to `/dashboard/user`. If the session is missing, expired,
invalid, or pending disclaimer, the user remains on the sign-in/disclaimer
flow.

Downstream protected pages should call `/api/auth/session`; on `401`, they
should redirect the browser back to `/`.

## Cookie Policy

The session cookie is configured by Authentication and is the only supported
session transport in v1.

| Attribute | v1 value |
| --- | --- |
| Name | `AUTH_COOKIE_NAME`, default `insight_session` |
| Value | HS256-signed JWT |
| `HttpOnly` | `true` |
| `SameSite` | `Lax` |
| `Secure` | `AUTH_SECURE_COOKIE`, default `false` for local standalone development |
| `Max-Age` | `AUTH_COOKIE_MAX_AGE_SECONDS`, default `28800` seconds |
| `Path` | `/` |

CSRF uses a separate signed double-submit token:

| Property | Value |
| --- | --- |
| Cookie name | `AUTH_CSRF_COOKIE_NAME`, default `insight_csrf` |
| Header name | `AUTH_CSRF_HEADER_NAME`, default `x-csrf-token` |
| Cookie `HttpOnly` | `false` |
| Cookie `SameSite` | `Lax` |
| Cookie `Secure` | `AUTH_SECURE_COOKIE`, default `false` for local standalone development |
| Cookie `Max-Age` | `AUTH_CSRF_MAX_AGE_SECONDS`, default `28800` seconds |
| Cookie `Path` | `/` |

Production deployments must set:

- a high-entropy `AUTH_JWT_SECRET`;
- `AUTH_SECURE_COOKIE=true` when served behind HTTPS;
- non-default admin credentials before first database initialization.

Tokens must not be stored in `localStorage` or exposed to frontend JavaScript.
Logout expires the same configured cookie with `Max-Age=0`.

## Persistence and Migration Contract

Authentication owns its SQLite schema as an internal implementation detail.
Downstream modules must not read or write Authentication tables directly.

Startup runs numbered SQLite migrations before default admin seeding. The
current schema version is stored in the database header with
`PRAGMA user_version`, and migrations are written to be safe for existing
databases. The current migration set covers:

- initial user storage;
- server-side sessions;
- legacy `user` role normalization to `psychiatrist`;
- account disable and forced password rotation fields;
- failed-login tracking;
- versioned disclaimer acceptances;
- audit logging.

Operators should be able to upgrade an existing Authentication database in
place without deleting users. Any future schema change must add a new numbered
migration and keep `/api/auth/session` as the downstream authorization
boundary.

## Admin Account Lifecycle Boundaries

The v1 account lifecycle is intentionally narrow.

Supported:

- seed one default admin on first database initialization;
- configure the seed username with `AUTH_ADMIN_USERNAME`;
- configure the seed password with `AUTH_ADMIN_PASSWORD`;
- create new `admin` or `psychiatrist` accounts through
  `POST /api/auth/register` from an accepted admin session;
- reject duplicate usernames with `409`;
- hash all stored passwords with bcrypt.
- list accounts without password hashes through `GET /api/auth/admin/users`;
- disable accounts and revoke active sessions;
- enable disabled accounts;
- reset an account password to an admin-supplied or generated temporary
  password and revoke active sessions;
- force a temporary-password user through `POST /api/auth/password/change`
  before normal session access;
- update another account's role when doing so does not remove the final active
  admin.

Not supported in v1:

- anonymous registration;
- self-registration;
- unauthenticated password reset or recovery;
- deleting accounts through HTTP;
- rotating the seeded admin password by changing environment variables after
  the row already exists.

Changing `AUTH_ADMIN_PASSWORD` after the seeded admin row exists does not
change the stored password. Changing `AUTH_ADMIN_USERNAME` can seed another
admin if the new username is absent. Operators must treat first database
initialization as the boundary for seed-admin configuration.

## Standalone Runtime Contract

Authentication v1 must remain standalone-runnable.

Supported local run shape:

```powershell
pip install -r requirements.txt
python main.py
```

Supported package import shape from a larger INSIGHT repo:

```powershell
uvicorn modules.auth.main:app --reload
```

The import fallback in `main.py` and `router.py` is part of this contract. Do
not remove it unless the standalone run contract and this document are updated
in the same change.

## Downstream Verification Checklist

A downstream module verifies an authenticated request by:

1. receiving a browser request to a protected route;
2. forwarding the browser `Cookie` header to `GET /api/auth/session`;
3. accepting the request only when Authentication returns `200` with
   `ok: true`;
4. mapping `role: "admin"` to administrator authorization;
5. mapping `role: "psychiatrist"` to psychiatrist authorization;
6. rejecting or redirecting on every non-`200`, missing role, or unknown role.

The downstream module must not authorize from JWT decoding alone. Authentication
re-checks current account state, role, and disclaimer status before returning a
valid session response.
