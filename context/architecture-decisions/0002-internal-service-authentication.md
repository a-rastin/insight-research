# ADR-0002: Internal Service Authentication and Attribution

- Status: Accepted
- Date: 2026-07-28
- Decision owners: Security Architecture
- Scope: INS-003

## Context

INSIGHT modules communicate through internal REST APIs while Authentication
remains sole authority for user sessions and roles. Calls must identify calling
service without allowing background work to impersonate psychiatrist, leaking
session credentials, or turning caller-controlled URLs into SSRF targets.

This decision follows [architecture invariants](../architecture.md), the
[INS-003 specification](../feature-specs/03-internal-service-authentication.md),
and [ADR-0001](0001-runtime-matrix.md). Normative machine-readable rules and
examples live in [internal-service-auth-v1.json](../../contracts/internal-service-auth-v1.json)
and are checked by [test_internal_service_auth.py](../../tests/test_internal_service_auth.py).

## Decision

Use contract version `1.0.0` and per-service HMAC-SHA256 request assertions.
Each caller/destination pair has its own key ID and secret supplied through
environment or a read-only secret mount. A caller signs destination service ID,
method, raw request target, exact body hash, timestamp, nonce, and
request/correlation/causation identifiers. Canonical fields are UTF-8 encoded
and LF-joined without a trailing LF; fields containing CR or LF are rejected.
Targets reject unknown or disabled services and keys, invalid signatures,
timestamps outside 60 seconds, replayed nonces, and methods or paths outside
caller's configured capability set. Rotation may overlap two key IDs; pairwise
keys are not reused for another caller or destination.

For user-attributed calls, forward only the configured Authentication session
cookie. Do not forward the complete `Cookie`, `Authorization`, CSRF, or
caller-supplied identity headers. Every protected target sends that opaque cookie
to Authentication's session endpoint and derives current user and role only from
a successful response. No session result is cached for authorization. Revocation,
disablement, role change, password reset, expiry, and disclaimer change therefore
take effect on the next protected call. Finalization revalidates immediately
before mutation and requires a current psychiatrist session.

Background calls use service HMAC only. They contain no session cookie or user
identity, are recorded as service actors, and cannot call endpoints requiring a
psychiatrist or finalize clinical data.

Browser writes enforce same-origin signed double-submit CSRF at the first module.
Internal HMAC-authenticated calls neither forward nor re-check browser CSRF;
service authentication protects that hop. This does not remove user-session and
role checks from user-attributed internal operations.

Outbound clients resolve destinations from configured service IDs. Unified
loopback calls use fixed `http` plus exact IP and port from ADR-0001. Gateway
base paths are not internal API capability paths. A validated read-only
deployment configuration supplies each caller's destination, exact method, and
segment-bounded path-prefix capabilities; missing or malformed capability
configuration denies all calls. Paths containing dot segments, backslashes, or
percent-encoded path separators are rejected before matching. Callers cannot
supply URLs, redirects are disabled, and requests outside both the registry and
caller's least-privilege capability set fail before network access.

Every hop creates a random UUID `X-Request-ID` and preserves the root request's
random UUID `X-Correlation-ID`. `X-Causation-ID` is absent at root and equals
parent hop's request ID on later hops. These values never contain patient or
user data.

Service-auth successes/failures, session denials, and privileged access belong
to append-only security audit. Clinical inputs, recommendations, edits,
overrides, and finalization evidence belong to owning-module clinical provenance.
Both may reference the same safe trace IDs, but neither copies the other's
payload. Cookies, HMAC values, secrets, PHI, and request/response bodies are
redacted from logs.

## Alternatives

| Alternative | Reason rejected |
| --- | --- |
| Mutual TLS | Strong identity but adds certificate issuance, trust stores, rotation, and local PKI to one-container loopback deployment. |
| OAuth2 client credentials | Adds token issuance, validation, expiry, and refresh behavior before INSIGHT needs delegated external clients. |
| Static bearer token | Easier but replayable, does not bind request content or destination, and encourages shared credentials. |
| Forward decoded user headers | Lets callers impersonate users and bypass current Authentication state. |

## Consequences

- Each module needs a small HMAC verification/outbound-signing adapter and a
  bounded nonce replay cache before protected internal endpoints are enabled.
- Authentication session contract remains authority; no module decodes JWTs.
- Existing adapters that forward full cookie or authorization headers must be
  narrowed during rollout.
- Pairwise service-key issuance, rotation, revocation, and caller destination
  sets become deployment configuration and operational responsibilities.
- Clinical release status remains blocked and unchanged.

## Verification

Run `python3 -m unittest tests/test_internal_service_auth.py`. Tests validate
contract version and signing fields, cookie and CSRF boundaries, safe trace and
logging policy, required browser/server/revocation/background/SSRF examples, and
the ADR's relative links.

## Rollback

Before runtime rollout, supersede this ADR and contract together. After rollout,
disable affected internal routes, rotate exposed service keys, deploy a
superseding version with dual-read support only for a bounded migration, then
remove v1 verification after all callers move. Never fall back to decoded JWTs,
request-body identity, shared bearer secrets, or unrestricted destinations.
