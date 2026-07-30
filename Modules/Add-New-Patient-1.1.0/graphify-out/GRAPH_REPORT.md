# Graph Report - G:/INSIGHT-Project/Modules/Add-New-Patient-1.1.0  (2026-07-12)

## Corpus Check
- 24 files · ~297,837 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 254 nodes · 549 edges · 15 communities (10 shown, 5 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 8 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Backend Test Suite
- Config and CSRF Helpers
- API and Module Documentation
- Auth Module
- Database Adapter and Repository
- Clinical Data Models
- Design System Rationale
- Frontend App Logic
- SQLite Migration Utilities
- Frontend HTML Shell
- Frontend Test Harness
- Package Init
- Image 1
- Image 2
- Python Dependencies

## God Nodes (most connected - your core abstractions)
1. `AddNewPatientServer` - 43 edges
2. `request_json()` - 40 edges
3. `valid_payload()` - 27 edges
4. `csrf_headers()` - 26 edges
5. `AddNewPatientBackendTest` - 26 edges
6. `Add New Patient Module Handoff` - 16 edges
7. `AuthBoundaryTest` - 14 edges
8. `MockAuthenticationServer` - 13 edges
9. `fetch_auth_identity()` - 11 edges
10. `PatientRepository` - 11 edges

## Surprising Connections (you probably didn't know these)
- `REST-Only Communication Rule` --semantically_similar_to--> `Carbon Health Design System`  [INFERRED] [semantically similar]
  handoff.md → DESIGN.md
- `White Space as Clinical Instrument` --semantically_similar_to--> `REST-Only Communication Rule`  [INFERRED] [semantically similar]
  DESIGN.md → handoff.md
- `Add New Patient Module Handoff` --conceptually_related_to--> `Repository Handoff`  [EXTRACTED]
  docs/add-new-patient-handoff.md → handoff.md
- `Stable Patient Identifier Contract` --conceptually_related_to--> `Stable Patient Identifier Contract`  [EXTRACTED]
  docs/api-contract.md → handoff.md
- `Patient Code (6-char identifier)` --references--> `Stable Patient Identifier Contract`  [EXTRACTED]
  docs/patient-domain-glossary.md → handoff.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Five Clinical Status States** — design_md_urgent, design_md_warning, design_md_normal, design_md_follow_up, design_md_info [EXTRACTED 1.00]
- **Stable Patient Identifier System** — patient_stable_id, patient_code, docs_api_contract_stable_identifier_contract, handoff_md_stable_identifier_contract, f1_1_stable_patient_identifier [EXTRACTED 1.00]
- **Add New Patient Module Architecture** — readme_md, readme_md_stack, handoff_md, handoff_md_core_architectural_rule, static_allowlist, docs_add_new_patient_handoff_md, docs_api_contract_md, docs_patient_domain_glossary_md [EXTRACTED 1.00]

## Communities (15 total, 5 thin omitted)

### Community 0 - "Backend Test Suite"
Cohesion: 0.12
Nodes (15): AddNewPatientBackendTest, AddNewPatientServer, auth_payload(), AuthBoundaryTest, ConcurrencyTest, csrf_headers(), dob_days_ago(), dob_for_age() (+7 more)

### Community 1 - "Config and CSRF Helpers"
Cohesion: 0.10
Nodes (35): Settings, csrf_error(), generate_csrf_token(), JSONResponse, Request, request_has_valid_csrf(), sign_csrf_token(), verify_csrf_token() (+27 more)

### Community 2 - "API and Module Documentation"
Cohesion: 0.06
Nodes (37): A0.1 Module Rebuild (Node to Python), GET /api/health, GET /api/patients, GET /api/patients/{idOrCode}, GET /internal/dashboard/module-routes/add-new-patient, POST /api/patients, Auth Module, B1.1 Auth REST Client (+29 more)

### Community 3 - "Auth Module"
Cohesion: 0.19
Nodes (20): auth_session_url(), AuthSessionError, _blocked_auth_session(), fetch_auth_identity(), _fetch_json(), forwarded_auth_headers(), _has_blocked_status(), _has_truthy_flag() (+12 more)

### Community 4 - "Database Adapter and Repository"
Cohesion: 0.16
Nodes (12): DatabaseAdapter, Any, canonical_suicidality(), compute_age(), _find_patient_id_row(), intake_row(), json_list(), now_iso() (+4 more)

### Community 5 - "Clinical Data Models"
Cohesion: 0.12
Nodes (6): ClinicalFlag, ClinicalSection, PatientDemographics, Any, BaseModel, date

### Community 6 - "Design System Rationale"
Cohesion: 0.17
Nodes (13): Carbon Health Design System, Five-State Clinical Status System, Follow-up Status, Info Status, Normal Status, Skeleton Loaders, Teal as Clinical Trust, Typography Legibility as Patient Safety (+5 more)

### Community 7 - "Frontend App Logic"
Cohesion: 0.25
Nodes (9): CLIENT_VALIDATION_MESSAGES, createAddNewPatientModule(), FIELD_INPUT_NAMES, generateBrowserPatientCode(), getRequiredElement(), isValidDob(), normalizePatientInput(), parseListInput() (+1 more)

### Community 8 - "SQLite Migration Utilities"
Cohesion: 0.36
Nodes (4): migrate_patients_to_identity_table(), now_iso(), SQLiteAdapter, Connection

### Community 9 - "Frontend HTML Shell"
Cohesion: 0.50
Nodes (4): Patient Module HTML Shell, Dashboard View, Patient Form, Patient View

## Knowledge Gaps
- **26 isolated node(s):** `CLIENT_VALIDATION_MESSAGES`, `FIELD_INPUT_NAMES`, `here`, `html`, `Urgent Status` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PatientRepository` connect `Database Adapter and Repository` to `Config and CSRF Helpers`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **What connects `CLIENT_VALIDATION_MESSAGES`, `FIELD_INPUT_NAMES`, `here` to the rest of the system?**
  _26 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Backend Test Suite` be split into smaller, more focused modules?**
  _Cohesion score 0.11528291909042834 - nodes in this community are weakly interconnected._
- **Should `Config and CSRF Helpers` be split into smaller, more focused modules?**
  _Cohesion score 0.10409745293466224 - nodes in this community are weakly interconnected._
- **Should `API and Module Documentation` be split into smaller, more focused modules?**
  _Cohesion score 0.06456456456456457 - nodes in this community are weakly interconnected._
- **Should `Clinical Data Models` be split into smaller, more focused modules?**
  _Cohesion score 0.12280701754385964 - nodes in this community are weakly interconnected._