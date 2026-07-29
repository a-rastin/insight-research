# INSIGHT Authentication Module Handoff

Last reviewed: 2026-07-06

This document is for future LLMs or maintainers working in
`modules/auth`. It explains how the authentication module is structured, what
security invariants it enforces, where the important seams live, and what to
avoid when changing it.

## Executive Summary

This module is a standalone FastAPI authentication surface for the INSIGHT
research prototype. It owns:

- the login page at `/`;
- auth routes under `/api/auth/*`;
- username/password verification;
- default admin seeding;
- account creation by an authenticated admin;
- JWT session cookies;
- server-side disclaimer gating for `user` accounts;
- account status, password rotation, failed-login tracking, and audit logging;
- lightweight SQLite persistence.

Other INSIGHT modules should treat this module as an internal auth provider and
call `GET /api/auth/session` with the browser cookie attached. They should not
decode the JWT themselves. The important invariant is:

> A valid signed JWT is not enough. A session is authorized only after
> `security.resolve_session()` re-checks the current database row, role, and
> disclaimer state.

## Files

| Path | Purpose |
| --- | --- |
| `main.py` | FastAPI app construction, static file mounting, root login page, SPA-style fallback. |
| `router.py` | Public HTTP interface under `/api/auth`; translates requests/responses and HTTP errors. |
| `security.py` | Deep auth module implementation: config, password hashing, JWTs, cookies, SQLite persistence, session resolution. |
| `static/index.html` | Single-file login and disclaimer UI. |
| `tests/test_auth.py` | Plain Python regression script covering security helpers and route-level behavior. |
| `.env.example` | Environment variable reference. |
| `requirements.txt` | Runtime dependencies. |
| `README.md` | User-facing module overview. |

## Runtime Entry Points

There are two supported run shapes:

```powershell
cd E:\authentication\modules\auth
python main.py
```

or, from a repo root where `modules` is importable:

```powershell
uvicorn modules.auth.main:app --reload
```

`main.py` uses a relative import first and falls back to local imports so both
shapes work:

```python
try:
    from .router import router
except ImportError:
    from router import router
```

Keep that pattern if the module remains runnable both as a package and as a
loose script.

## HTTP Interface

All API routes are mounted under `/api/auth`.

### `POST /api/auth/login`

Request:

```json
{
  "username": "Admin",
  "password": "Admin",
  "role": "admin"
}
```

Role must be `admin`, `psychiatrist`, or legacy alias `user`.

Behavior:

- looks up the user by username;
- verifies the password with bcrypt;
- rejects login if the selected role does not match the stored role;
- issues an HttpOnly JWT cookie on successful credential verification;
- returns admin dashboard redirect for admins;
- returns user dashboard redirect only if the user disclaimer is already signed;
- otherwise returns `disclaimer_required: true`.

Important detail: for an unsigned `user`, login still sets the cookie. That
cookie is needed so the user can call `/api/auth/disclaimer/accept`. The cookie
must not be treated as an active application session until the disclaimer is
signed. This is enforced by `GET /api/auth/session`.

Responses:

```json
{ "ok": true, "next": "/dashboard/admin", "disclaimer_required": false }
```

```json
{ "ok": true, "next": null, "disclaimer_required": true }
```

Errors:

- `401` for wrong username or password;
- `403` for role mismatch, using the same generic message.

The generic failure message is intentional to avoid revealing which field
failed.

### `POST /api/auth/register`

Admin-only account creation.

Request:

```json
{
  "username": "doc1",
  "password": "secret",
  "role": "user"
}
```

Behavior:

- resolves the caller session with `require_disclaimer=True`;
- requires the caller role to be `admin`;
- stores a bcrypt password hash;
- returns the created user id.

Responses:

```json
{ "ok": true, "user_id": 2 }
```

Errors:

- `401` if the caller is missing, invalid, stale, deleted, a pending
  disclaimer user, or non-admin;
- `409` if the username already exists.

The router catches `security.DuplicateUsernameError`, not `sqlite3` errors.
Keep SQLite details inside `security.py`.

### Admin account management

Accepted admins can manage accounts through:

- `GET /api/auth/admin/users`;
- `POST /api/auth/admin/users/{user_id}/disable`;
- `POST /api/auth/admin/users/{user_id}/enable`;
- `POST /api/auth/admin/users/{user_id}/reset-password`;
- `PATCH /api/auth/admin/users/{user_id}/role`.

Account listing returns account metadata only, never password hashes. Disabling
an account, resetting a password, and changing a role all revoke the target
account's sessions. Disabled accounts fail login with the generic credential
failure and fail session resolution through `resolve_session()`.

### `GET /api/auth/disclaimer`

Pending-or-signed user-only endpoint.

Behavior:

- resolves the cookie with `require_disclaimer=False`;
- allows `psychiatrist` accounts that have not accepted the active version yet;
- returns the current auth-owned disclaimer content and version;
- rejects admins and invalid sessions.

Pending response:

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

Accepted response:

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

### `POST /api/auth/disclaimer/accept`

Pending-or-signed user-only endpoint.

Behavior:

- resolves the cookie with `require_disclaimer=False`;
- requires role `psychiatrist`;
- stores the caller user id, timestamp, and active disclaimer version;
- returns the user dashboard redirect.

Response:

```json
{ "ok": true, "next": "/dashboard/user", "disclaimer_required": false }
```

### `GET /api/auth/session`

This is the main contract other modules should consume.

Behavior:

- reads the configured cookie;
- calls `security.resolve_session(token, require_disclaimer=True)`;
- returns `401` unless the JWT is valid and the current DB user still exists,
  still has the token role, and, for `user` accounts, has accepted the
  disclaimer.

Response:

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

Do not broaden this route to return a pending user session. That would reopen
the disclaimer bypass bug.

### `POST /api/auth/logout`

Expires the configured cookie by setting the same cookie attributes and
`max_age=0`.

Response:

```json
{ "ok": true, "message": "Signed out." }
```

## Browser UI Flow

`static/index.html` is a single-file login/disclaimer UI.

Login flow:

1. User submits username, password, and selected role.
2. Browser calls `POST /api/auth/login`.
3. If response has `password_change_required: true`, the page renders the
   password-change state and stays on the auth page.
4. If response has `disclaimer_required: true`, the page renders the disclaimer
   and stays on the auth page.
5. Otherwise the browser redirects to `data.next`.
6. On page load, the browser calls `GET /api/auth/session`.
7. Only an accepted session redirects away from `/`.

The login page does not ship production credential values. `Admin` / `Admin`
autofill is limited to localhost with `?dev_autofill=1`.

## Core Security Seam

The central seam is:

```python
security.resolve_session(token: str, require_disclaimer: bool = True) -> dict | None
```

This function is deliberately deeper than `verify_token()`.

`verify_token()` only proves:

- the token is syntactically valid;
- the token signature is valid;
- the token has not expired according to JWT `exp`.

`resolve_session()` additionally proves:

- `sub` exists and is an integer;
- the user still exists in SQLite;
- the token role still matches the current stored role;
- if `require_disclaimer=True`, a `user` account has signed the disclaimer.

Use `resolve_session()` for authorization. Use `verify_token()` only for low
level token tests or diagnostics.

### `require_disclaimer` Rules

Default to `require_disclaimer=True`.

Use `require_disclaimer=False` only for routes that must be reachable by a
pending user so they can finish the disclaimer flow:

- `GET /api/auth/disclaimer`;
- `POST /api/auth/disclaimer/accept`.

Do not use `require_disclaimer=False` for `/session`, `/register`, dashboard
access, or protected downstream module access.

## Data Model

SQLite schema is managed by numbered migrations in `security.py`. The current
schema version is stored in the SQLite database header with
`PRAGMA user_version`, so startup can upgrade existing databases in place
before seeding the default admin.

### `users`

| Column | Meaning |
| --- | --- |
| `id` | Integer primary key. |
| `username` | Unique login name. |
| `role` | `admin` or `psychiatrist`. Legacy `user` input is normalized. |
| `password_hash` | bcrypt hash. Never store plaintext. |
| `disabled` | Boolean-ish SQLite value. `1` means the account cannot log in or resolve sessions. |
| `must_change_password` | Boolean-ish SQLite value. `1` means normal session resolution is blocked until password rotation succeeds. |
| `disclaimer_signed` | Compatibility projection. Active acceptance is checked against `disclaimer_acceptances`. |
| `created_at` | SQLite timestamp from `datetime('now')`. |

### `disclaimer_acceptances`

Versioned psychiatrist disclaimer acceptance history:

| Column | Meaning |
| --- | --- |
| `user_id` | User that accepted the disclaimer. |
| `version` | Disclaimer version accepted by the user. |
| `accepted_at` | SQLite timestamp from `datetime('now')`. |

### `sessions`

The `sessions` table is the server-side revocation source of truth:

| Column | Meaning |
| --- | --- |
| `token` | Signed JWT stored exactly as issued. Primary key. |
| `user_id` | Owning account id. |
| `expires_at` | Unix timestamp in seconds. Must match the JWT `exp`. |

`issue_token()` inserts a row, `resolve_session()` requires that row to exist
and still be unexpired, `logout()` deletes the current row through
`revoke_session()`, and account lifecycle flows can call
`revoke_sessions_for_user()`.

### `login_failures`

Failed login attempts are tracked per username/client tuple for local lockout
enforcement. Successful login clears the tuple.

### `audit_log`

Security-relevant account and auth events are appended without plaintext
passwords or JWTs.

## Persistence and Concurrency

`security.py` uses one module-global SQLite connection:

```python
_conn = None
_conn_lock = threading.RLock()
```

`get_conn()` lazily creates the connection, runs pending migrations, seeds the
default admin, commits, and returns the singleton. The connection uses
`check_same_thread=False`, so all reads and writes that use the shared
connection must be protected by `_conn_lock`.

Current public persistence functions:

- `get_user(username)`;
- `get_user_by_id(user_id)`;
- `list_users()`;
- `register_user(username, role, password)`;
- `set_user_disabled(user_id, disabled, actor_user_id=None)`;
- `reset_user_password(user_id, temporary_password=None)`;
- `update_user_role(user_id, role, actor_user_id=None)`;
- `set_disclaimer_signed(user_id)`.

Write transactions use `_tx(conn)`, which wraps the connection lock,
commit/rollback behavior, and exception propagation.

Do not leak `sqlite3.IntegrityError` or raw SQL details to `router.py`. Add
domain exceptions in `security.py` when needed.

## Passwords

Passwords are hashed with bcrypt:

```python
bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(12))
```

Verification uses `bcrypt.checkpw()` and catches malformed hash inputs.

Do not:

- store plaintext passwords;
- move password hashing into the router;
- add a second hash layer without a migration plan;
- lower the bcrypt cost without a performance/security reason.

## JWT and Cookie Behavior

JWTs:

- use HS256;
- contain `sub`, `role`, `iat`, `exp`, and `jti`;
- are signed with `AUTH_JWT_SECRET`;
- expire after `AUTH_COOKIE_MAX_AGE_SECONDS` unless `issue_token()` is called
  with an explicit `expires_in`;
- require a matching live row in `sessions` before authorization succeeds.

Cookies are configured by `security.cookie_kwargs()`:

| Attribute | Value |
| --- | --- |
| `key` | `AUTH_COOKIE_NAME`, default `insight_session`. |
| `httponly` | `True`. |
| `samesite` | `lax`. |
| `secure` | `AUTH_SECURE_COOKIE`, default `false`. |
| `max_age` | `AUTH_COOKIE_MAX_AGE_SECONDS`, default `28800`. |
| `path` | `/`. |

Do not move tokens into `localStorage`.

## Configuration

Configuration is read directly from `os.environ` through:

- `cfg(key)`;
- `cfg_int(key, default)`;
- `cfg_bool(key)`.

Defaults:

| Variable | Default | Notes |
| --- | --- | --- |
| `AUTH_DB_PATH` | `./auth.db` | Relative to the process working directory. |
| `AUTH_JWT_SECRET` | `change-me-in-production-use-secrets.token_urlsafe` | Must be changed outside local dev. |
| `AUTH_COOKIE_NAME` | `insight_session` | Browser session cookie name. |
| `AUTH_COOKIE_MAX_AGE_SECONDS` | `28800` | Eight hours. |
| `AUTH_SECURE_COOKIE` | `false` | Set `true` behind HTTPS. |
| `AUTH_ADMIN_USERNAME` | `Admin` | Seeded on first DB creation if absent. |
| `AUTH_ADMIN_PASSWORD` | `Admin` | Seed password only; changing it later does not update existing admin. |
| `AUTH_ALLOWED_REDIRECTS` | `/dashboard/admin,/dashboard/user` | Parsed by `_safe_redirect()`, currently unused by login requests. |
| `AUTH_LOGIN_FAILURE_LIMIT` | `5` | Failed attempts per username/client tuple before lockout. Set `0` only for isolated test fixtures. |
| `AUTH_LOGIN_FAILURE_WINDOW_SECONDS` | `300` | Rolling window for counting failed login attempts. |
| `AUTH_LOGIN_LOCKOUT_SECONDS` | `900` | Temporary lockout duration once the failure limit is reached. |

Production must set at least:

- `AUTH_JWT_SECRET` to a high-entropy secret;
- `AUTH_SECURE_COOKIE=true` behind HTTPS;
- non-default admin credentials before first database initialization.

## Default Admin Seeding

On first connection, `_seed_default_admin(conn)` checks whether
`AUTH_ADMIN_USERNAME` exists. If not, it inserts that username with role
`admin`, a bcrypt hash of `AUTH_ADMIN_PASSWORD`, and `disclaimer_signed=1`.

Important implications:

- changing `AUTH_ADMIN_PASSWORD` after the row exists does not rotate the
  password;
- changing `AUTH_ADMIN_USERNAME` can seed a second admin if the new username is
  absent;
- a real production deployment needs an explicit admin credential lifecycle.

## Import Shape

`main.py` and `router.py` both support package and local script execution.

`router.py` imports `security` like this:

```python
try:
    from . import security
except ImportError:
    import security
```

If the module is later converted into a normal package with `__init__.py`
files and no script-mode requirement, this fallback can be simplified, but do
not break the README's advertised run modes without updating docs and tests.

## Testing

The current test command is:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python tests/test_auth.py
```

`PYTHONDONTWRITEBYTECODE=1` keeps test runs from modifying `__pycache__`.

The test script:

- puts the module root on `sys.path`;
- creates a temp SQLite DB under `%TEMP%` or `/tmp`;
- sets `AUTH_DB_PATH` and `AUTH_JWT_SECRET`;
- imports `security` and `main`;
- checks default admin seeding;
- checks password hash/verify behavior;
- checks JWT issue/verify behavior;
- checks pending disclaimer session rejection;
- checks stale role token rejection;
- checks deleted-user token rejection;
- checks fresh and upgraded database migration paths;
- checks admin login through HTTP;
- checks admin-only registration through HTTP;
- checks duplicate username returns `409`;
- checks pending user `/session` returns `401`;
- checks disclaimer acceptance enables `/session`.

Also verify package import mode when changing imports:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'; python -c "import sys; sys.path.insert(0, r'E:\authentication'); import modules.auth.main as m; print(m.app.title)"
```

Expected output:

```text
INSIGHT Authentication
```

## Route Policy Matrix

| Route | Anonymous | Admin | User pending disclaimer | User accepted |
| --- | --- | --- | --- | --- |
| `POST /login` | Allowed | Allowed | Allowed | Allowed |
| `POST /password/change` | 401 | Allowed only if current session is valid | Allowed only when rotating password | Allowed |
| `POST /register` | 401 | Allowed | 401 | 401 |
| `GET /disclaimer` | 401 | 401 | Allowed | Allowed |
| `POST /disclaimer/accept` | 401 | 401 | Allowed | Allowed |
| `GET /session` | 401 | Allowed | 401 | Allowed |
| `POST /logout` | Allowed | Allowed | Allowed | Allowed |

`logout` is safe for anonymous callers because it only expires the cookie.

## Common Change Recipes

### Add a New Protected Auth Route

1. Add the route in `router.py`.
2. Call `_current_user(request)` with the default `require_disclaimer=True`.
3. Check the returned role or user id.
4. Keep persistence calls in `security.py`.
5. Add a route-level test in `tests/test_auth.py`.

### Add a Pending-Disclaimer Route

Only do this for the disclaimer flow itself.

1. Call `_current_user(request, require_disclaimer=False)`.
2. Require `payload.get("role") == "psychiatrist"`.
3. Do not return dashboard access or normal session success from this route.
4. Add a regression test proving `/session` still rejects pending users.

### Extend Password or Account Lifecycle Flows

Password reset, account disable/enable, account listing, and role updates are
now implemented as admin-only routes. Keep future lifecycle changes in
`security.py`, update the DB in `_tx(conn)`, and call
`revoke_sessions_for_user(user_id)` when existing sessions should stop working
immediately.

### Add Audit Logging

Keep route code small. Prefer auth-domain functions in `security.py` or a new
internal module called by `security.py`. Log at least:

- successful login;
- failed login;
- registration;
- disclaimer acceptance;
- logout.

Do not log plaintext passwords or JWTs.

### Maintain Server-Side Sessions

Keep all authorization callers on `resolve_session()`. Do not bypass it with
`verify_token()`, because that would skip server-side revocation, current user
state, role mismatch, and disclaimer checks.

## Known Limitations

These are not necessarily bugs in the current prototype, but future agents
should not miss them:

- SQLite login rate limiting is local to this database/process; use the existing limiter seam for a Redis-backed multi-instance deployment;
- no forgotten-password recovery flow;
- no first-login admin password rotation;
- SQLite migrations are local to this module and should be extended carefully
  for future schema changes;
- `AUTH_ALLOWED_REDIRECTS` and `_safe_redirect()` exist but login does not
  currently accept a `next` parameter;
- the default local admin credentials are insecure outside development;
- deployment security depends on setting `AUTH_SECURE_COOKIE=true` behind
  HTTPS and using a strong `AUTH_JWT_SECRET`.

## Things Future LLMs Should Not Do

- Do not treat `verify_token()` as authorization.
- Do not make `/api/auth/session` accept pending disclaimer users.
- Do not decode JWTs in other modules instead of calling `/api/auth/session`.
- Do not catch `sqlite3` exceptions in `router.py`.
- Do not move bcrypt or JWT implementation details into route handlers.
- Do not store auth tokens in browser `localStorage`.
- Do not remove package/local import fallback without updating the run contract.
- Do not run tests without considering generated `.pyc` files; prefer
  `PYTHONDONTWRITEBYTECODE=1`.

## Mental Model

Think of this module as two layers:

1. `router.py` is the HTTP interface. It validates request shapes, maps domain
   outcomes to HTTP responses, and sets/clears cookies.
2. `security.py` is the auth implementation. It owns password hashing, token
   signing, session resolution, DB access, and domain exceptions.

The most important call path is:

```text
browser cookie
  -> router._current_user()
  -> security.resolve_session()
  -> security.verify_token()
  -> security.get_user_by_id()
  -> role/disclaimer/current-user checks
  -> authorized payload or None
```

Keep that path deep and boring. If a future feature needs auth policy, put the
policy where this path can enforce it once for every caller.
