# ADR-0007: Knowledge Authority Gates

- Status: Accepted
- Date: 2026-07-29
- Decision owners: Task-level approval; accountable clinical, pharmacy, terminology, and product owners unresolved
- Scope: INS-009

## Context

INSIGHT needs approved authorities for formularies, medication dosing,
contraindications, monitoring, diagnosis terminology, and medication
terminology. It also needs a review cadence that prevents stale knowledge from
remaining active. Current normative materials identify these needs but provide
no jurisdiction, licensed source, source version, approval record, or update
cadence. Repository artifacts and prototype behavior cannot become clinical
authority by implication.

This decision follows the [project overview](../project-overview.md), the
[INS-009 specification](../feature-specs/09-knowledge-authority.md), and the
[AI workflow rules](../ai-workflow-rules.md). Normative controls live in
[knowledge-source-manifest-v1.json](../../contracts/knowledge-source-manifest-v1.json),
validated by
[knowledge-source-manifest-v1.schema.json](../../contracts/knowledge-source-manifest-v1.schema.json)
and checked by
[test_knowledge_source_manifest.py](../../tests/test_knowledge_source_manifest.py).

## Decision

All six knowledge domains remain unresolved. No formulary, medication dose,
contraindication, monitoring source, diagnosis terminology, or medication
terminology is approved for clinical use. No source name, jurisdiction,
license, version, or approval is inferred from existing code, model assets, or
prototype data.

Update cadence also remains unresolved. Activation requires an attributable
domain owner and clinical approver, a named and licensed source, exact source
and terminology versions where applicable, jurisdiction, review cadence, last
review time, and next review deadline. Missing or expired metadata blocks the
affected clinical use. Source withdrawal, safety notice, license change, or
version retirement suspends use pending review.

Blocked use returns `knowledge-authority-blocked` with code
`KNOWLEDGE_AUTHORITY_UNRESOLVED`, names every failed domain, preserves original
clinician-entered values, displays uncertainty, and produces no authoritative
normalization, dose, contraindication, monitoring, formulary, or terminology
claim. Missing authority cannot be represented as no contraindication, normal
monitoring, valid dose, formulary availability, or resolved terminology.

## Alternatives

| Alternative | Reason rejected |
| --- | --- |
| Select common external terminologies by convention | No jurisdiction, license, version, accountable owner, or approval was supplied. |
| Treat bundled medication data as authoritative | Prototype assets do not establish dose, formulary, contraindication, monitoring, or terminology authority. |
| Permit research output with an unversioned source | Results would not be reproducible and stale knowledge could appear current. |
| Set an arbitrary annual review | Cadence is a clinical governance decision and cannot be invented. |

## Consequences

- Affected clinical use and release remain blocked until all required source and
  cadence metadata receives attributable approval.
- Clinician-entered text remains visible but cannot silently become a canonical
  diagnosis or medication concept.
- No module API, runtime, persistence, UI, clinical source, terminology asset,
  or model artifact changes in this packet.
- A superseding manifest and decision must identify exact approved sources,
  versions, licenses, jurisdiction, owners, cadence, and migration behavior.

## Verification

Run `python3 -B -m unittest tests/test_knowledge_source_manifest.py -v`.
Tests validate the manifest against its Draft 2020-12 schema, require all six
domains, reject incomplete approval metadata, and verify fail-closed behavior
for unresolved authority and cadence.

## Rollback

No runtime capability or clinical data exists to roll back. Revert this
decision packet, or supersede the ADR, manifest, schema, and tests together.
Missing or partial replacement policy remains fail-closed.
