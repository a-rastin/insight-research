# INSIGHT - A Clinical Decision Support System

## Overview

INSIGHT is a clinical decision support system for psychiatrists managing patients with schizophrenia. It is intended to combine structured patient and encounter records, clinician-confirmed schizophrenia diagnostic assessment, PANSS severity assessment, risk and medical-history data, deterministic safety rules, drug-drug interaction checking, and versioned Bayesian-network evaluations to produce an **explainable Primary Treatment Plan** for psychiatrist review. The system is designed to address fragmented clinical information, inconsistent provenance, and opaque recommendation logic by preserving the exact source data, policy versions, model versions, evidence, safety findings, and psychiatrist decisions used in each recommendation. INSIGHT does not diagnose, prescribe, or issue clinical orders autonomously; the psychiatrist remains the final clinical authority.

> **Current project boundary:** The supplied archive is an architectural and prototype baseline, not clinically releasable software. The Treatment Plan backend contains substantial lifecycle functionality, but its review UI still uses synthetic data and is not fully connected to the backend routes. Severity and Medical History retain prototype file-based persistence and require production authentication and audit integration. The DDI Checker currently lacks the required server-side REST service and stores operational state in the browser. Several bundled Bayesian networks use illustrative or qualitative conditional probability tables. Clinical use is blocked until the supported pathways, evidence mappings, safety policies, models, and release controls receive independent clinical, privacy, regulatory, and deployment approval.

## Goals

1. **Create a modular, interoperable clinical workflow:** Every INSIGHT module must run and test independently while exchanging versioned data only through REST APIs, using one canonical Patient UUID and Encounter UUID across the system and never querying another module's database.
2. **Generate reproducible and explainable decision support:** For every recommendation run, INSIGHT must preserve an immutable, schema-versioned clinical input snapshot and expose the patient facts, deterministic policies, DDI knowledge-base version, Bayesian model version, posterior results, limitations, and approved evidence metadata supporting the Primary Treatment Plan.
3. **Preserve psychiatrist authority and enforce safety throughout the plan lifecycle:** Psychiatrists must be able to accept or modify the system draft, with attributable edits, required rationale, concurrency protection, server-side safety and DDI revalidation, immutable finalized plans, and prospective supersession during follow-up rather than alteration of prior plans.

## Core User Flow

1. An administrator provisions and manages user accounts, system configuration, approved knowledge artifacts, logs, and backups; a psychiatrist signs in through the Authentication module.
2. The psychiatrist reviews the research-use and clinical-responsibility disclaimer before entering the clinical workspace.
3. The psychiatrist creates or locates a patient through the Add New Patient module. The system resolves the patient to one canonical Patient UUID; the human-readable patient code remains an alias only.
4. The psychiatrist opens a new dated Encounter for an initial assessment or follow-up visit.
5. The psychiatrist completes or reviews the relevant clinical inputs: clinician-controlled schizophrenia diagnosis, PANSS severity assessment, baseline and medical history, medication history, prior antipsychotic response and adherence, contraindications, and suicide/aggression risk information. The intended full workflow also includes a structured C-SSRS risk-assessment step.
6. The Treatment Plan module requests versioned snapshots from the owning modules through internal REST APIs and creates an immutable Clinical Input Snapshot for an idempotent Recommendation Run.
7. INSIGHT validates identity, schema compatibility, completeness, freshness, medication resolution, and cross-source consistency. Missing, stale, conflicting, ambiguous, or unavailable data are shown explicitly; the system does not silently infer or default clinically material facts.
8. Eligible cases are evaluated through approved deterministic safety policies, the DDI service, and the applicable versioned Bayesian-network pathways. Deterministic contraindications and urgent safety rules take precedence over probabilistic recommendations.
9. INSIGHT produces an explainable Primary Treatment Plan covering the supported treatment-setting, pharmacotherapy, safety, and follow-up recommendations. The draft is advisory and is not a prescription or signed order.
10. The psychiatrist reviews the recommendation evidence and safety findings, accepts or modifies the draft, and provides rationale where policy requires it. Medication changes trigger renewed DDI and safety checks before finalization.
11. The psychiatrist approves the plan. INSIGHT stores an attributable, immutable Final Treatment Plan with the original recommendation, all edits, overrides, evidence, model and knowledge versions, and audit/provenance records.
12. At follow-up, INSIGHT captures a new Encounter and Follow-up Delta, revalidates the current facts and medications, generates a new plan when appropriate, and links it as a superseding version without mutating the prior Final Treatment Plan.

## Features

### Clinical Workflow and Patient Records

- Role-based workspaces for administrators and psychiatrists.
- Canonical patient identity with a UUID owned by the Add New Patient module and a separate human-friendly patient-code alias.
- Encounter-based clinical records so assessments and treatment decisions are tied to a specific dated decision context.
- Structured schizophrenia diagnostic checklist with server-side evaluation while preserving explicit psychiatrist confirmation or bypass; computed results must not overwrite the psychiatrist's diagnosis.
- PANSS assessment covering the 30 positive, negative, and general psychopathology items, with total and subscale calculations derived from item responses and validated server-side in the unified system.
- Baseline and medical-history capture, including physical and laboratory information, medications, prior antipsychotic treatment and response, adherence concerns, contraindications, and relevant risk factors.
- Initial and follow-up workflows, patient lookup, longitudinal encounter history, and comparison with the preceding encounter.

### Decision Support and Clinical Safety

- A Treatment Plan orchestrator that assembles versioned data from Authentication, Patient, Diagnosis, Severity, Medical History, DDI, and BN Manager services.
- Eligibility and data-quality policies that distinguish complete, incomplete, stale, conflicting, unresolved, and dependency-failure states.
- Deterministic safety findings for allergies, contraindications, risk conditions, missing information, evidence quality, and other plan-qualifying or plan-blocking facts.
- Drugâ€“drug interaction evaluation using normalized medication identities where available, while preserving original clinician-entered text.
- Fail-closed medication resolution: ambiguous or unknown concepts are reported as incomplete interaction coverage and must not be presented as â€œno interaction.â€
- Versioned Bayesian-network and influence-diagram support for candidate pathways represented in the archive, including:
  - treatment setting;
  - pharmacotherapy selection;
  - involuntary-treatment considerations;
  - clozapine pathways for treatment resistance, substantial suicide risk, and persistent aggressive behavior;
  - continuation and maintenance of antipsychotic treatment;
  - long-acting injectable antipsychotic considerations;
  - management pathways for acute dystonia, parkinsonism, akathisia, and tardive dyskinesia.
- Visible recommendation evidence linking outputs to input facts, deterministic policy, model or knowledge version, posterior results, approved source metadata, and known limitations.
- Safety precedence rules so a Bayesian result cannot bypass a deterministic contraindication, serious DDI, unresolved medication, or urgent clinical condition.

### Psychiatrist Review, Finalization, and Follow-up

- Explainable Primary Treatment Plan presented as a system-generated draft rather than a prescription or clinical order.
- Structured review workspace that preserves the original recommendation while showing psychiatrist changes as an explicit diff.
- Append-only Plan Edit ledger with actor, timestamp, before/after values, and rationale where required.
- Optimistic concurrency control so simultaneous edits are detected and neither user's changes are silently lost.
- Re-execution of safety and DDI checks after clinically relevant edits and immediately before finalization.
- Policy-controlled overrides that require authorization and a documented reason; unsupported overrides remain blocked.
- Idempotent finalization producing an immutable and attributable Final Treatment Plan.
- Follow-up supersession that creates a new version and preserves the complete history and provenance of earlier plans.

### Platform Architecture and Integration

- Independently deployable modules with separate processes, configuration, health/readiness endpoints, migrations, and data ownership.
- Versioned REST contracts and JSON Schemas for all persisted and exchanged clinical datasets.
- No shared clinical database, cross-schema query, shared mutable filesystem, or direct import of another module's domain logic.
- A unified deployment option in one Docker image while retaining module separation; only an internal gateway is externally exposed, with nginx providing TLS termination on the VPS deployment path.
- SQLite support for local or prototype deployment and a defined PostgreSQL path for production-oriented persistence where implemented.
- Typed dependency failures, retry policy, correlation identifiers, and explicit readiness failures for unsupported schema versions or unavailable services.
- Consumer-driven contract tests, migration tests, backup/restore tests, failure-mode tests, and integrated end-to-end scenarios.

### Security, Privacy, Audit, and Governance

- Administrator and psychiatrist roles with server-validated sessions, password hashing, revocation support, CSRF protection on writes, rate limiting, and secure cookie configuration.
- Separation of security audit events from clinical provenance so access/activity records and recommendation lineage remain independently reviewable.
- Exclusion of protected health information from URLs, browser storage, logs, correlation identifiers, and unprotected exports.
- Encryption and secrets-management requirements for persisted sensitive data and deployed environments.
- Versioned, reviewable model and knowledge artifacts with explicit lifecycle states; only approved DDI records may generate clinical alerts.
- Clinical governance gates for intended use, supported pathways, deterministic policies, Bayesian evidence mappings and conditional probability tables, reference cases, override policy, retention, and release approval.
- Accessible clinical UI requirements, including visible text or icon indicators rather than color-only warnings and preservation of psychiatrist control.
- A page-aware, read-only AI assistant described by the product specification; it must remain advisory, must not modify clinical data, and must receive scrubbed context without patient identifiers.

### Administration and Operations

- Administrator account management and role assignment.
- Module discovery and dashboard routing without duplicating the business logic of downstream modules.
- Knowledge-base and Bayesian-model validation, review, activation, versioning, and rollback controls.
- Audit, chat-log, and operational-log access subject to role and privacy policy.
- Backup, restore, migration, environment configuration, health checks, graceful shutdown, and deployment rollback procedures.
- Standalone module verification plus unified Docker, Windows Docker Desktop, and Ubuntu VPS deployment verification.

## Scope

### In Scope

- A psychiatrist-facing CDSS for structured schizophrenia assessment, treatment-planning support, safety review, and follow-up planning.
- Administrator and psychiatrist authentication and authorization workflows.
- Patient and encounter identity, records, assessments, and longitudinal plan history.
- Clinician-confirmed diagnosis support, PANSS severity assessment, risk and medical-history inputs, medication normalization, DDI checking, and deterministic safety evaluation.
- Versioned BN Manager support for XML BIF 0.3 models and the candidate Bayesian-network or influence-diagram pathways supplied in the archive, subject to clinical validation before activation.
- Explainable Primary Treatment Plans, psychiatrist edits and rationale, safety revalidation, immutable Final Treatment Plans, and follow-up supersession.
- REST-only module integration, versioned schemas, separate module persistence, provenance, security audit, PHI controls, accessibility, deployment, testing, backup, and operational readiness work.
- Standalone execution of each module and a unified single-image deployment that preserves process and data boundaries.
- Completion of the integration and hardening work identified in the supplied unification plan, including canonical identity, server-side assessment validation, production persistence, DDI REST APIs, model provenance, and connected Treatment Plan UI routes.

### Out of Scope

- Autonomous diagnosis, autonomous treatment selection, prescribing, medication ordering, or replacement of psychiatrist judgment.
- Representing a Primary Treatment Plan as a prescription, signed clinical order, or mandatory course of action.
- Real-world clinical deployment before the bundled models, mappings, knowledge base, safety policies, reference cases, and supported pathways are independently validated and all release gates are approved.
- Treating illustrative or qualitative Bayesian-network probability tables as established clinical truth.
- Silently guessing missing clinical facts, resolving ambiguous medications without review, suppressing contradictory data, or interpreting an unavailable dependency as a negative finding.
- Direct database access between modules, a shared clinical database, cross-schema joins, shared mutable state, or one module owning another module's domain entities.
- A full FHIR server or comprehensive EHR integration in the first unified release; interoperability mappings may be added later through explicit, versioned adapters.
- Allowing the AI assistant to access patient identifiers, alter records, finalize plans, or act as an autonomous clinical decision-maker.
- Claiming that software tests alone establish clinical safety or release readiness.

## Success Criteria

1. A psychiatrist can authenticate, create or locate a patient, open an Encounter, and access only the workflows permitted by the psychiatrist role; a disabled or revoked account can no longer read or mutate protected data.
2. Every module starts and passes its own tests independently, and the unified deployment communicates between modules exclusively through published, versioned REST contracts.
3. The same canonical Patient UUID and Encounter UUID are used across all assessments and treatment-plan artifacts, while each module retains exclusive ownership of its own data and database.
4. Given a complete approved reference case, INSIGHT generates the same Primary Treatment Plan for the same immutable input snapshot, policy version, DDI knowledge version, and Bayesian-model version, and displays the complete recommendation evidence trace.
5. Missing severity data, conflicting risk information, stale inputs, unresolved medication concepts, unsupported schema versions, or unavailable dependencies produce explicit typed states and do not result in a silently completed recommendation.
6. DDI evaluation uses only approved knowledge records for clinical alerts, reports unresolved medication coverage explicitly, and blocks or qualifies finalization according to the approved safety policy.
7. A psychiatrist can modify a proposed treatment, see the original recommendation and diff, record required rationale, and trigger server-side DDI and safety revalidation before the plan is finalized.
8. Concurrent editing produces a detectable precondition failure rather than lost updates, and all accepted edits remain attributable in an append-only ledger.
9. Finalization is idempotent and creates an immutable Final Treatment Plan; a later follow-up plan supersedes the prior version while preserving both plans, their evidence, edits, and provenance.
10. Existing plans retain the exact model and knowledge versions originally used after a BN or DDI knowledge-base upgrade, while newly generated plans visibly use the new approved versions.
11. PHI is absent from URLs, browser storage, logs, and unprotected exports; authentication, CSRF, audit, migration, backup/restore, accessibility, failure-mode, and integrated deployment tests pass for the declared environment.
12. Independent psychiatrists approve the supported pathways and reference cases, and the designated clinical, privacy, regulatory, security, and deployment owners approve release for the declared intended use before any clinical deployment.