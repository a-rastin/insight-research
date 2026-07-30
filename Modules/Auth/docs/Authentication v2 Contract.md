# INSIGHT Authentication v2 Session Contract

Status: current

Interface version: `2.0.0`

Schema: [`auth-session-v2.schema.json`](auth-session-v2.schema.json)

## Trust boundary

Consumers verify browser identity with `GET /api/auth/v2/session`. They must
forward the opaque Authentication cookie and must not decode its JWT, read the
Authentication database, trust request-body identity, or parse a human message.
Successful responses carry `X-Schema-Version: 2.0.0`.

Authentication returns `401` when the cookie, server-side session, current
account, or current role is invalid, disabled, revoked, or expired. A valid
session with an outstanding password or disclaimer gate returns `200` with
`authenticated: true` and `authorized: false`. Consumers authorize protected
work only when `authorized` is `true` and `user.role` is permitted.

## Success response

```json
{
  "authenticated": true,
  "authorized": true,
  "interfaceVersion": "2.0.0",
  "session": {
    "id": "e8c996c1-ab80-4de0-a9f4-70d36a80f301",
    "active": true,
    "expiresAt": "2026-07-29T18:30:00Z"
  },
  "user": {
    "id": "35e65add-887d-4911-a970-97a4e5300a21",
    "username": "doc1",
    "role": "psychiatrist"
  },
  "gates": {
    "passwordChangeRequired": false,
    "disclaimerRequired": false,
    "disclaimerVersion": "2026-07-06"
  },
  "compatibility": {
    "legacyUserId": 2,
    "legacyRole": "user"
  }
}
```

`user.id` and `session.id` are stable UUIDs owned by Authentication. Existing
integer user IDs remain internal keys and are exposed only as the explicitly
deprecated `compatibility.legacyUserId` mapping. Roles are lowercase `admin`
and `psychiatrist`; legacy `user` maps to `psychiatrist` only at the boundary.
`expiresAt` is canonical RFC 3339 UTC and always uses the uppercase `Z` suffix;
numeric offsets such as `+00:00` are not valid v2 response values.

## Compatibility

`GET /api/auth/session` remains the v1 compatibility adapter. Its response is
unchanged and carries `Deprecation` and successor `Link` headers. A `Sunset`
date is not published until consumer rollout is scheduled. It
uses the same live session resolver as v2, so disablement, revocation, password
reset, role change, expiry, and disclaimer-version changes remain immediate.

## Migration and rollback

Migration 007 appends UUID columns and unique indexes, assigns one UUID to each
existing user and session, and preserves integer keys and all existing rows.
Rollback requires stopped writes and a verified database backup. Set
`PRAGMA user_version = 6` before starting v1 code; added nullable columns and
indexes are compatible with v1 writes. Reapplying migration 007 backfills UUIDs
for rows created during rollback. Do not delete UUID columns or mappings.
