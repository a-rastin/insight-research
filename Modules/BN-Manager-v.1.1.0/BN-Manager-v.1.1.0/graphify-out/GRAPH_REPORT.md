# Graph Report - G:\INSIGHT-Project\Modules\BN-Manager-v.1.1.0\BN-Manager-v.1.1.0  (2026-07-12)

## Corpus Check
- 15 files · ~7,603 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 224 nodes · 561 edges · 13 communities (10 shown, 3 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 12 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Evaluation and Graph Model
- XML Compiler and Schema
- FastAPI Model Operations
- Authentication and CSRF
- Semantic Validation Tests
- Contract and Response Envelope
- Registry and API Tests
- XML Migration Architecture
- Authentication Integration Tests
- Configuration and Server
- Package Metadata
- Clozapine Suicide Risk Network
- Pharmacotherapy Network

## God Nodes (most connected - your core abstractions)
1. `ClinicalGraphModel` - 29 edges
2. `compile_xmlbif()` - 24 edges
3. `ValidateModelTests` - 21 edges
4. `Node` - 20 edges
5. `_make_node()` - 17 edges
6. `_make_potential()` - 17 edges
7. `create_app()` - 17 edges
8. `XmlBifCompileError` - 16 edges
9. `ValidationMessage` - 14 edges
10. `validate_model()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `ValidateModelTests` --uses--> `ClinicalGraphModel`  [INFERRED]
  tests/test_validation.py → clinical_graph_models/model.py
- `_make_node()` --references--> `Node`  [EXTRACTED]
  tests/test_validation.py → clinical_graph_models/model.py
- `_make_potential()` --references--> `Potential`  [EXTRACTED]
  tests/test_validation.py → clinical_graph_models/model.py
- `create_app()` --calls--> `contract_payload()`  [EXTRACTED]
  bn_manager_backend/main.py → clinical_graph_models/contract.py
- `create_app()` --calls--> `error_response()`  [EXTRACTED]
  bn_manager_backend/main.py → clinical_graph_models/contract.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Four Canonical XML Networks** — readme_pharmacotherapy, readme_treatment_setting, readme_involuntary_treatment_considerations, readme_clozapine_in_suicide_risk [EXTRACTED 1.00]
- **XML Model Processing Pipeline** — context_module_registry_file_boundary, readme_secure_xml_compilation, ubiquitous_language_structural_validation, ubiquitous_language_semantic_validation, ubiquitous_language_posterior_evaluation [EXTRACTED 1.00]

## Communities (13 total, 3 thin omitted)

### Community 0 - "Evaluation and Graph Model"
Cohesion: 0.15
Nodes (30): _enumerate_chance_assignments(), evaluate_expected_utilities(), evaluate_posterior(), EvaluationResult, _evidence_weight(), ClinicalGraphModel, Node, Potential (+22 more)

### Community 1 - "XML Compiler and Schema"
Cohesion: 0.17
Nodes (21): read_registry_schema(), _compile_definition(), _compile_variable(), compile_xmlbif(), _node_kind(), _parse_table(), _parse_xml_document(), _properties() (+13 more)

### Community 2 - "FastAPI Model Operations"
Cohesion: 0.16
Nodes (21): BnManagerHttpError, create_app(), _evaluate_payload(), _load_model(), Any, ClinicalGraphModel, Exception, SessionState (+13 more)

### Community 3 - "Authentication and CSRF"
Cohesion: 0.19
Nodes (18): _as_dict(), assert_csrf_token(), AuthenticationRestAdapter, _blocked_reason(), _collect_roles(), CsrfError, _first_text(), _is_active() (+10 more)

### Community 4 - "Semantic Validation Tests"
Cohesion: 0.37
Nodes (3): _make_node(), _make_potential(), ValidateModelTests

### Community 5 - "Contract and Response Envelope"
Cohesion: 0.20
Nodes (9): contract_payload(), error_response(), _meta(), ok_response(), Any, RouteContract, TargetNodeContract, XmlBifTarget (+1 more)

### Community 6 - "Registry and API Tests"
Cohesion: 0.11
Nodes (5): TestClient, AdminSessionAdapter, BnManagerBackendTests, Request, SessionState

### Community 7 - "XML Migration Architecture"
Cohesion: 0.14
Nodes (18): BN Manager XML Status UI, BN Manager Contract 2.0.0, Compact CPT Broadcast, Module Registry File-Loading Boundary, XML-Only Clinical BN Boundary, Legacy Workflow Removal, XML Bayesian Network Migration, Involuntary Treatment Considerations Network (+10 more)

### Community 8 - "Authentication Integration Tests"
Cohesion: 0.26
Nodes (4): AuthenticationGuardTests, FakeSessionAdapter, Request, SessionState

### Community 9 - "Configuration and Server"
Cohesion: 0.50
Nodes (3): BnManagerSettings, get_settings(), main()

## Knowledge Gaps
- **8 isolated node(s):** `clinical-graph-models`, `Pharmacotherapy Network`, `Treatment Setting Network`, `Involuntary Treatment Considerations Network`, `Clozapine in Suicide Risk Network` (+3 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `compile_xmlbif()` connect `XML Compiler and Schema` to `FastAPI Model Operations`, `Contract and Response Envelope`, `Registry and API Tests`?**
  _High betweenness centrality (0.139) - this node is a cross-community bridge._
- **Why does `ClinicalGraphModel` connect `Evaluation and Graph Model` to `Semantic Validation Tests`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Why does `create_app()` connect `FastAPI Model Operations` to `XML Compiler and Schema`, `Contract and Response Envelope`, `Registry and API Tests`, `Authentication Integration Tests`, `Configuration and Server`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `ClinicalGraphModel` (e.g. with `EvaluationResult` and `ValidateModelTests`) actually correct?**
  _`ClinicalGraphModel` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `clinical-graph-models`, `Pharmacotherapy Network`, `Treatment Setting Network` to the rest of the system?**
  _8 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Evaluation and Graph Model` be split into smaller, more focused modules?**
  _Cohesion score 0.14950166112956811 - nodes in this community are weakly interconnected._
- **Should `Registry and API Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.10526315789473684 - nodes in this community are weakly interconnected._