# ADR-0001: Unified Runtime Matrix

- Status: Accepted
- Date: 2026-07-28
- Decision owners: Architecture and Operations
- Scope: INS-002

## Context

INSIGHT must run in one Docker image without merging module processes, storage,
health state, or ownership. Current standalone defaults collide on ports 8000,
4173, and 3000, health routes vary, and no internal gateway or container PID 1
has been selected. Only the gateway may be public. Browser routes must remain
relative to that gateway.

This decision follows [project boundaries](../project-overview.md),
[architecture invariants](../architecture.md), and the approved
[INS-002 specification](../feature-specs/02-runtime-matrix.md). Machine-readable
values live in [runtime-policy.json](../../deploy/runtime-policy.json) and are
checked by [test_runtime_policy.py](../../tests/test_runtime_policy.py).

## Decision

Use nginx as internal gateway on container port 8080. Publish only that port.
Bind every module process to a unique loopback port. Run supervisord as PID 1,
with nginx and all module processes running as non-root UID 10001. Keep one
process boundary and one writable data directory per module.

Use Python 3.13 for Python services and Node.js 22 LTS for Node services and
frontend builds. Treatment Plan uses both runtimes but remains one independently
owned module process at runtime; Vite is build-time only.

| Process | Runtime | Internal port | Gateway base path | Liveness | Readiness | Data directory |
| --- | --- | ---: | --- | --- | --- | --- |
| Gateway | nginx | 8080 | `/` | `/healthz` | `/readyz` | None |
| Authentication | Python | 8101 | `/api/auth` | `/healthz` | `/readyz` | `/var/lib/insight/authentication` |
| Dashboard | Python | 8102 | `/dashboard` | `/healthz` | `/readyz` | `/var/lib/insight/dashboard` |
| Add New Patient | Python | 8103 | `/modules/add-new-patient` | `/healthz` | `/readyz` | `/var/lib/insight/add-new-patient` |
| Diagnosis | Python | 8104 | `/modules/diagnosis` | `/health` | `/ready` | `/var/lib/insight/diagnosis` |
| Severity | Node.js | 8105 | `/modules/severity` | `/healthz` | `/readyz` | `/var/lib/insight/severity` |
| Medical History | Node.js | 8106 | `/modules/medical-history` | `/healthz` | `/readyz` | `/var/lib/insight/medical-history` |
| DDI Checker | Node.js | 8107 | `/modules/ddi` | `/healthz` | `/readyz` | `/var/lib/insight/ddi-checker` |
| BN Manager | Python | 8108 | `/api/bn-manager/v1` | `/api/health` | `/api/ready` | `/var/lib/insight/bn-manager` |
| Suicide Risk | Node.js | 8109 | `/modules/suicide-risk` | `/healthz` | `/readyz` | `/var/lib/insight/suicide-risk` |
| Treatment Plan | Python + Node build | 8110 | `/modules/treatment-plan` | `/health` | `/ready` | `/var/lib/insight/treatment-plan` |

Gateway liveness checks only nginx process health. Gateway readiness succeeds
only when every required module readiness probe succeeds. Failure names
unavailable module IDs but omits internal URLs, paths, credentials, stack traces,
and response bodies. Module liveness and readiness remain independently
queryable inside container network namespace.

On SIGTERM, supervisord stops accepting gateway traffic, forwards SIGTERM to
child process groups, and allows 30 seconds for graceful shutdown. Remaining
processes receive SIGKILL. Container exits nonzero when required process exits
unexpectedly. Runtime databases and mutable files remain in module-specific
mounted directories and are never baked into image.

DDI Checker does not yet expose its selected production REST service seam.
Unified readiness must remain failed for any missing required process or probe;
gateway must not synthesize healthy states. Follow-up has no approved standalone
service contract and receives no port in this matrix.

## Alternatives

| Area | Rejected alternative | Trade-off |
| --- | --- | --- |
| Gateway | Caddy or Traefik | Useful automatic discovery and TLS features duplicate nginx public-edge policy and add another configuration model. |
| Gateway | Custom Python/Node router | Reuses application runtimes but creates avoidable routing, streaming, timeout, and security-header code. |
| Supervisor | s6-overlay | Strong supervision model, but adds image conventions and shell tooling not otherwise required. |
| Supervisor | systemd in container | Familiar on Ubuntu, but heavy and conflicts with host systemd owning container rather than child services. |
| Supervisor | Shell background jobs | Small initial script, but weak signal forwarding, restart policy, exit propagation, and process reaping. |
| Runtimes | Per-module Python/Node versions | Better isolation, but expands single-image size and patch surface. Python 3.13 and Node 22 satisfy declared strictest module constraints. |
| Health | Gateway ready when any module is ready | Keeps navigation partially available, but can represent required clinical dependencies as operational. Fail closed instead. |
| Ports | Preserve standalone defaults | Avoids configuration changes but leaves collisions and ambiguous probes inside unified container. |

## Platform Paths

Windows Docker Desktop and Ubuntu VPS use same image, internal ports, relative
routes, UID, probes, stop signal, and 30-second grace period. Docker Desktop
publishes host port to container 8080 for local use and mounts module data through
Docker-managed volumes; no Windows host path is embedded in image. Ubuntu VPS
binds container gateway to loopback behind host nginx TLS termination. VPS
systemd starts and stops container only; it does not supervise module processes.

## Consequences

- Module start commands must accept selected host, port, data directory, and
  graceful-stop configuration before unified deployment can become ready.
- Missing module probes are implementation blockers, not reasons to weaken
  aggregation policy.
- Gateway route configuration must preserve relative browser URLs and explicit
  route precedence, especially Dashboard fallback routes.
- Runtime patch releases and image digests require normal dependency update and
  verification; this ADR selects compatible runtime lines, not immutable image
  digests.
- Clinical release status remains blocked and unchanged.

## Verification

Run `python3 -m unittest tests/test_runtime_policy.py`. Test validates ADR schema
and relative links, then rejects public module ports, duplicate ports, root
execution, missing health entries, non-loopback module binds, duplicate data
directories, and absolute browser service URLs.

## Rollback

Before unified deployment ships, rollback is deletion or supersession of this
ADR and policy. After deployment ships, write superseding ADR, update policy and
gateway/supervisor configuration together, then verify clean shutdown and all
module probes before replacing image.
