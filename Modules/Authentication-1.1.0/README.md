# INSIGHT Authentication module

A standalone-runnable auth surface for the INSIGHT research prototype. Other
INSIGHT modules consume it only through its REST interface.

## Contract

The current session contract is documented in
[`docs/Authentication v2 Contract.md`](docs/Authentication%20v2%20Contract.md).
The deprecated v1 adapter remains documented in
[`docs/Authentication v1 Contract.md`](docs/Authentication%20v1%20Contract.md).
Downstream modules should use that document as the source of truth for roles,
session verification, redirects, disclaimer behavior, cookies, and admin
account lifecycle boundaries.

## Design

One deep module, with the small interface below; the implementation hides
SQLite, bcrypt, JWT signing, role gating, and the disclaimer gate.

| Method | Path | Returns | Purpose |
| --- | --- | --- | --- |
| GET | `/api/auth/health` | `{ ok, service, status }` | Liveness probe for Docker, nginx, and orchestrators. Alias: `/healthz`. |
| GET | `/api/auth/ready` | `{ ok, service, status, checks }` or 503 | Readiness probe that verifies DB access and required config without exposing config values. Alias: `/readyz`. |
| GET | `/api/auth/csrf` | `{ ok, csrf_token }` | Safe bootstrap route that sets the readable CSRF cookie and returns the token for write requests. |
| POST | `/api/auth/login` | `{ ok, next?, disclaimer_required?, password_change_required? }` | Verify credentials, create a server-side session, and issue the httponly signed cookie. |
| GET | `/api/auth/v2/session` | Versioned nested UUID identity | Canonical current session verification contract. |
| POST | `/api/auth/password/change` | `{ ok, next?, disclaimer_required? }` or 401 | Change a temporary password before dashboard access. |
| GET | `/api/auth/session` | v1 flat integer identity or 401 | Deprecated compatibility adapter. |
| GET | `/api/auth/disclaimer` | `{ ok, version, title, content_html, acknowledgement, accepted, accepted_version?, accepted_at?, message }` or 401 | Return the current auth-owned disclaimer contract and this psychiatrist's acceptance state. |
| POST | `/api/auth/disclaimer/accept` | `{ ok, next: "/dashboard/user" }` or 401 | Record acceptance of the active disclaimer version. |
| POST | `/api/auth/logout` | `{ ok, message: "Signed out." }` | Revoke the current session and expire the session cookie. |
| POST | `/api/auth/register` | `{ ok, user_id }` (admin-only) | Create a new account. Caller's session must be `role=admin`. |
| GET | `/api/auth/admin/users` | `{ ok, users }` (admin-only) | List accounts without password hashes. |
| POST | `/api/auth/admin/users/{id}/disable` | `{ ok, message }` (admin-only) | Disable an account and revoke its sessions. |
| POST | `/api/auth/admin/users/{id}/enable` | `{ ok, message }` (admin-only) | Re-enable a disabled account. |
| POST | `/api/auth/admin/users/{id}/reset-password` | `{ ok, user_id, temporary_password }` (admin-only) | Set or generate a temporary password and revoke sessions. |
| PATCH | `/api/auth/admin/users/{id}/role` | `{ ok, message }` (admin-only) | Update an account role when policy allows it. |

Default administrator credentials: `Admin` / `Admin` (configurable via env).

## Roles

Use `admin` for administrators and `psychiatrist` for psychiatrist accounts.
Legacy `user` input is still accepted for compatibility and normalized to
`psychiatrist`; session responses expose the canonical clinical role.

## Other modules register psychiatrists

An already-signed-in admin calls `POST /api/auth/register` with `{ username,
role, password }`. Use `role: "psychiatrist"` for psychiatrist accounts.
Anonymous access to account creation is intentionally denied and matches the
spec's "ask admin to register" wording.

Before any `POST` or `PATCH`, same-origin browser clients must call
`GET /api/auth/csrf` and echo the returned token in `X-CSRF-Token`.

## Admin account management

Accepted admins can list accounts, disable or enable accounts, reset a
password to a temporary password, and update another account's role. Account
listing never returns password hashes. Reset passwords force the user through
`/api/auth/password/change` before `/api/auth/session` succeeds. Disabling an
account, resetting a password, or changing a role revokes that account's active
sessions. Disabled accounts receive the same generic login failure as bad
credentials.

## Security properties

- bcrypt 12-round hashing for all stored passwords.
- HS256-signed JWT in an `HttpOnly`, `SameSite=Lax`, `Secure` (configurable) cookie. Not stored in `localStorage`.
- Signed double-submit CSRF protection for all state-changing auth routes.
- Generic "Wrong username or password" message never reveals which field failed.
- SQLite-backed failed-login limiting locks a username/client tuple after repeated failures; successful login clears that tuple.
- SQLite schema version is stored in `PRAGMA user_version`; startup runs idempotent migrations before seeding the default admin.
- Role selected at login MUST match the stored role after compatibility normalization.
- Whitelist-validated redirect target: `next` only accepts paths listed in `AUTH_ALLOWED_REDIRECTS`.
- Temporary password rotation is enforced server-side before normal session access.
- Disclaimer gate is enforced server-side: a `psychiatrist` account cannot reach `/dashboard/user` until an acceptance record exists for the active disclaimer version.
- Disabled accounts are rejected both at login and during session resolution.

## Persistence

The SQLite database upgrades in place on startup. Migrations are numbered and
stored in the database header via `PRAGMA user_version`, so existing users are
preserved while the auth schema evolves. The current migrations create or
upgrade users, sessions, login failure tracking, account status and password
rotation fields, versioned disclaimer acceptances, and audit logging.

## Standalone run

```bash
pip install -r requirements.txt
python main.py
# open http://localhost:8000/
```

## Environment

See `.env.example` for all knobs and defaults. Required change for production:
set `AUTH_JWT_SECRET` to a `secrets.token_urlsafe(64)` output, and flip
`AUTH_SECURE_COOKIE=true` behind HTTPS.

Docker/VPS health checks can use `GET /healthz` for liveness and `GET /readyz`
for readiness. Readiness returns HTTP 503 until SQLite is reachable and required
config is present; responses include only check names and statuses, never secret
or path values.

## Test

The auth suite uses only per-test temporary SQLite databases. Run it with
bytecode disabled so local/CI runs do not write generated `__pycache__` files
into the repo:

```bash
python -B -m unittest discover -s tests
```
