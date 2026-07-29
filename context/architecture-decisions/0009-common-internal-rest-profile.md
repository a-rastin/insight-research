# ADR-0009: Common Internal REST Profile

- Status: Accepted
- Date: 2026-07-29
- Decision owners: Architecture
- Scope: INS-012

## Context

INSIGHT modules need one copyable REST contract for health, readiness, contract
discovery, version negotiation, safe errors, tracing, concurrency, and retry
semantics. Existing modules use inconsistent routes, identifiers, and response
shapes. This decision follows the [architecture invariants](../architecture.md),
[INS-012 specification](../feature-specs/12-common-internal-REST-profile.md), and
[ADR-0002](0002-internal-service-authentication.md).

Normative rules live in
[common-rest-profile-v1.json](../../contracts/common-rest-profile-v1.json).
Reusable JSON Schemas and OpenAPI components live beside that file and are
verified by
[test_common_rest_profile.py](../../tests/test_common_rest_profile.py).

## Decision

Adopt profile version `1.0.0`. Modules package the four
`common-rest-profile-v1.*.json` artifacts together without editing them. Module
OpenAPI documents reference the packaged components and add only module-owned
paths and schemas.

All JSON responses identify their schema with `X-Schema-Version`. UUID trace
headers and UTC timestamps use the canonical schemas. Every hop creates a new
`X-Request-ID`, preserves `X-Correlation-ID`, and sets `X-Causation-ID` to the
parent request ID after the root hop.

Major versions are compatibility boundaries. Providers reject unsupported
request-schema majors with typed problem details. Consumers reject unsupported
response-schema majors before using or persisting the body and expose a typed
dependency failure. Minor versions may add optional fields; patch versions may
clarify or correct behavior without changing valid instances. Removal or a new
required field requires a new major. Deprecation cannot remove a v1 field or
operation in place; a successor is published, all consumers pass compatibility
tests, and rollout completes before sunset.

Mutable resources return strong ETags. Writes require exact `If-Match`; missing
preconditions return `428` and stale preconditions return `412`. Retryable
creates and durable actions require `Idempotency-Key`. Same key and request
semantics replay the original result; changed semantics return `409`.

Problem responses expose only controlled fields. They omit request targets,
filesystem paths, stack traces, dependency internals, credentials, secrets, and
PHI. Error production still requires boundary redaction because schema
validation cannot determine whether arbitrary text contains PHI.

## Alternatives

| Alternative | Reason rejected |
| --- | --- |
| Per-module common types | Creates drift and incompatible safety behavior. |
| Shared runtime package | Couples independently runnable Python and Node.js modules. |
| OpenAPI-only definitions | Does not provide standalone JSON Schema validation. |
| Weak ETags or last-writer-wins | Cannot protect clinical edits from lost updates. |

## Consequences

- Each module must package unchanged common artifacts and reference them from
  its module-owned OpenAPI contract.
- Existing route and payload migrations remain separate module packets.
- Provider and consumer tests must reject unsupported major versions.
- Runtime adapters must generate safe problem details and enforce ETag and
  idempotency rules before claiming profile conformance.
- Clinical deployment status remains blocked and unchanged.

## Verification

Run `python3 -B -m unittest tests/test_common_rest_profile.py -v`. Tests validate
all examples, invalid UUID/time/header/error fixtures, OpenAPI references,
compatibility/deprecation behavior, safe errors, ETags, and idempotent replay.

## Rollback

Before module rollout, revert this ADR and its four contract artifacts together.
After rollout, publish a superseding profile, retain v1 until every provider and
consumer passes dual-version compatibility tests, then sunset v1. Never roll
back to unversioned payloads, unsafe errors, weak concurrency, or duplicate
idempotent effects.
