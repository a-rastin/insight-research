# Graph Report - Medical-History-1.0.0  (2026-07-12)

## Corpus Check
- 9 files · ~3,481 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 130 nodes · 138 edges · 41 communities (7 shown, 34 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 8 edges (avg confidence: 0.79)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Frontend app.js logic|Frontend app.js logic]]
- [[_COMMUNITY_Server config & modules|Server config & modules]]
- [[_COMMUNITY_HTML UI panels|HTML UI panels]]
- [[_COMMUNITY_package.json manifest|package.json manifest]]
- [[_COMMUNITY_Server internals docs|Server internals docs]]
- [[_COMMUNITY_Production hardening limits|Production hardening limits]]
- [[_COMMUNITY_Activation flow|Activation flow]]
- [[_COMMUNITY_README integration overview|README integration overview]]
- [[_COMMUNITY_Activation & submission handlers|Activation & submission handlers]]
- [[_COMMUNITY_Routing & JSON IO|Routing & JSON I/O]]
- [[_COMMUNITY_Options & submission endpoints|Options & submission endpoints]]
- [[_COMMUNITY_README|README.md]]
- [[_COMMUNITY_Activation Status Flow active - submitted  expired|Activation Status Flow: active -> submitted / expired]]
- [[_COMMUNITY_BASE_PATH Environment Variable|BASE_PATH Environment Variable]]
- [[_COMMUNITY_Permissive Wildcard CORS|Permissive Wildcard CORS]]
- [[_COMMUNITY_Keep Schema In Sync With Code|Keep Schema In Sync With Code]]
- [[_COMMUNITY_Standard Error Payload Shape|Standard Error Payload Shape]]
- [[_COMMUNITY_Static File Path Traversal Guard|Static File Path Traversal Guard]]
- [[_COMMUNITY_GET apiinternalmedical-historyactivation{code}|GET /api/internal/medical-history/activation/{code}]]
- [[_COMMUNITY_GET apiinternalmedical-historyhealth|GET /api/internal/medical-history/health]]
- [[_COMMUNITY_Internal REST API Boundary|Internal REST API Boundary]]
- [[_COMMUNITY_Local JSON File Persistence|Local JSON File Persistence]]
- [[_COMMUNITY_Known Limitations List|Known Limitations List]]
- [[_COMMUNITY_launchUrl Response Field|launchUrl Response Field]]
- [[_COMMUNITY_GET apiinternalmedical-historysubmissions|GET /api/internal/medical-history/submissions]]
- [[_COMMUNITY_Medical History Handoff Document|Medical History Handoff Document]]
- [[_COMMUNITY_Medication Notes UI Gap|Medication Notes UI Gap]]
- [[_COMMUNITY_Medication Row|Medication Row]]
- [[_COMMUNITY_Zero-Dependency Node.js Server|Zero-Dependency Node.js Server]]
- [[_COMMUNITY_GET apiinternalmedical-historyoptions|GET /api/internal/medical-history/options]]
- [[_COMMUNITY_PHI Production Hardening Gaps|PHI Production Hardening Gaps]]
- [[_COMMUNITY_Repeat Submission Limitation|Repeat Submission Limitation]]
- [[_COMMUNITY_GET apiinternalmedical-historyschema|GET /api/internal/medical-history/schema]]
- [[_COMMUNITY_Server.js Function Inventory|Server.js Function Inventory]]
- [[_COMMUNITY_2-Hour Activation Session Expiry|2-Hour Activation Session Expiry]]
- [[_COMMUNITY_PowerShell Smoke Test|PowerShell Smoke Test]]
- [[_COMMUNITY_Static Frontend Serving|Static Frontend Serving]]
- [[_COMMUNITY_Default Port 4173|Default Port 4173]]
- [[_COMMUNITY_Module Integration Pattern|Module Integration Pattern]]
- [[_COMMUNITY_medical_history_entry_form|medical_history_entry_form]]
- [[_COMMUNITY_README (Quick Start)|README (Quick Start)]]

## God Nodes (most connected - your core abstractions)
1. `activateMedicalHistory()` - 9 edges
2. `submitMedicalHistory()` - 9 edges
3. `route()` - 9 edges
4. `getActivation()` - 8 edges
5. `sendJson()` - 7 edges
6. `sendError()` - 7 edges
7. `restoreActivationFromUrl()` - 6 edges
8. `readJson()` - 6 edges
9. `showError()` - 5 edges
10. `showForm()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `History Form (HTML)` --references--> `POST /api/internal/medical-history/submissions`  [INFERRED]
  public/index.html → MEDICAL_HISTORY_HANDOFF.md
- `Three-State UI Flow` --references--> `Frontend URL ?code= Loader`  [INFERRED]
  public/index.html → MEDICAL_HISTORY_HANDOFF.md
- `Activation Panel (HTML)` --references--> `POST /api/internal/medical-history/activate`  [INFERRED]
  public/index.html → MEDICAL_HISTORY_HANDOFF.md
- `Comorbidities Multi-Select` --shares_data_with--> `Comorbidity Option List`  [INFERRED]
  public/index.html → MEDICAL_HISTORY_HANDOFF.md
- `Activation Code Input` --references--> `6-Character Alphanumeric Activation Code`  [INFERRED]
  public/index.html → MEDICAL_HISTORY_HANDOFF.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Activation Flow (activate endpoint, session, expiry, code validation, launchUrl, frontend loader)** — medical_history_handoff_activateendpoint, medical_history_handoff_activationsession, medical_history_handoff_sessionexpiry, medical_history_handoff_activationcodevalidation, medical_history_handoff_lauRL, medical_history_handoff_urlquerycodeloader, public_index_activationpanel [EXTRACTED 0.95]
- **Submission Flow (submit endpoint, submission record, comorbidity option, medication row, history-form)** — medical_history_handoff_submitendpoint, medical_history_handoff_medicalhistorysubmission, medical_history_handoff_comorbidityoption, medical_history_handoff_medicationrow, public_index_historyform [EXTRACTED 0.95]
- **Production Hardening Gaps (CORS wildcard, JSON persistence, PHI, repeat submissions)** — medical_history_handoff_corswildcard, medical_history_handoff_jsonpersistence, medical_history_handoff_phiproductiongaps, medical_history_handoff_repeatsubmissions, medical_history_handoff_cornotsecret [EXTRACTED 0.85]

## Communities (41 total, 34 thin omitted)

### Community 0 - "Frontend app.js logic"
Cohesion: 0.21
Nodes (14): activateFromCode(), addMedicationRow(), api(), clearError(), elements, escapeAttribute(), isYes(), loadOptions() (+6 more)

### Community 1 - "Server config & modules"
Cohesion: 0.14
Nodes (29): activateMedicalHistory(), ANTIPSYCHOTIC_OPTIONS, CLOZAPINE_CONTRAINDICATION_OPTIONS, COMORBIDITY_OPTIONS, crypto, ensureDataFiles(), ensureJsonFile(), fs (+21 more)

### Community 2 - "HTML UI panels"
Cohesion: 0.13
Nodes (15): POST /api/internal/medical-history/activate, 6-Character Alphanumeric Activation Code, Comorbidity Option List, returnUrl / Back-to-Dashboard, POST /api/internal/medical-history/submissions, Frontend URL ?code= Loader, Activation Code Input, Activation Panel (HTML) (+7 more)

### Community 3 - "package.json manifest"
Cohesion: 0.17
Nodes (11): description, engines, node, main, name, private, scripts, dev (+3 more)

### Community 8 - "Activation & submission handlers"
Cohesion: 0.22
Nodes (6): assert, fs, os, path, { spawn }, test

### Community 9 - "Routing & JSON I/O"
Cohesion: 0.33
Nodes (5): Architecture, Change guidance, Conditional UI behavior, Persistence and testing, Submission model (v2)

### Community 11 - "README.md"
Cohesion: 0.33
Nodes (5): Collected information, Correlation and persistence, Internal REST API, Production note, Run and test

## Knowledge Gaps
- **67 isolated node(s):** `name`, `version`, `private`, `description`, `main` (+62 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **34 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `name`, `version`, `private` to the rest of the system?**
  _83 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Server config & modules` be split into smaller, more focused modules?**
  _Cohesion score 0.14482758620689656 - nodes in this community are weakly interconnected._
- **Should `HTML UI panels` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._