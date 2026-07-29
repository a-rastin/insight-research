# ADR-0008: Treatment Plan Breadth and Safety Gates

- Status: Accepted
- Date: 2026-07-29
- Decision owners: Task-level psychiatrist and product approval; accountable names unresolved
- Scope: INS-010

## Context

Treatment Plan needs bounded sections and deterministic behavior for scheduling,
emergencies, uncertainty, allergies, contraindications, suicide risk, and severe
drug interactions. Repository contracts do not assign appointment, availability,
or timezone ownership and do not define an emergency-services integration or an
approved non-pharmacological intervention taxonomy. Missing contracts cannot be
replaced by inferred capability.

This decision follows the [project overview](../project-overview.md), the
[INS-010 specification](../feature-specs/10-emergency.md), the existing
[scope decision](0006-treatment-plan-scope-gates.md), and the
[AI workflow rules](../ai-workflow-rules.md). Normative controls live in
[treatment-plan-safety-policy-v1.json](../../contracts/treatment-plan-safety-policy-v1.json),
validated by
[treatment-plan-safety-policy-v1.schema.json](../../contracts/treatment-plan-safety-policy-v1.schema.json)
and checked by
[test_treatment_plan_safety_policy.py](../../tests/test_treatment_plan_safety_policy.py).

## Decision

System-generated plans contain only treatment-setting, pharmacotherapy, and
follow-up sections, each requiring approved source evidence. System-generated
and structured finalized non-pharmacological recommendations remain unsupported
until an approved taxonomy, evidence contract, and owning workflow exist.

Treatment Plan does not own appointments, availability, or timezones. No owner
is assigned by current architecture, so calendar lookup, booking, and exact
date/time recommendations remain unavailable. Source-backed relative follow-up
intervals may appear as clinical recommendations, but they are not appointments.

Emergency states stop routine recommendation generation and plan finalization.
The persistent result directs the psychiatrist to the applicable local emergency
protocol for immediate clinical evaluation. It does not contact, dispatch, book,
or claim availability of emergency services and cannot be overridden.

Missing, unknown, unavailable, stale, conflicting, or invalid clinically required
inputs block processing with distinct reasons and resolution actions. Optional
uncertainty remains visible and qualifies output. It is never silently defaulted.

Allergy, absolute contraindication, unresolved medication identity, unavailable
DDI coverage, required-data uncertainty, and urgent suicide-risk gates are hard
blockers. A high-severity DDI is an overridable blocker only. Override requires
an authenticated psychiatrist, a 20-2000 character rationale, actor UUID, UTC
timestamp, preserved original finding, plan provenance, repeated server-side
safety validation, and final attestation. Other hard blockers remain effective.

## Alternatives

| Alternative | Reason rejected |
| --- | --- |
| Let Treatment Plan book appointments | No appointment, availability, or timezone owner contract exists. |
| Show location-specific emergency contacts | No location or emergency-services integration contract exists. |
| Generate broad non-pharmacological advice | No approved taxonomy, evidence mapping, or owning workflow exists. |
| Permit overrides for allergy or absolute contraindication | Would weaken deterministic safety precedence without approved policy evidence. |
| Treat unknown suicide risk as low risk | Would convert missing safety data into a favorable finding. |

## Consequences

- DG-04, DG-05, and DG-06 have explicit, testable fail-closed policy decisions.
- Scheduling and non-pharmacological generation remain visibly unavailable.
- Emergency output cannot imply unimplemented integration.
- Scope gates from INS-008 still block every Treatment Plan generation because no
  supported population is approved.
- No module runtime, API, persistence, UI, clinical source, or model changes in
  this packet. Clinical deployment remains blocked.

## Verification

Run `python3 -B -m unittest tests/test_treatment_plan_safety_policy.py -v`.
Tests validate both policy and scope contracts, decision-table distinctions,
emergency behavior, uncertainty paths, and high-severity DDI override controls.

## Rollback

No runtime capability or clinical data exists to roll back. Revert this decision
packet, or supersede ADR, policy, schema, and tests together. Missing or partial
replacement policy remains fail-closed.
