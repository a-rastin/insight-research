# ADR-0006: Treatment Plan Scope Gates

- Status: Accepted
- Date: 2026-07-29
- Decision owners: Task-level psychiatrist and product approval; accountable names unresolved
- Scope: INS-008

## Context

Treatment Plan generation needs explicit intended-use, diagnosis, and population
gates. INSIGHT is psychiatrist-facing schizophrenia decision support, not an
autonomous diagnosis or prescribing system. Current sources do not establish an
approved patient population boundary or exclusions based on age or other
demographics. Missing scope evidence cannot be interpreted as eligibility.

This decision follows the [project overview](../project-overview.md), the
[INS-008 specification](../feature-specs/08-jurisdiction.md), and the
[AI workflow rules](../ai-workflow-rules.md). Normative controls live in
[scope-matrix-v1.json](../../contracts/scope-matrix-v1.json), validated by
[scope-matrix.schema.json](../../contracts/scope-matrix.schema.json) and checked
by [test_scope_matrix.py](../../tests/test_scope_matrix.py).

## Decision

INSIGHT remains research-only. Clinical deployment, autonomous diagnosis,
prescribing, ordering, and replacement of psychiatrist judgment are prohibited.
A supported diagnosis pathway requires an explicit psychiatrist-confirmed
schizophrenia decision. Excluded, other, and unknown diagnosis states block
Treatment Plan generation and remain visible as distinct reasons.

No patient population is approved. The supported-population list is empty until
psychiatrist and product owners provide attributable evidence and exclusions.
Known-excluded and unknown population states both block generation, with
different observable reasons. The system must not infer population eligibility
from diagnosis, care setting, demographics, or missing data.

Blocked cases return the stable state `scope-blocked`, code
`TP_SCOPE_UNSUPPORTED`, gate-specific reasons, and the action needed to resolve
each reason. A blocked result produces no recommendation run or Primary
Treatment Plan. Status is communicated with text and code, not color alone.

## Alternatives

| Alternative | Reason rejected |
| --- | --- |
| Infer an adult population | No approved age boundary or supporting evidence exists. |
| Treat missing population as supported | Would silently convert unknown data into favorable eligibility. |
| Accept any schizophrenia-like diagnosis | Bypasses explicit psychiatrist confirmation and broadens intended use. |
| Generate a qualified plan for unsupported cases | A limitation banner cannot replace a required scope gate. |

## Consequences

- All Treatment Plan generation remains blocked until a supported population is
  approved and represented in a superseding scope matrix.
- Diagnosis and population failures are independently observable and testable.
- No module API, runtime, persisted entity, or clinical model changes in this
  decision packet.
- Clinical release status remains blocked and unchanged.

## Verification

Run `python3 -B -m unittest tests/test_scope_matrix.py -v`. Tests check the
versioned schema contract, research-only status, clinician-confirmed diagnosis
gate, empty population allowlist, blocked-case response, and negative diagnosis
and population fixtures.

## Rollback

No runtime capability or data exists to roll back. Revert this decision packet,
or supersede the ADR, matrix, schema, fixtures, and tests together. Missing or
partial replacement policy remains fail-closed.
