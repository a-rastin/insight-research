# ADR-0010: Treatment Plan Lifecycle Prototype Retirement

- Status: Accepted
- Date: 2026-07-31
- Decision owners: INS-054 engineering walkthrough; independent psychiatrist
  review remains pending under INS-057
- Scope: INS-054
- Evidence reference: `INS-054-WALKTHROUGH-2026-07-31`

## Context

The disposable TP-04 lifecycle prototype represented incomplete-input blocking,
structured psychiatrist edits, high-severity DDI override, immutable
finalization, and follow-up supersession. INS-054 requires a controlled
synthetic walkthrough, recorded feedback and evidence, bounded follow-up issues,
and prototype retirement only after production tests retain those behaviors.

The Treatment Plan repository had no `prototype/` directory at the start of
INS-054 and no production or test import of a prototype package. Retirement is
therefore recorded as verification of the existing repository state; this
packet did not delete an unverified implementation. Generated `graphify-out/`
references to historical files are not runtime sources and were not modified.

## Controlled Walkthrough

The walkthrough used synthetic identifiers, medications, findings, and source
versions. It did not use patient data or claim clinical validation. The
psychiatrist role was exercised by the production domain and HTTP/UI test seams;
no human psychiatrist participated, so clinical and human-factors feedback is
explicitly pending.

| Case | Psychiatrist-role step | Observed production behavior | Evidence |
| --- | --- | --- | --- |
| `PW-01` | Request a plan with a required input missing | The run ends as `inputs-incomplete`, reports `required-fact-missing`, and does not call BN, synthesis, DDI, or persistence stages. | `tests/test_tp50_recommendation_runs.py::RecommendationWorkflowTests.test_blocked_inputs_are_explicit_and_skip_model_generation` |
| `PW-02` | Review and edit a generated plan | The immutable recommendation remains visible, each accepted edit records actor, session, before/after values and time, and urgent findings remain visible in the React workspace. | `tests/test_tp15_edit_ledger.py::EditLedgerTests.test_full_plan_is_reconstructed_without_altering_primary_plan`; `frontend/src/review-screen.test.tsx` |
| `PW-03` | Override a high-severity DDI | Finalization rejects a mismatched or unattributed rationale and accepts only the exact actor-bound reviewed rationale. | `tests/test_tp17_finalization_versioning.py::TP17FinalizationVersioningTests.test_high_severity_override_requires_exact_attributable_reason` |
| `PW-04` | Attest and finalize the reviewed plan | The server repeats DDI checking, binds the fresh result, persists a content hash, and rejects later edits to the Final Plan. | `tests/test_tp16_finalization.py::TP16FinalizationTests.test_finalize_rechecks_and_persists_fresh_hash_then_freezes_edits` |
| `PW-05` | Start follow-up from a prior Final Plan | Fresh snapshots produce explained changed/unchanged sections and a successor workflow while the prior Final Plan remains byte-for-byte unchanged. | `tests/test_tp18_supersession.py::TP18SupersessionTests.test_changed_and_unchanged_sections_are_explained_and_prior_is_immutable`; `frontend/src/review-screen.test.tsx` |

Executed evidence:

```text
python3 -B -m unittest \
  tests.test_tp50_recommendation_runs.RecommendationWorkflowTests.test_blocked_inputs_are_explicit_and_skip_model_generation \
  tests.test_tp15_edit_ledger.EditLedgerTests.test_full_plan_is_reconstructed_without_altering_primary_plan \
  tests.test_tp17_finalization_versioning.TP17FinalizationVersioningTests.test_high_severity_override_requires_exact_attributable_reason \
  tests.test_tp16_finalization.TP16FinalizationTests.test_finalize_rechecks_and_persists_fresh_hash_then_freezes_edits \
  tests.test_tp18_supersession.TP18SupersessionTests.test_changed_and_unchanged_sections_are_explained_and_prior_is_immutable -v

Result: 5 tests passed.

npm test -- --run src/review-screen.test.tsx

Result: 1 test passed.
```

## Feedback And Findings

- The production backend retains every safety-relevant behavior represented by
  the disposable lifecycle prototype. No runtime fallback to the prototype is
  needed.
- The React review workspace supports authenticated plan review, structured
  edits, persistent urgent findings, and successor creation, but exposes no
  finalization or attestation action. INS-055 owns that bounded UI gap.
- The repository has no composed authenticated gateway test that starts with a
  Recommendation Run and completes edit, finalization, and supersession through
  real HTTP module boundaries. INS-056 owns that integration gap.
- No independent psychiatrist observed this run, and the clinical-validation
  case and approval records remain pending. INS-057 owns controlled human
  walkthrough authorship, observations, findings, and sign-off. Until then,
  this evidence is software verification only.

## Decision

The disposable lifecycle prototype is retired. Production Treatment Plan code
and tests are the sole implementation and verification path for retained
lifecycle behavior. A prototype package must not be restored or imported into
production.

This decision does not approve clinical deployment. INS-055 through INS-057,
existing knowledge/model governance gates, and release composition remain
separate fail-closed requirements.

## Consequences

- Historical prototype behavior is traceable to named production tests.
- The absence of `prototype/` is intentional rather than an undocumented loss.
- Human feedback is not fabricated or conflated with automated evidence.
- Each walkthrough finding has one bounded follow-up packet.

## Rollback

Do not restore the disposable prototype as a rollback. Revert this ADR and its
follow-up issue records if the evidence mapping is invalid; repair the owning
production behavior and tests directly.
