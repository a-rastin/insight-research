# ADR-0011: Read-only Treatment Plan Assistant

- Status: Accepted
- Date: 2026-07-31
- Decision owners: Task-level product, privacy, and security approval; accountable names unresolved
- Scope: INS-055

## Context

INS-006 disabled the assistant because no bounded page, provider boundary, data
projection, access policy, or retention policy was approved. INS-055 now approves
one read-only slice on the Treatment Plan review page. The assistant remains
optional decision support and cannot participate in clinical writes or
finalization.

This decision follows the [architecture invariants](../architecture.md), the
[INS-055 specification](../feature-specs/55-read-only.md), and the
[AI workflow rules](../ai-workflow-rules.md). Normative controls live in
[assistant-policy-v1.json](../../contracts/assistant-policy-v1.json).

## Decision

Permit psychiatrist-only advisory requests from the Treatment Plan review page.
The Treatment Plan server loads the current plan and constructs a default-deny
projection containing only supported plan content, safety-finding descriptors,
and rationale. Plan, patient, encounter, run, finding, actor, and source
identifiers, timestamps, edits, and provenance are omitted structurally before a
defense-in-depth scrub is applied to every transmitted string.

The deployment-configured provider receives a fixed advisory instruction, the
scrubbed prompt, the scrubbed projection, an empty tool list, and an explicit
no-retention/no-training policy. No application tool or mutation capability is
available. Prompts and responses are not persisted, backed up, or added to
clinical provenance. Provider output is scrubbed again before display.

The UI is a bounded rail labelled as advisory. Missing configuration, timeout,
malformed response, or provider failure produces an unavailable state and cannot
block or alter plan reading, editing, safety review, supersession, or finalization.

## Alternatives

| Alternative | Reason rejected |
| --- | --- |
| Send the complete plan view | It contains identifiers, timestamps, edits, and provenance outside the approved purpose. |
| Project context in the browser | It would make privacy enforcement dependent on untrusted client code. |
| Add read-only retrieval tools | The approved page context is sufficient and tools expand the provider trust boundary. |
| Persist a conversation thread | No retention purpose or deletion workflow is approved. |

## Consequences

- The prior INS-006 disabled decision is superseded only for this bounded page.
- Provider enablement remains deployment configuration and fails closed when
  absent or invalid.
- The assistant cannot establish a clinical fact, mutate a record, or replace
  psychiatrist review.
- Controlled clinical release approval remains unchanged.

## Verification

Run the assistant policy, Treatment Plan assistant, contract, security, and UI
tests. They verify allowlisted projection, identifier scrubbing, captured provider
payloads, role enforcement, no retention or tools, advisory labelling, and
non-blocking provider-failure behavior.

## Rollback

Remove provider configuration and the route resolves to unavailable without data
migration because no assistant conversation is stored. Restoring the disabled
policy requires reverting this ADR, contract, route, and UI together.
