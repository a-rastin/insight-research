# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- **In progress — mixed system phase.** The Treatment Plan documentation places that module after TP-19 and at the start of clinical-validation/deployment-readiness work, while several upstream modules still require dependency hardening and contract unification.
- **Not production-ready or clinically released.** The Treatment Plan release gate is explicitly blocked; the supplied Bayesian Networks are research/qualitative artifacts with placeholder, neutral, or otherwise uncalibrated probability tables; and Severity, Medical History, and DDI retain prototype persistence or security constraints.
- **Evidence boundary:** this archive contains documentation, handoffs, schemas, guideline extracts, diagrams, and BN model artifacts, but not the implementation source trees referenced by the module handoffs. Therefore, implementation milestones below are marked as **documented as implemented** rather than independently source-verified in this archive.

## Current Goal

- Integrate the independently runnable INSIGHT modules through versioned internal REST APIs into an explainable, psychiatrist-controlled Treatment Plan workflow.
- Preserve canonical Patient and Encounter identity, central Authentication trust, immutable clinical snapshots/final plans, deterministic safety gates, complete provenance, and strict module data ownership.
- **Immediate goal:** connect the Treatment Plan React review workspace to its authenticated backend APIs and wire the remaining recommendation-run and supersession workflow routes.

## Completed

### Directly present and verified in this archive

- System-level product requirements, modular architecture constraints, domain terminology, Treatment Plan context definitions, context ownership rules, UI design guidance, and a dependency-ordered unification plan are documented.
- Thirteen BN model XML files and the supplied BIF 0.3 XSD are present. All thirteen model XML files are well-formed and validate against the supplied XSD.
- Seventeen Hugin-style `.net` files are present, representing eleven unique files after duplicate copies are removed. Their brace and parenthesis structures are balanced.
- BN documentation/model packages cover pharmacotherapy, treatment setting, involuntary treatment, clozapine for suicide risk, clozapine for treatment resistance, clozapine for aggression, long-acting injectables, maintenance treatment, continuing the same antipsychotic, acute dystonia, parkinsonism, akathisia, and VMAT2 treatment for tardive dyskinesia.
- Mermaid diagrams, guideline source extracts, BN specifications, rationale labels, contraindication gates, and implementation cautions are documented for the available model packages.
- The BN Manager contract identifies four canonical XML registry models: Pharmacotherapy, Treatment Setting, Involuntary Treatment Considerations, and Clozapine in Suicide Risk.

### Documented as implemented, but not independently source-verified in this archive

- **Authentication:** standalone FastAPI/SQLite service with bcrypt password hashing, server-side sessions, signed cookies, CSRF protection, disclaimer gating, account lifecycle operations, failed-login controls, migrations, audit logging, health/readiness endpoints, and tests.
- **Dashboard:** FastAPI/SQLite workspace router with Authentication REST verification, role-scoped workspace buttons, local session/event persistence, route discovery, health/readiness checks, and passing documented tests. The handoff states that the FastAPI rewrite remained uncommitted and out of sync with the remote repository at the time of review.
- **Add New Patient:** standalone FastAPI/SQLite intake module with REST-only browser integration, canonical server-generated patient UUIDs, patient-code aliases, intake retrieval, Authentication/CSRF seams, validation, and tests.
- **Diagnosis:** standalone FastAPI/SQLite schizophrenia criteria module with clinician-confirmed or clinician-bypassed decisions, Authentication/CSRF controls, canonical-patient lookup seam, readiness/discovery endpoints, audit snapshots, embeddable UI, and tests.
- **Severity:** standalone Node/Express PANSS module with browser UI, GET/PUT endpoints, JSON-file persistence, client-side scoring, and a runnable integration self-check.
- **Medical History:** standalone Node module with activation codes, conditional clinical fields, server-side validation, JSON-file persistence, internal REST endpoints, schema documentation, and integration tests.
- **DDI Checker:** standalone browser/JavaScript interaction engine with deterministic pairwise checking, knowledge-base ingestion and validation, fail-closed medication identity resolution, admin review workflow, local revision handling, and browser-local audit state.
- **BN Manager:** standalone FastAPI service for XSD validation, registry discovery, model validation, protected evaluation routes, posterior evaluation, Authentication/CSRF enforcement, and tests for the four canonical registry models.
- **Treatment Plan TP-01 through TP-19:** governance, contracts, FastAPI/React scaffold, Authentication integration, clinical-context assembly, eligibility policy, BN orchestration, deterministic safety policy, primary-plan synthesis, DDI checking, psychiatrist review UI, append-only edits, finalization, follow-up supersession, SQLite/PostgreSQL persistence, backup/restore, and approval-gated retention are documented as implemented.

## In Progress

- Connect the Treatment Plan React workspace, which currently uses synthetic data, to authenticated plan-read, edit-ledger, DDI recheck, and finalization APIs.
- Wire the remaining Treatment Plan workflow endpoints, including recommendation-run creation/status and the public supersession route.
- Reconcile module-specific Authentication response assumptions into one versioned session contract.
- Standardize health, readiness, contract discovery, schemas/OpenAPI, error envelopes, UUIDs, timestamps, request correlation, ETags, and idempotency across modules.
- Migrate all clinical records to canonical Patient UUID and Encounter UUID ownership while retaining patient codes only as aliases/compatibility inputs.
- Replace prototype JSON/localStorage clinical persistence and browser-owned administrative state in Severity, Medical History, and DDI with authenticated, auditable, concurrency-safe server persistence.
- Add a standalone DDI server REST boundary and make a single tested interaction engine authoritative for browser, ingestion, and server use.
- Complete BN evidence schemas, evaluation provenance, model version/hash reporting, CPT calibration, expert review, and signed model governance.
- Build clinician-authored validation cases, failure-injection cases, override workflows, hazard traceability, human-factors testing, and the independent clinical safety case.
- Package and verify the modules independently and within the unified non-root Docker image for Windows Docker Desktop and Ubuntu/nginx/systemd deployment.
- Commit and push the documented Dashboard FastAPI rewrite so repository history matches the handoff documentation.

## Next Up

1. **Connect the Treatment Plan frontend to the authenticated backend APIs.** This is the explicit highest-priority next unit in the Treatment Plan handoff.
2. Implement and test the remaining recommendation-run and supersession routes against the existing Treatment Plan seams.
3. Create the standalone DDI REST service because the current browser/localStorage design is the largest documented blocker to reliable Treatment Plan integration.
4. Publish and adopt the common Authentication, Patient/Encounter identity, schema-versioning, error, readiness, provenance, and idempotency contracts.
5. Run the psychiatrist lifecycle walkthrough, record findings, retire the disposable prototype after the walkthrough, and begin TP-21 clinical validation.
6. Complete TP-22 unified packaging, security scanning, migration/recovery tests, TLS/security-header checks, and rollback verification only after clinical-validation prerequisites are satisfied.

## Open Questions

- Where are the current source repositories or source-code snapshots for each module? They are required to verify the implementation and test claims made by the handoff documents.
- Which exact Authentication v1 session payload is canonical during the compatibility period, and when will legacy role/field aliases be removed?
- Which module owns longitudinal current medications and allergies, versus encounter-specific intake snapshots?
- How will conflicting suicide-risk observations from Add New Patient, Medical History, and dedicated risk assessment be resolved without silently selecting one source?
- Which BN models and clinical pathways are in the intended first release scope, and who is the accountable clinical/model owner for each one?
- What calibration dataset, expert-elicitation method, acceptance thresholds, subgroup checks, and prospective monitoring plan will be used for each BN?
- Which stakeholder roles must approve the TP-01 release gate, and where will controlled evidence of those approvals be stored?
- What is the final policy for involuntary-treatment logic across different jurisdictions and changing local law?
- Which LLM provider/model will power the optional assistant, and what validated de-identification, retention, access, and failure policies will govern it?
- What content, format, clinical ownership, and review process are required for the currently unspecified patient-education PDF report?
- What production encryption-at-rest/key-management design will be used for module databases and backups?

## Architecture Decisions

- INSIGHT is a multi-module system. Every module remains independently runnable and testable; modules communicate only through internal REST APIs and are not merged into one application codebase.
- A unified Docker image may contain multiple module processes, but each module retains its own process, base path/port, configuration, migrations, health/readiness endpoints, and data store.
- Authentication is the only identity/session authority. Downstream modules call the Authentication session endpoint and do not decode tokens or read the Authentication database.
- Patient UUID is canonical identity; patient code is a human-friendly alias. Clinical assessments and plans must also reference a canonical Encounter UUID.
- Each module owns its own data and migration history. Cross-module database queries, shared mutable clinical files, and browser storage as an integration channel are prohibited.
- Clinical input snapshots, recommendation runs, edits, findings, evidence, and final plans are versioned and attributable. Final plans are immutable; later plans supersede rather than mutate prior plans.
- The psychiatrist remains the final clinical authority. BN results are advisory evidence, not autonomous prescriptions or signed diagnoses.
- Deterministic safety rules, missing/conflicting/unresolved-data policies, and emergency gates take precedence over probabilistic recommendations.
- SQLite is the standalone/default persistence option; PostgreSQL is the production upgrade path. Production persistence must add concurrency safety, encryption/key management, backup/restore, retention, and auditable migrations.
- Every exchanged or persisted dataset requires a published versioned schema and provenance identifying the exact source, policy, model, and knowledge-base versions.
- BN Manager v2 treats BIF 0.3 XML as its canonical model format. Legacy `.net` topic artifacts require controlled migration and semantic validation before registry adoption.
- DDI resolution is fail-closed: unknown or ambiguous medication identity means interaction coverage is incomplete, never “no interaction.”
- Security audit events and clinical provenance are separate records with different purposes and retention controls.

## Session Notes

- The archive was successfully extracted and all **97 files** were inventoried and analyzed: 53 Markdown, 17 `.net`, 14 XML, 8 Mermaid, 4 text, and 1 PNG file.
- Duplicate analysis found **16 duplicate-content groups covering 33 files**. Most duplicates intentionally mirror BN artifacts between the central `BNs/` area and module-specific folders; the same design document is also copied at root and into two modules.
- All textual files decoded as UTF-8 without replacement-character corruption. All XML files are well-formed; all 13 BN model XML files validate against the supplied XSD.
- Structural checks found no unbalanced braces or parentheses in any `.net` file.
- The Akathisia PNG is a small BN diagram showing Alcohol, Sleep Apnea, Opioid, and Age influencing a benzodiazepine option, with Low BP and High-Risk Antipsychotic also contributing to the final Interventions node.
- Semantic CPT cardinality review identified generated XML tables that require correction or an explicit compiler rule before use:
  - LAI `UtilizationIndication`: 72 values supplied where 144 are implied by the declared parent/state cardinalities.
  - Continuing Medications `medication_adjustment_priority`: 135 values supplied where 405 are implied.
  - Clozapine TRS: three tables have value counts smaller than their declared cardinalities (`TreatmentResistanceStatus`, `ClozapineImplementationMode`, and `ManagementRecommendation`).
- The compact single-row CPTs in the canonical Treatment Setting and Involuntary Treatment XML models are explicitly documented as compiler-broadcast qualitative placeholders; dimensional loading does not constitute clinical validation.
- The archive contains no executable module source directories, dependency files, tests, Dockerfiles, migrations, or databases described by the handoffs. A repository/source snapshot is needed before marking those implementation claims as independently verified.
- Preserve the template sections and update this tracker after each meaningful implementation, integration, validation, governance, or release-gate change.
