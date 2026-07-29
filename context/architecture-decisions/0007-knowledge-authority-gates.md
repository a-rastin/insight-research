# ADR-0007: Knowledge Authority Gates

- Status: Accepted
- Date: 2026-07-29
- Decision owners: Task-level product approval; accountable clinical and pharmacy sign-off remains a release gate
- Scope: INS-009

## Context

INSIGHT needs reproducible authorities for formularies, medication dosing,
contraindications, monitoring, diagnosis terminology, and medication
terminology. It also needs an update cadence that prevents stale knowledge from
remaining active. No deployment jurisdiction or institutional formulary was
supplied. INSIGHT remains research-only, so this packet selects a bounded US
research profile without claiming clinical-release approval.

This decision follows the [project overview](../project-overview.md), the
[INS-009 specification](../feature-specs/09-knowledge-authority.md), and the
[AI workflow rules](../ai-workflow-rules.md). Normative controls live in
[knowledge-source-manifest-v1.json](../../contracts/knowledge-source-manifest-v1.json),
validated by
[knowledge-source-manifest-v1.schema.json](../../contracts/knowledge-source-manifest-v1.schema.json)
and checked by
[test_knowledge_source_manifest.py](../../tests/test_knowledge_source_manifest.py).

## Decision

INS-009 uses a US research authority profile:

- INSIGHT makes no formulary, insurance coverage, reimbursement, stock, or local
  availability claim. FDA approval status is not a formulary.
- Per-product FDA-approved labeling indexed by Drugs@FDA governs medication
  dosing, contraindication, and monitoring claims. Every extracted claim must
  retain application number, submission number, labeling document date, source
  URL, retrieval time, and source-byte SHA-256.
- CDC/NCHS ICD-10-CM 2026 governs diagnosis terminology and codes. It does not
  establish the psychiatrist's diagnosis or replace INS-008 diagnosis gates.
- NLM RxNorm Current Prescribable Content Full Monthly Release dated July 6,
  2026 governs medication concepts and identifiers. Original clinician-entered
  text remains preserved, and ambiguous or unknown matches remain unresolved.

Drugs@FDA is checked every weekday, RxNorm weekly, and ICD-10-CM every 30 days.
The complete authority profile receives a 90-day governance review. A changed,
withdrawn, unavailable, hash-mismatched, or overdue source is not
auto-activated; affected output enters `knowledge-authority-blocked` pending
validation and clinical review. Prior results retain their pinned source
versions and hashes.

Selected sources are approved for bounded research implementation only.
Clinical deployment remains prohibited until named clinical and pharmacy owners
approve the profile and deployment jurisdiction, validation, licensing, and
release controls are complete.

## Alternatives

| Alternative | Reason rejected |
| --- | --- |
| Treat FDA approval as formulary status | Approval does not establish payer coverage, local availability, or institutional policy. |
| Use DSM terminology | Repository provides no licensed DSM terminology package or redistribution terms. |
| Use full licensed RxNorm/UMLS release | Current Prescribable Content supplies needed normalized drug concepts without adding a license-gated artifact. |
| Auto-activate upstream updates | Source publication does not replace ingestion validation and clinical review. |

## Consequences

- DG-02 and DG-08 have selected authorities, pinned baseline versions, and
  explicit update cadence for research implementation.
- Formulary-dependent behavior remains unavailable rather than guessed.
- FDA labeling is product-specific; absent label evidence blocks the affected
  claim and is not interpreted as no contraindication or no monitoring need.
- No module API, runtime, persistence, UI, clinical source, terminology asset,
  or model artifact changes in this packet.

## Verification

Run `python3 -B -m unittest tests/test_knowledge_source_manifest.py -v`.
Tests validate the manifest against its Draft 2020-12 schema, require all six
domains, verify source selections and cadence, and reject missing provenance or
unsafe formulary claims.

## Rollback

No runtime capability or clinical data exists to roll back. Revert this
decision packet, or supersede the ADR, manifest, schema, and tests together.
Missing or partial replacement policy remains fail-closed.
