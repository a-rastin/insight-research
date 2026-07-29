# ADR-0004: Administration and Operations Ownership

- Status: Accepted
- Date: 2026-07-29
- Decision owners: Task-level architecture, security, and operations approval; accountable names unresolved
- Scope: INS-005

## Context

INSIGHT needs administrative navigation, audit and provenance access, operational
logs, backup, restore, and retention without turning Dashboard into a second
domain owner or allowing one module to write another module's database. Backup
metadata must support aggregate recovery while filenames and manifests remain
free of PHI.

This decision follows the [architecture invariants](../architecture.md), the
[INS-005 specification](../feature-specs/05-administration-ownership.md), and
[ADR-0002](0002-internal-service-authentication.md). Normative ownership,
permissions, manifest fields, and examples live in
[administration-operations-v1.json](../../contracts/administration-operations-v1.json)
and are checked by
[test_administration_operations.py](../../tests/test_administration_operations.py).

## Decision

Dashboard owns navigation only. It resolves an approved module route and sends
the user to the owner; it does not proxy, copy, aggregate, or persist account,
audit, provenance, log, backup, restore, or retention data.

Authentication owns account administration and security-audit records. Each
clinical module owns and serves its clinical provenance. Each emitting module
owns its redacted operational logs. Security audit, clinical provenance, and
operational logs remain separate datasets and stores. An administrator may
manage accounts and inspect security audit and operational logs. A psychiatrist
may read clinical provenance only through the owning module's patient- and
encounter-scoped authorization. Administrative role alone grants no clinical
provenance access, and psychiatrist role grants no account, security-log,
operational-log, backup, restore, or retention administration access.

Deployment operations owns orchestration and aggregate backup manifests, not
module data or module backup contents. An authenticated administrator may
initiate an operation, but every orchestration call also requires the operations
service identity and its exact module capability under ADR-0002. Each module
creates a module-local backup through its own adapter and returns an opaque
artifact reference plus metadata. Aggregate manifests contain module ID, module
version, data-schema version, backup-format version, creation time, artifact
name, byte count, and SHA-256 digest. Artifact names use random UUIDs and
controlled module IDs only; patient, user, encounter, clinical, path, database,
or timestamp-derived values are forbidden.

Each module owns its restore implementation. Operations may submit only that
module's opaque artifact to that module's restore boundary. The module rejects a
manifest entry whose module ID does not equal its configured identity, validates
versions and digest, restores into isolated staging storage, runs module-owned
integrity and migration checks, and atomically activates only after verification.
Operations records metadata-only results in an aggregate restore report. It
never opens, attaches, queries, or writes a module database or private data
directory. A failed module restore does not redirect its artifact into another
module or report aggregate success.

Each data owner enforces retention and deletion for its records and module
backup artifacts under an approved policy. Deployment operations enforces
retention only for aggregate manifests and restore reports. Retention never
silently deletes immutable final plans, required clinical provenance, or
security audit records; policy definitions and accountable approvals remain a
separate release gate.

## Alternatives

| Alternative | Reason rejected |
| --- | --- |
| Dashboard owns administrative data and backups | Duplicates owner data and turns navigation into a privileged persistence boundary. |
| One shared backup process reads every database | Breaks module credentials, storage isolation, and independent restore validation. |
| Operations restores databases directly | Allows cross-module writes and bypasses module schema and integrity checks. |
| Put patient or timestamp labels in artifact names | Leaks PHI or operational detail and creates unstable identifiers. |
| Merge audit, provenance, and operational logs | Mixes distinct access, retention, privacy, and evidentiary purposes. |

## Consequences

- Authentication and each module need protected, versioned administration,
  export, restore, verification, and retention interfaces in later work packets.
- Deployment tooling needs an operations service identity, least-privilege
  module capabilities, protected artifact storage, and metadata-only aggregate
  manifest/report persistence.
- Dashboard needs role-filtered owner-route discovery but no new domain tables.
- Concrete retention periods, encryption/key management, storage provider,
  recovery objectives, and named accountable owners remain unresolved release
  gates. Clinical release stays blocked.

## Verification

Run `python3 -B -m unittest tests/test_administration_operations.py`. Tests check
the ADR structure, ownership and permission matrix, separation of logs and
provenance, PHI-safe manifest schema, and module-bound restore isolation.

## Rollback

Before runtime rollout, supersede this ADR and contract together. After rollout,
disable new operations, preserve existing artifacts and manifests under their
original retention and encryption controls, and migrate through owner-provided
export/import contracts. Never roll back to shared database access or a
cross-module restore writer.
