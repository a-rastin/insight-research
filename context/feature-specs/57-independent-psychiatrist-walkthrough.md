# INSIGHT Application

## Phase 4 - Treatment Plan Workflow Completion

### INS-057 - Execute Independent Psychiatrist Walkthrough

- **Finding:** `INS-054-WALKTHROUGH-2026-07-31` is automated software evidence;
  no independent psychiatrist participated and no human-factors feedback was
  collected.
- **Build:** Have an independent psychiatrist author or approve the controlled
  synthetic cases, execute the review lifecycle, and record attributable
  observations against the existing clinical-validation protocol. Triage every
  unsafe omission, unsafe commission, unresolved-data presentation issue, alert
  burden issue, use error, and override-workflow issue into a bounded owner and
  remediation packet.
- **Boundaries:** Use synthetic no-PHI cases only. Do not invent reviewer
  identity, approval, observations, thresholds, calibration outcomes, or clinical
  sign-off. Keep the independent psychiatrist and Clinical Safety Officer roles
  distinct.
- **Acceptance:** Versioned case, observation, hazard, report-hash, and approval
  evidence is complete; open hazards or missing approvals keep release blocked;
  the ADR references the controlled evidence location without embedding PHI.
