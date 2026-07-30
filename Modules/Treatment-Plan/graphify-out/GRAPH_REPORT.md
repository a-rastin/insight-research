# Graph Report - .  (2026-07-16)

## Corpus Check
- 15 files · ~65,739 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1622 nodes · 3578 edges · 115 communities (93 shown, 22 thin omitted)
- Extraction: 84% EXTRACTED · 16% INFERRED · 0% AMBIGUOUS · INFERRED: 580 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Safety Policy Tests
- Repository Adapter Contracts
- Clinical Context Tests
- Plan Edit Ledger
- Supersession Tests
- Governance Scope Matrix v1
- Bayesian Net Eval Tests
- BN Evaluation Bundle
- Frontend Config
- Safety Policy Tests v2
- Schema: Plan Arrays
- Schema: Plan Content
- Observability Tests
- Schema: Clinical Input Snapshot
- Handoff Migration
- Schema: Final/Primary Plan defs
- Scaffold Tests
- Frontend tsconfig
- Schema: Safety Finding
- Finalization Versioning Tests
- Contract Checker Scripts
- Schema: Root & defs
- Schema: Plan Edit
- Schema: Instrument/Interpretation
- Frontend Review Workspace
- Governance Scope Matrix Schema
- Prototype Lifecycle
- FastAPI App Boot
- Safety Policy Module
- Schema: Problem Details
- Governance Schema Required
- Schema: Audit Provenance
- Governance Schema Types
- Security Tests
- Schema: Allergies/Conditions
- Schema: Follow-up Delta
- Schema: Required fields
- Schema: Source Reference
- Schema: Status enum
- Edit Ledger Route Tests
- Context Map Modules
- Schema: Code field
- Schema: Final Plan required
- Schema: PlanEdit/PrimaryPlan required
- Governance: Approvals/Decision Gates
- Governance: Items & Status
- Audit Event: action/id
- Audit Event: required/actor
- Identifier Contract Tests
- Audit Event: agent
- Governance: Owners & Role
- Migration TP19 Provenance
- Schema: Diagnosis required
- Audit Event: entity
- Schema: SafetyFindings/Sources
- Schema: module enum
- Audit Event: what
- Governance: status enum
- Identifiers contract
- Audit Event: identifier
- Schema: SafetyFinding required
- Context Ownership Tests
- BN Eval Store/Orchestrator
- Frontend Public Assets
- Audit Event: root
- Audit Event: outcome
- Release Gate Tests
- Security Authentication Port
- Context Map ownership
- Audit Provenance Schema
- ClinicalInputSnapshot Schema
- Final Plan Schema
- Follow-up Delta Schema
- Plan Edit Schema
- Primary Plan Schema
- Problem Details Schema
- Recommendation Run Schema
- Safety Finding Schema
- Governance: decision field
- Context Ownership Checker
- Identifier Contract Checker
- Release Gate Checker
- Audit Event: correlationId
- ADR TP04
- Governance: signedAt
- Governance TP01
- Governance TP10
- BN Evaluation Bundle hash
- Frontend index/main
- Graphify query memory
- Plan Recommendation
- Treatment Plan init
- Migrations init
- Policies init
- docker-compose
- DDI check result
- Handoff release gate
- Plan Edit
- README BN Evaluation
- README DDI check
- README edit ledger
- README eligibility
- README primary plan
- README safety policy
- Repository Protocol
- SQLite Repository connection

## God Nodes (most connected - your core abstractions)
1. `DdiMedicationChecker` - 69 edges
2. `PlanEditLedger` - 60 edges
3. `PlanFinalizer` - 50 edges
4. `SQLiteRepository` - 43 edges
5. `Medication` - 42 edges
6. `InMemoryPlanEditStore` - 40 edges
7. `PreconditionFailed` - 33 edges
8. `SQLitePlanEditStore` - 32 edges
9. `BnEvaluationBundle` - 32 edges
10. `Observability` - 32 edges

## Surprising Connections (you probably didn't know these)
- `ScaffoldTests` --uses--> `RuntimeRecord`  [INFERRED]
  tests/test_tp06_scaffold.py → treatment_plan/repository.py
- `ScaffoldTests` --uses--> `SQLiteRepository`  [INFERRED]
  tests/test_tp06_scaffold.py → treatment_plan/sqlite_repository.py
- `SecurityTests` --uses--> `ConfigurationError`  [INFERRED]
  tests/test_tp07_security.py → treatment_plan/config.py
- `SecurityTests` --uses--> `Settings`  [INFERRED]
  tests/test_tp07_security.py → treatment_plan/config.py
- `SecurityTests` --uses--> `InMemoryRepository`  [INFERRED]
  tests/test_tp07_security.py → treatment_plan/repository.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **TP-19 Persistence Seams** — handoff_migratedrunner, handoff_retentionpolicy, handoff_persistence_fraud_controls [EXTRACTED 0.95]
- **Repository Protocol implementees** — readme_repository_protocol, readme_sqliterepository, readme_postgresqlrepository [EXTRACTED 0.95]
- **INSIGHT entity ownership model** — context_map_patient, context_map_encounter, context_map_assessment, context_map_medication_knowledge, context_map_recommendation, context_map_final_plan [EXTRACTED 1.00]

## Communities (115 total, 22 thin omitted)

### Community 0 - "Safety Policy Tests"
Cohesion: 0.05
Nodes (67): SafetyPolicy, primary_plan(), RecordingDdiPort, FailingDdiPort, TP13CheckerFailureTests, no_interaction_response(), TP13MedicationSetBindingTests, TP13HttpAdapterTests (+59 more)

### Community 1 - "Repository Adapter Contracts"
Cohesion: 0.06
Nodes (34): Collection, Connection, Dialect, PermissionError, Protocol, RepositoryContractTests, RetentionPolicyTests, TP19BackupTests (+26 more)

### Community 2 - "Clinical Context Tests"
Cohesion: 0.06
Nodes (45): Exception, payloads(), TP08ContractTests, context(), TP09EligibilityPolicyTests, _BnAdapter, _Circuit, ClinicalContext (+37 more)

### Community 3 - "Plan Edit Ledger"
Cohesion: 0.09
Nodes (33): _apply_pointer(), _canonical_json(), _editable_tokens(), EditCategory, EditLedgerError, _encode_token(), _etag(), _finding_for_pointer() (+25 more)

### Community 4 - "Supersession Tests"
Cohesion: 0.12
Nodes (32): ConcurrentSnapshotProvider, final_plan(), finalized_ledger(), follow_up_delta(), Generator, hash_json(), prior_primary_plan(), snapshot() (+24 more)

### Community 5 - "Governance Scope Matrix v1"
Cohesion: 0.04
Nodes (47): approvals, clinicalScope, appointmentPolicy, emergencyBehavior, planBreadth, supportedDiagnoses, supportedPopulation, clinicalValidation (+39 more)

### Community 6 - "Bayesian Net Eval Tests"
Cohesion: 0.10
Nodes (24): HTTPX, requirements.txt, FakeEvaluator, TP10BnEvaluationTests, BnEvaluationOrchestrator, BnFinding, BnFindingCode, BnManagerHttpEvaluator (+16 more)

### Community 7 - "BN Evaluation Bundle"
Cohesion: 0.17
Nodes (28): AssessedRecommendation, SafetyPolicyDecision, BnEvaluationBundle, BnModel, ModelEvaluation, _AppointmentOption, _bundled_policy(), EvidenceKind (+20 more)

### Community 8 - "Frontend Config"
Cohesion: 0.06
Nodes (33): dependencies, react, react-dom, typescript, vite, @vitejs/plugin-react, vitest, devDependencies (+25 more)

### Community 9 - "Safety Policy Tests v2"
Cohesion: 0.20
Nodes (14): TP11SafetyPolicyTests, bundle(), evaluation(), facts(), TP12PrimaryPlanTests, TP13DdiCheckTests, MappingCoverage, ProbabilisticRecommendation (+6 more)

### Community 10 - "Schema: Plan Arrays"
Cohesion: 0.10
Nodes (28): items, items, type, items, type, additionalProperties, minLength, properties (+20 more)

### Community 11 - "Schema: Plan Content"
Cohesion: 0.07
Nodes (28): PlanContent, pattern, type, additionalProperties, properties, required, type, additionalProperties (+20 more)

### Community 12 - "Observability Tests"
Cohesion: 0.12
Nodes (10): Logger, Settings, TP20ObservabilityTests, AuditEvent, MetricPoint, Observability, opaque_id(), Any (+2 more)

### Community 13 - "Schema: Clinical Input Snapshot"
Cohesion: 0.08
Nodes (27): $ref, additionalProperties, properties, type, $ref, ClinicalInputSnapshot, RecommendationRun, additionalProperties (+19 more)

### Community 14 - "Handoff Migration"
Cohesion: 0.08
Nodes (27): MigrationRunner seam, Treatment Plan Module Objective, TP-19 Persistence Fraud Controls, PlanSuperseder seam, Module README, RetentionPolicy seam, Approval-gated PHI redaction, TP-18 Follow-up Supersession (+19 more)

### Community 15 - "Schema: Final/Primary Plan defs"
Cohesion: 0.08
Nodes (26): minLength, type, $ref, $ref, FinalPlan, PrimaryPlan, $ref, $ref (+18 more)

### Community 16 - "Scaffold Tests"
Cohesion: 0.17
Nodes (9): Repository, ScaffoldTests, create_app(), _bool(), ConfigurationError, ValueError, Settings, main() (+1 more)

### Community 17 - "Frontend tsconfig"
Cohesion: 0.08
Nodes (24): compilerOptions, allowJs, allowSyntheticDefaultImports, esModuleInterop, forceConsistentCasingInFileNames, isolatedModules, jsx, lib (+16 more)

### Community 18 - "Schema: Safety Finding"
Cohesion: 0.08
Nodes (24): enum, type, $ref, $ref, minLength, type, $ref, minLength (+16 more)

### Community 19 - "Finalization Versioning Tests"
Cohesion: 0.20
Nodes (10): RecordingPort, ConcurrentPort, content_hash(), ContextProvider, HighAlertPort, TP17FinalizationVersioningTests, InMemoryPlanEditStore, PlanEditLedger (+2 more)

### Community 20 - "Contract Checker Scripts"
Cohesion: 0.21
Nodes (14): check_compatibility(), ContractError, lint_openapi(), load(), _pointer(), Path, ValueError, Offline TP-05 JSON Schema, example, compatibility, and OpenAPI conformance. (+6 more)

### Community 21 - "Schema: Root & defs"
Cohesion: 0.09
Nodes (21): $defs, Instant, PlanEdit, SafetyFinding, Uuid, Version, $id, format (+13 more)

### Community 22 - "Schema: Plan Edit"
Cohesion: 0.09
Nodes (22): $ref, $ref, $ref, enum, type, pattern, type, properties (+14 more)

### Community 23 - "Schema: Instrument/Interpretation"
Cohesion: 0.09
Nodes (22): minLength, type, minLength, type, instrument, interpretation, score, severity (+14 more)

### Community 24 - "Frontend Review Workspace"
Cohesion: 0.17
Nodes (18): App(), reviewCase, clonePlan(), compare(), Comparison, createReviewWorkspace(), Dose, fields (+10 more)

### Community 25 - "Governance Scope Matrix Schema"
Cohesion: 0.10
Nodes (21): enum, minLength, type, pattern, properties, minLength, type, behavior (+13 more)

### Community 26 - "Prototype Lifecycle"
Cohesion: 0.21
Nodes (11): main(), Run: python prototype/run_lifecycle.py (synthetic walkthrough only)., initial_state(), ValueError, THROWAWAY TP-04 lifecycle prototype. Not for clinical use or production import., Return a new state for one action; never mutate ``state``., reduce(), _require() (+3 more)

### Community 27 - "FastAPI App Boot"
Cohesion: 0.18
Nodes (12): FastAPI, LogRecord, configure_logging(), JsonFormatter, Any, _safe_fields(), PHI-safe operational observability and security audit events (TP-20)., Capability (+4 more)

### Community 28 - "Safety Policy Module"
Cohesion: 0.20
Nodes (15): AssessedRecommendation, _Definition, Disposition, EmergencyEscalation, _load_bundled_definition(), _normalized(), _normalized_set(), _parse_definition() (+7 more)

### Community 29 - "Schema: Problem Details"
Cohesion: 0.11
Nodes (18): $ref, ProblemDetails, minLength, type, pattern, type, additionalProperties, properties (+10 more)

### Community 30 - "Governance Schema Required"
Cohesion: 0.11
Nodes (17): $id, schemaVersion, required, $schema, title, type, approvals, clinicalScope (+9 more)

### Community 31 - "Schema: Audit Provenance"
Cohesion: 0.12
Nodes (16): minLength, type, additionalProperties, properties, type, AuditProvenance, minLength, type (+8 more)

### Community 32 - "Governance Schema Types"
Cohesion: 0.12
Nodes (16): type, type, minLength, type, type, type, properties, additionalProperties (+8 more)

### Community 33 - "Security Tests"
Cohesion: 0.30
Nodes (5): RuntimeError, SecurityTests, AccessDenied, AuthenticationUnavailable, Session

### Community 34 - "Schema: Allergies/Conditions"
Cohesion: 0.13
Nodes (15): items, type, uniqueItems, items, type, uniqueItems, additionalProperties, properties (+7 more)

### Community 35 - "Schema: Follow-up Delta"
Cohesion: 0.13
Nodes (15): minItems, type, FollowUpDelta, $ref, additionalProperties, properties, type, $ref (+7 more)

### Community 36 - "Schema: Required fields"
Cohesion: 0.16
Nodes (15): required, required, required, capturedAt, changes, currentMedications, deltaId, encounterId (+7 more)

### Community 37 - "Schema: Source Reference"
Cohesion: 0.13
Nodes (15): pattern, type, SourceReference, minLength, type, contentHash, etag, resourceId (+7 more)

### Community 38 - "Schema: Status enum"
Cohesion: 0.13
Nodes (15): enum, acknowledged, confirmed, editing, evaluating, gathering-inputs, generated, generation-failed (+7 more)

### Community 39 - "Edit Ledger Route Tests"
Cohesion: 0.31
Nodes (9): EditLedgerRouteTests, EditLedgerTests, ledger(), primary_plan(), PolicyBound, A trusted policy constraint for one exact JSON Pointer., ReasonRequired, Authenticate and authorize through one deny-by-default interface. (+1 more)

### Community 40 - "Context Map Modules"
Cohesion: 0.16
Nodes (14): Add New Patient module, Assessment entity, Authentication module, BN Manager module, DDI Checker module, Diagnosis module, Encounter entity, Final Plan entity (+6 more)

### Community 41 - "Schema: Code field"
Cohesion: 0.14
Nodes (14): minLength, pattern, type, enum, type, properties, code, codeSystem (+6 more)

### Community 42 - "Schema: Final Plan required"
Cohesion: 0.17
Nodes (13): required, schemaVersion, required, attestation, contentHash, finalizedAt, finalizedBy, module (+5 more)

### Community 43 - "Schema: PlanEdit/PrimaryPlan required"
Cohesion: 0.17
Nodes (13): required, required, after, before, content, createdAt, editedAt, editId (+5 more)

### Community 44 - "Governance: Approvals/Decision Gates"
Cohesion: 0.17
Nodes (13): items, type, type, approvals, clinicalValidation, items, maxItems, minItems (+5 more)

### Community 45 - "Governance: Items & Status"
Cohesion: 0.15
Nodes (13): required, status, items, type, notSupported, behavior, case, decision (+5 more)

### Community 46 - "Audit Event: action/id"
Cohesion: 0.17
Nodes (12): pattern, type, format, type, properties, action, id, recorded (+4 more)

### Community 47 - "Audit Event: required/actor"
Cohesion: 0.18
Nodes (12): required, required, action, actorId, correlationId, id, outcome, recorded (+4 more)

### Community 49 - "Audit Event: agent"
Cohesion: 0.20
Nodes (10): additionalProperties, properties, required, type, agent, who, additionalProperties, properties (+2 more)

### Community 50 - "Governance: Owners & Role"
Cohesion: 0.29
Nodes (10): owners, required, type, role, enum, clinicalSafetyOfficer, privacy, product (+2 more)

### Community 51 - "Migration TP19 Provenance"
Cohesion: 0.42
Nodes (9): clinical_provenance, evidence_links, input_snapshots, plan_edits, plan_items, plan_versions, plans, recommendation_runs (+1 more)

### Community 52 - "Schema: Diagnosis required"
Cohesion: 0.25
Nodes (9): required, status, required, code, codeSystem, detail, requestId, title (+1 more)

### Community 53 - "Audit Event: entity"
Cohesion: 0.25
Nodes (8): items, type, additionalProperties, properties, required, type, entity, what

### Community 54 - "Schema: SafetyFindings/Sources"
Cohesion: 0.25
Nodes (8): $ref, safetyFindings, sources, items, type, items, minItems, type

### Community 55 - "Schema: module enum"
Cohesion: 0.25
Nodes (8): enum, type, module, add-new-patient, bn-manager, ddi-checker, diagnosis, medicalHistory

### Community 56 - "Audit Event: what"
Cohesion: 0.29
Nodes (7): what, additionalProperties, properties, required, type, required, identifier

### Community 57 - "Governance: status enum"
Cohesion: 0.29
Nodes (7): enum, approved, draft_pending_approval, rejected, superseded, unresolved, withdrawn

### Community 58 - "Identifiers contract"
Cohesion: 0.33
Nodes (6): encounterId UUID, Idempotency-Key, TP-03 identifier contract, patientCode alias, patientId UUID, Schema versioning contract

### Community 59 - "Audit Event: identifier"
Cohesion: 0.33
Nodes (6): additionalProperties, properties, required, type, identifier, value

### Community 60 - "Schema: SafetyFinding required"
Cohesion: 0.33
Nodes (6): required, category, detectedAt, findingId, severity, summary

### Community 62 - "BN Eval Store/Orchestrator"
Cohesion: 0.40
Nodes (3): BnEvaluationStore, BnEvaluator, Protocol

### Community 63 - "Frontend Public Assets"
Cohesion: 0.40
Nodes (5): Clinical Decision Support, INSIGHT Logo, Neural Network Graph Visual, Open Door / Gateway Visual, Schizophrenia Care

### Community 64 - "Audit Event: root"
Cohesion: 0.40
Nodes (4): additionalProperties, $id, $schema, type

### Community 65 - "Audit Event: outcome"
Cohesion: 0.40
Nodes (5): enum, outcome, denied, failure, success

### Community 67 - "Security Authentication Port"
Cohesion: 0.40
Nodes (3): AuthenticationPort, datetime, Protocol

### Community 68 - "Context Map ownership"
Cohesion: 0.50
Nodes (4): CONTEXT-MAP, Entity ownership rule, Prohibited cross-module coupling, Sole ownership rule

### Community 69 - "Audit Provenance Schema"
Cohesion: 0.50
Nodes (3): $id, $ref, $schema

### Community 70 - "ClinicalInputSnapshot Schema"
Cohesion: 0.50
Nodes (3): $id, $ref, $schema

### Community 71 - "Final Plan Schema"
Cohesion: 0.50
Nodes (3): $id, $ref, $schema

### Community 72 - "Follow-up Delta Schema"
Cohesion: 0.50
Nodes (3): $id, $ref, $schema

### Community 73 - "Plan Edit Schema"
Cohesion: 0.50
Nodes (3): $id, $ref, $schema

### Community 74 - "Primary Plan Schema"
Cohesion: 0.50
Nodes (3): $id, $ref, $schema

### Community 75 - "Problem Details Schema"
Cohesion: 0.50
Nodes (3): $id, $ref, $schema

### Community 76 - "Recommendation Run Schema"
Cohesion: 0.50
Nodes (3): $id, $ref, $schema

### Community 77 - "Safety Finding Schema"
Cohesion: 0.50
Nodes (3): $id, $ref, $schema

### Community 78 - "Governance: decision field"
Cohesion: 0.50
Nodes (4): type, decision, null, string

### Community 79 - "Context Ownership Checker"
Cohesion: 0.67
Nodes (3): evaluate(), main(), Validate unique ownership and REST-only cross-module relationship rules.

### Community 80 - "Identifier Contract Checker"
Cohesion: 0.67
Nodes (3): evaluate(), main(), Validate the shared TP-03 identifier and transport contract.

### Community 81 - "Release Gate Checker"
Cohesion: 0.67
Nodes (3): evaluate(), main(), Fail-closed TP-01 clinical release gate. Uses only the Python standard library.

### Community 82 - "Audit Event: correlationId"
Cohesion: 0.67
Nodes (3): format, type, correlationId

### Community 83 - "ADR TP04"
Cohesion: 0.67
Nodes (3): ADR TP-04 disposable lifecycle prototype, ADR TP-04 disposable reduce(state,action) reducer, ADR TP-04 psychiatrist agreement pending

### Community 84 - "Governance: signedAt"
Cohesion: 0.67
Nodes (3): signedAt, format, type

### Community 85 - "Governance TP01"
Cohesion: 0.67
Nodes (3): TP-01 scope and release gates, TP-01 clinical release BLOCKED, TP-01 eight decision gates

### Community 86 - "Governance TP10"
Cohesion: 0.67
Nodes (3): TP-10 BN mapping coverage, TP-10 four BN model vocabularies, TP-10 synthetic candidate (pending approval)

## Knowledge Gaps
- **482 isolated node(s):** `$schema`, `$id`, `$ref`, `$schema`, `$id` (+477 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `required` connect `Audit Event: required/actor` to `Audit Event: root`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `required` connect `Governance: Items & Status` to `Governance: Approvals/Decision Gates`, `Audit Event: required/actor`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `id` connect `Audit Event: required/actor` to `Governance: Items & Status`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 28 inferred relationships involving `DdiMedicationChecker` (e.g. with `RecordingDdiPort` and `TP13DdiCheckTests`) actually correct?**
  _`DdiMedicationChecker` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `PlanEditLedger` (e.g. with `EditLedgerRouteTests` and `EditLedgerTests`) actually correct?**
  _`PlanEditLedger` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `PlanFinalizer` (e.g. with `BlockingPort` and `RecordingPort`) actually correct?**
  _`PlanFinalizer` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `SQLiteRepository` (e.g. with `ScaffoldTests` and `EditLedgerRouteTests`) actually correct?**
  _`SQLiteRepository` has 18 INFERRED edges - model-reasoned connections that need verification._