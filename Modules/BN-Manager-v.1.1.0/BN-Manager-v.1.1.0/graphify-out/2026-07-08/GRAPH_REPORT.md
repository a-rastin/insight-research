# Graph Report - .  (2026-07-08)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 348 nodes · 732 edges · 40 communities (12 shown, 28 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 45 edges (avg confidence: 0.66)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_main.py|main.py]]
- [[_COMMUNITY_ClinicalGraphModel|ClinicalGraphModel]]
- [[_COMMUNITY_compile_xmlbif|compile_xmlbif]]
- [[_COMMUNITY_BNM-05 Vendor XMLBIF Model Registry|BNM-05 Vendor XMLBIF Model Registry]]
- [[_COMMUNITY_compile_xmlbif|compile_xmlbif]]
- [[_COMMUNITY_parse_net|parse_net]]
- [[_COMMUNITY___init__.py|__init__.py]]
- [[_COMMUNITY_BNM-01 Primitive BN Manager Contract|BNM-01 Primitive BN Manager Contract]]
- [[_COMMUNITY__Parser|_Parser]]
- [[_COMMUNITY_BnManagerBackendTests|BnManagerBackendTests]]
- [[_COMMUNITY_Ubiquitous Language|Ubiquitous Language]]
- [[_COMMUNITY_BN Manager Static UI|BN Manager Static UI]]
- [[_COMMUNITY_Standalone BN Manager API|Standalone BN Manager API]]
- [[_COMMUNITY_Module Status Panels|Module Status Panels]]
- [[_COMMUNITY_BNM-03 Protected Evaluation and Model-Management Routes|BNM-03 Protected Evaluation and Model-Management Routes]]
- [[_COMMUNITY_BNM-04 Dashboard Route Discovery|BNM-04 Dashboard Route Discovery]]
- [[_COMMUNITY_Legacy .net Adapter Policy|Legacy .net Adapter Policy]]
- [[_COMMUNITY_Stable Human-in-the-Loop Boundary|Stable Human-in-the-Loop Boundary]]
- [[_COMMUNITY_Inter-Module Route Contract|Inter-Module Route Contract]]
- [[_COMMUNITY_Liveness Readiness and Contract Access|Liveness Readiness and Contract Access]]
- [[_COMMUNITY_Standalone FastAPI Module Shell|Standalone FastAPI Module Shell]]
- [[_COMMUNITY_Authentication REST Adapter|Authentication REST Adapter]]
- [[_COMMUNITY_CSRF Protection|CSRF Protection]]
- [[_COMMUNITY_Role Guards|Role Guards]]
- [[_COMMUNITY_Dashboard Route Discovery Slice|Dashboard Route Discovery Slice]]
- [[_COMMUNITY_Protected Embeddable UI|Protected Embeddable UI]]
- [[_COMMUNITY_Public Dashboard Discovery Route|Public Dashboard Discovery Route]]
- [[_COMMUNITY_Treatments for Akathisia Model|Treatments for Akathisia Model]]
- [[_COMMUNITY_Treatments for Parkinsonism Model|Treatments for Parkinsonism Model]]
- [[_COMMUNITY_Vendor XMLBIF Model Registry|Vendor XMLBIF Model Registry]]
- [[_COMMUNITY_clinical-graph-models|clinical-graph-models]]
- [[_COMMUNITY_Authentication Environment Overrides|Authentication Environment Overrides]]
- [[_COMMUNITY_Module Boundary Without Cross-Surface Imports|Module Boundary Without Cross-Surface Imports]]
- [[_COMMUNITY_Bayesian Network|Bayesian Network]]
- [[_COMMUNITY_Clinical Model Evaluation|Clinical Model Evaluation]]
- [[_COMMUNITY_Graph-First Editing|Graph-First Editing]]
- [[_COMMUNITY_Influence Diagram|Influence Diagram]]
- [[_COMMUNITY_Model Validation|Model Validation]]
- [[_COMMUNITY_Structured Model Editing|Structured Model Editing]]
- [[_COMMUNITY_Uncertain Evidence|Uncertain Evidence]]

## God Nodes (most connected - your core abstractions)
1. `ClinicalGraphModel` - 36 edges
2. `Node` - 22 edges
3. `create_app()` - 19 edges
4. `XmlBifCompileError` - 18 edges
5. `compile_xmlbif()` - 18 edges
6. `parse_net()` - 17 edges
7. `validate_model()` - 17 edges
8. `evaluate_expected_utilities()` - 16 edges
9. `_Parser` - 16 edges
10. `Potential` - 15 edges

## Surprising Connections (you probably didn't know these)
- `Clinical Graph Model` --semantically_similar_to--> `ClinicalGraphModel (internal model)`  [INFERRED] [semantically similar]
  CONTEXT.md → docs/BNM-06-xmlbif-compiler-with-lxml.md
- `XMLBIF 0.3` --semantically_similar_to--> `xmlbif-0.3-bn-manager.xsd (bundled XSD)`  [INFERRED] [semantically similar]
  CONTEXT.md → docs/BNM-06-xmlbif-compiler-with-lxml.md
- `BnManagerHttpError` --uses--> `ClinicalGraphModel`  [INFERRED]
  bn_manager_backend/main.py → clinical_graph_models/model.py
- `AuthenticationGuardTests` --uses--> `SessionState`  [INFERRED]
  tests/test_auth_adapter.py → bn_manager_backend/auth_adapter.py
- `FakeSessionAdapter` --uses--> `SessionState`  [INFERRED]
  tests/test_auth_adapter.py → bn_manager_backend/auth_adapter.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **XMLBIF Compilation Pipeline** — docs_bnm_06_xmlbif_compiler_with_lxml_compile_xmlbif, docs_bnm_06_xmlbif_compiler_with_lxml_xmlbif_xsd, docs_bnm_06_xmlbif_compiler_with_lxml_clinical_graph_model, docs_bnm_06_xmlbif_compiler_with_lxml_xml_bif_compile_error [EXTRACTED 0.95]
- **Primitive Flow Model Loading** — docs_bnm_06_xmlbif_compiler_with_lxml_load_model, docs_bnm_06_xmlbif_compiler_with_lxml_compile_xmlbif, docs_bnm_06_xmlbif_compiler_with_lxml_load_legacy_net_model [EXTRACTED 0.95]
- **Vendor Model Registry XMLBIF Set** — docs_bnm_06_xmlbif_compiler_with_lxml_parkinsonism_model, docs_bnm_06_xmlbif_compiler_with_lxml_akathisia_model, docs_bnm_06_xmlbif_compiler_with_lxml_xmlbif_xsd [EXTRACTED 0.95]
- **Clinical Graph Model Vocabulary** — ubiquitous_language_clinical_graph_model, ubiquitous_language_bayesian_network, ubiquitous_language_influence_diagram, ubiquitous_language_structured_model_editing, ubiquitous_language_clinical_model_evaluation [EXTRACTED 1.00]
- **Module Boundary Protection Pattern** — readme_module_boundary, docs_bnm_03_authentication_rest_adapter_role_guards_session_adapter, docs_bnm_04_dashboard_route_discovery_slice_protected_embeddable_ui, docs_bnm_05_vendor_xmlbif_model_registry_path_safety [INFERRED 0.75]

## Communities (40 total, 28 thin omitted)

### Community 0 - "main.py"
Cohesion: 0.09
Nodes (34): _as_dict(), assert_csrf_token(), AuthenticationRestAdapter, _blocked_reason(), _collect_roles(), CsrfError, _first_text(), _is_active() (+26 more)

### Community 1 - "ClinicalGraphModel"
Cohesion: 0.14
Nodes (29): _model_to_xmlbif(), _enumerate_chance_assignments(), evaluate_expected_utilities(), evaluate_posterior(), EvaluationResult, _evidence_weight(), ClinicalGraphModel, Node (+21 more)

### Community 2 - "compile_xmlbif"
Cohesion: 0.05
Nodes (42): Rationale: Module runnable without Authentication, Dashboard, patient DB imports, BNM-01 Primitive BN Manager Contract, BNM-05 Vendor Model Registry Routes, BNM-06 XMLBIF Compiler Contract, Clinical Graph Model, Clinical Model Evaluation, Evaluation Engine Adapter, Graph-First Editing (+34 more)

### Community 3 - "BNM-05 Vendor XMLBIF Model Registry"
Cohesion: 0.05
Nodes (34): BNM-02 Standalone FastAPI Module Shell, Module Layout, Purpose, Routes, Run, Status, Test, BNM-03 Authentication REST Adapter and Role Guards (+26 more)

### Community 4 - "compile_xmlbif"
Cohesion: 0.17
Nodes (23): get_registry_entry(), list_registry_entries(), ModelRegistryEntry, Path, read_owned_registry_file(), read_registry_model(), read_registry_schema(), resolve_owned_registry_file() (+15 more)

### Community 5 - "parse_net"
Cohesion: 0.15
Nodes (11): BaseHTTPRequestHandler, model_to_dict(), parse_net(), serialize_net(), escape_html(), escape_json_attr(), main(), _validation_payload() (+3 more)

### Community 6 - "__init__.py"
Cohesion: 0.20
Nodes (9): contract_payload(), error_response(), _meta(), ok_response(), Any, RouteContract, TargetNodeContract, XmlBifTarget (+1 more)

### Community 7 - "BNM-01 Primitive BN Manager Contract"
Cohesion: 0.11
Nodes (16): Preserve .net round-trip compatibility, Consequences, Context, Decision, Freeze primitive BN Manager contract, BNM-01 Primitive BN Manager Contract, Boundary, Clinical Safety Wording (+8 more)

### Community 8 - "_Parser"
Cohesion: 0.37
Nodes (5): _contains_nested(), _format_attributes(), _format_value(), _Parser, Any

### Community 10 - "Ubiquitous Language"
Cohesion: 0.29
Nodes (6): Core Concepts, Editing And Validation, Evidence And Evaluation, Model Elements, Ubiquitous Language, Version 1 Agreements

### Community 11 - "BN Manager Static UI"
Cohesion: 0.67
Nodes (3): BN Manager Static UI, BN Manager, Clinical Graph Model

### Community 12 - "Standalone BN Manager API"
Cohesion: 0.67
Nodes (3): BNM-02 Standalone FastAPI Module Shell, Standalone BN Manager API, Standalone Workbench

## Knowledge Gaps
- **92 isolated node(s):** `clinical-graph-models`, `Run Standalone BN Manager API`, `Run Standalone Workbench`, `Use As Module`, `BN Manager Contract` (+87 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **28 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ClinicalGraphModel` connect `ClinicalGraphModel` to `main.py`, `compile_xmlbif`, `parse_net`, `__init__.py`, `_Parser`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `parse_net()` connect `parse_net` to `main.py`, `ClinicalGraphModel`, `__init__.py`, `_Parser`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `ClinicalGraphModel` (e.g. with `BnManagerHttpError` and `EvaluationResult`) actually correct?**
  _`ClinicalGraphModel` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `Node` (e.g. with `NetParseError` and `_Parser`) actually correct?**
  _`Node` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `XmlBifCompileError` (e.g. with `ClinicalGraphModel` and `Node`) actually correct?**
  _`XmlBifCompileError` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `clinical-graph-models`, `Run Standalone BN Manager API`, `Run Standalone Workbench` to the rest of the system?**
  _100 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09225589225589226 - nodes in this community are weakly interconnected._