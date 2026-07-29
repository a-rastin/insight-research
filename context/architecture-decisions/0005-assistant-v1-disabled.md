# ADR-0005: Assistant v1 Disabled

- Status: Accepted
- Date: 2026-07-29
- Decision owners: Task-level privacy, security, and product approval; accountable names unresolved
- Scope: INS-006

## Context

INSIGHT describes a page-aware advisory assistant, but sending clinical context
to a model provider requires approved provider, retention, encryption, access,
deletion, backup, provider-use, context-allowlist, and tool-boundary policies.
None is approved. Patient names, codes, MRNs, contact details, and dates must
never reach a provider, and assistant availability must not affect clinical
workflows.

This decision follows the [architecture invariants](../architecture.md), the
[INS-006 specification](../feature-specs/06-assistant-provider.md), and the
[AI workflow rules](../ai-workflow-rules.md). Normative controls live in
[assistant-policy-v1.json](../../contracts/assistant-policy-v1.json) and are
checked by [test_assistant_policy.py](../../tests/test_assistant_policy.py).

## Decision

Reject assistant scope for v1 and keep it disabled. No model provider is
selected. No page context, prompt, conversation, patient data, or application
data may cross an assistant-provider boundary. No assistant conversation is
stored, backed up, restored, or exposed through an access role.

The page-context allowlist and tool list are empty. The assistant cannot create,
update, delete, submit, sign, approve, or finalize any record. Structural
identifier omission and defense-in-depth scrubbing remain mandatory admission
controls for any future proposal; names, patient codes, MRNs, contact details,
and dates are forbidden even in an otherwise approved context.

The UI exposes a non-interactive unavailable state and no prompt control.
Provider configuration, outage, or failure cannot block, delay, or alter any
clinical read, write, review, or finalization workflow. Unsupported or incomplete
policy always resolves to disabled.

## Alternatives

| Alternative | Reason rejected |
| --- | --- |
| Select a provider now | No provider security, privacy, retention, or use policy is approved. |
| Enable without conversation storage | Provider transmission and context policy remain unresolved. |
| Rely only on regex redaction | Structured fields must be omitted first; regex cannot establish safe disclosure alone. |
| Add read-only tools before provider approval | Creates an unnecessary application-data access boundary while scope is rejected. |
| Hide provider failures by retrying in clinical flows | Couples optional assistance to required clinical workflows. |

## Consequences

- V1 has no assistant provider integration, prompt endpoint, conversation store,
  assistant tool, or active chat UI.
- Clinical workflows remain independent of assistant configuration and failures.
- A future assistant requires a superseding approved decision covering every
  unresolved policy, plus redaction, schema, authorization, retention, failure,
  and disabled-state tests before enablement.
- Clinical release status remains blocked and unchanged.

## Verification

Run `python3 -B -m unittest tests/test_assistant_policy.py`. Tests check the
disabled provider and UI state, forbidden identifier corpus, empty context and
tool allowlists, mutation absence, no conversation retention or access, and
non-blocking failure policy.

## Rollback

No runtime capability or data exists to roll back. Supersede this ADR and
contract together before enabling an assistant. Do not reinterpret missing or
partial policy as approval.
