# INSIGHT Application

## Phase 4 - Treatment Plan Workflow Completion

### INS-055 - Connect Finalization And Attestation UI

- **Finding:** `INS-054-WALKTHROUGH-2026-07-31` found that the React review
  workspace cannot invoke the existing authenticated finalization route.
- **Build:** Add an explicit psychiatrist attestation and finalization action to
  the Treatment Plan React workspace. Submit the current strong ETag, CSRF token,
  idempotency key, and attestation to the existing canonical route; preserve
  open findings and server rejection text; display the immutable returned Final
  Plan without permitting later edits.
- **Boundaries:** Do not change finalization policy, backend route semantics,
  plan schemas, override rules, or clinical content. Do not preselect or infer
  attestation.
- **Acceptance:** Frontend tests cover success, stale ETag, missing CSRF or ETag,
  safety rejection, idempotent replay, persistent urgent findings, keyboard
  operation, and edit lockout after finalization.
