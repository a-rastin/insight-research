# Graph Report - diagnosis  (2026-07-09)

## Corpus Check
- 27 files · ~39,765 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 503 nodes · 1015 edges · 25 communities (22 shown, 3 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 68 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `98dc33e8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Diagnosis API Router|Diagnosis API Router]]
- [[_COMMUNITY_CSRF Test Suite|CSRF Test Suite]]
- [[_COMMUNITY_Auth Enforcement Tests|Auth Enforcement Tests]]
- [[_COMMUNITY_SQLite Persistence Layer|SQLite Persistence Layer]]
- [[_COMMUNITY_CSRF Module|CSRF Module]]
- [[_COMMUNITY_Auth Adapter|Auth Adapter]]
- [[_COMMUNITY_API Self-Check|API Self-Check]]
- [[_COMMUNITY_Fake Auth HTTP Handler|Fake Auth HTTP Handler]]
- [[_COMMUNITY_HTTP Server|HTTP Server]]
- [[_COMMUNITY_HANDOFF Doc|HANDOFF Doc]]
- [[_COMMUNITY_test_discovery.py|test_discovery.py]]
- [[_COMMUNITY_test_readiness.py|test_readiness.py]]
- [[_COMMUNITY_TestCSRF|TestCSRF]]
- [[_COMMUNITY_TestPersistence|TestPersistence]]
- [[_COMMUNITY_TestRestContract|TestRestContract]]
- [[_COMMUNITY_test_routes.py|test_routes.py]]
- [[_COMMUNITY_TestRestContract|TestRestContract]]
- [[_COMMUNITY_auth.py|auth.py]]
- [[_COMMUNITY_dashboard.py|dashboard.py]]
- [[_COMMUNITY_TestClinicianAuthority|TestClinicianAuthority]]
- [[_COMMUNITY_Session|Session]]

## God Nodes (most connected - your core abstractions)
1. `evaluate()` - 23 edges
2. `DiagnosisStore` - 22 edges
3. `Session` - 18 edges
4. `check_readiness()` - 18 edges
5. `main()` - 18 edges
6. `TestCriteriaRules` - 18 edges
7. `_reload_config()` - 17 edges
8. `TestRestContract` - 17 edges
9. `TestPersistence` - 17 edges
10. `resolve_patient()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `TestAuditSeam` --uses--> `Evaluation`  [INFERRED]
  test_unittest.py → diagnosis/criteria.py
- `TestAuthRejection` --uses--> `Evaluation`  [INFERRED]
  test_unittest.py → diagnosis/criteria.py
- `TestClinicianAuthority` --uses--> `Evaluation`  [INFERRED]
  test_unittest.py → diagnosis/criteria.py
- `TestCSRF` --uses--> `Evaluation`  [INFERRED]
  test_unittest.py → diagnosis/criteria.py
- `TestPatientIdentity` --uses--> `Evaluation`  [INFERRED]
  test_unittest.py → diagnosis/criteria.py

## Import Cycles
- 3-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 3-file cycle: `diagnosis/__init__.py -> diagnosis/readiness.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 3-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/dashboard.py -> diagnosis/__init__.py`
- 3-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/page.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/dashboard.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/diagnosis_api.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/page.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/api.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/readiness.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/diagnosis_api.py -> diagnosis/dashboard.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/api.py -> diagnosis/dashboard.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/api.py -> diagnosis/page.py -> diagnosis/__init__.py`
- 5-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/diagnosis_api.py -> diagnosis/dashboard.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 5-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/api.py -> diagnosis/dashboard.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 5-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/api.py -> diagnosis/diagnosis_api.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 5-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/api.py -> diagnosis/page.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 5-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/api.py -> diagnosis/diagnosis_api.py -> diagnosis/dashboard.py -> diagnosis/__init__.py`

## Communities (25 total, 3 thin omitted)

### Community 0 - "Diagnosis API Router"
Cohesion: 0.10
Nodes (32): API seam for the diagnosis module — the composed router.  The single ``router`, page(), Browser page seam for the diagnosis module.  The single ``GET /`` route serves, Read ``static/index.html`` once per request (no build step)., Serve the SPA. Stamp a fresh signed CSRF token into the page     (``<meta name=, _read_page(), main(), Embeddable module UI tests for the diagnosis module.  Issue: replace the stand (+24 more)

### Community 1 - "CSRF Test Suite"
Cohesion: 0.15
Nodes (26): BaseHTTPRequestHandler, _client(), _free_port(), _Handler, main(), _mint_bad_token(), _mint_valid_token(), HTTPServer (+18 more)

### Community 2 - "Auth Enforcement Tests"
Cohesion: 0.15
Nodes (22): _arm_with_csrf(), _client_for(), _exercise(), _free_port(), _Handler, main(), HTTPServer, TestClient (+14 more)

### Community 3 - "SQLite Persistence Layer"
Cohesion: 0.23
Nodes (30): _config_selfcheck(), Self-verify the adapter. Covers:     - every previously hard-coded default surf, _clear_env(), main(), Settings-adapter tests for the diagnosis module.  Strategy:     - Exercise th, When ``AUTH_BASE_URL`` is unset, ``auth.AUTH_BASE_URL`` defaults to     the set, ``dashboard.MODULE_ID`` defaults to the settings-derived id; a     custom ``DIA, ``app.py`` builds its CORS middleware from ``settings.cors_origins``     (no lo (+22 more)

### Community 4 - "CSRF Module"
Cohesion: 0.16
Nodes (16): mint(), Request, Signed double-submit CSRF for the diagnosis module's write routes.  PUT /diagnos, FastAPI dependency. Fail closed (403) on any mismatch.      Mirrors ``auth.requi, Test-only hook (mirrors ``auth.reset_auth_for_tests``). Pin a     known secret s, Attach an HMAC-SHA256 signature to ``raw``. Returns ``raw.sig``., Constant-time check that ``token`` was signed by this secret., Mint a fresh signed token. Callers set it as the CSRF cookie and     surface it (+8 more)

### Community 5 - "Auth Adapter"
Cohesion: 0.21
Nodes (10): BaseModel, _dump_for_audit(), JSON snapshot for audit logging. Persisted to the audit table by     ``store.au, require_csrf(), init_session(), put_session(), Request, Protected diagnosis REST seam — per-patient session state.  This is the only r (+2 more)

### Community 6 - "API Self-Check"
Cohesion: 0.21
Nodes (20): _arm_with_csrf(), _AuthHandler, _client(), _free_port(), main(), _PatientHandler, HTTPServer, TestClient (+12 more)

### Community 7 - "Fake Auth HTTP Handler"
Cohesion: 0.11
Nodes (17): 10. Gotchas that cost time if you don't know, 11. Glossary, 12. If you only read four files, 1. What this module is, 2. Repo layout, 3. The two layers and how to find things, 4. The web page (`static/index.html`), 5. Run it (+9 more)

### Community 8 - "HTTP Server"
Cohesion: 0.14
Nodes (13): Architecture (deep module), Configuration (env knobs → `Settings`), CSRF on write routes, Dashboard module-route discovery, `diagnosis` module, Embeddable module UI — `createDiagnosisModule({root, apiBaseUrl})`, Interface (the seam), Module-local readiness (`/ready`) (+5 more)

### Community 9 - "HANDOFF Doc"
Cohesion: 0.06
Nodes (28): _http_selfcheck(), Run the REST-contract unittest cases under the bypass shim.      The inline ``, _demo(), Run the rule-suite unittest cases. Exit non-zero on failure.      Run: ``python, main(), Boot the diagnosis module as a standalone web app.      python -m diagnosis, _build_patient(), _fetch_patient() (+20 more)

### Community 11 - "test_discovery.py"
Cohesion: 0.23
Nodes (13): _client(), _free_port(), _Handler, main(), HTTPServer, TestClient, Dashboard discovery-route tests for the diagnosis module.  Mirrors the ``test_, _start_fake_auth() (+5 more)

### Community 15 - "test_readiness.py"
Cohesion: 0.07
Nodes (53): Any, Cursor, Standalone FastAPI app for the diagnosis module.  Usage:     python -m diagnosis, ready(), Shared wiring for the diagnosis route seams.  The public router was split into, _check_auth(), _check_db(), _check_patient() (+45 more)

### Community 16 - "TestCSRF"
Cohesion: 0.14
Nodes (4): _fake_request(), Minimal stand-in for ``fastapi.Request`` for dep-level unittests.     ``auth.re, TestAuthRejection, TestCSRF

### Community 18 - "TestRestContract"
Cohesion: 0.18
Nodes (4): evaluate(), Evaluation, Pure function: given the clinician's checked criteria, return an     Evaluation., TestCriteriaRules

### Community 19 - "test_routes.py"
Cohesion: 0.17
Nodes (20): main(), _paths(), Route-seam split tests for the diagnosis module.  Issue: split public routes f, Invariant 4: ``/_meta`` and ``/_csrf`` MUST match before     ``/{code}`` or Fas, The Dashboard discovery route lives in ``dashboard.py`` only —     invariant 10, The audit-log route lives in ``dashboard.py`` only — invariant 10     (seam spl, `MODULE_ID` is part of the discovery contract — Dashboard joins on     it and t, Tests + Insight callers import contract symbols from     ``diagnosis.api`` dire (+12 more)

### Community 21 - "auth.py"
Cohesion: 0.09
Nodes (21): _AuthUnavailable, _build_session(), _fetch_session(), Authentication adapter for the diagnosis module.  Delegates trust to the central, FastAPI dependency factory. Returns a dependency that enforces     membership in, Test-only hook: rebind the auth base URL for the lifetime of the     current pro, The auth service is unreachable or returned a non-JSON body., Call the Insight auth service. Returns the parsed JSON.      Raises ``_AuthUnava (+13 more)

### Community 22 - "dashboard.py"
Cohesion: 0.18
Nodes (9): get_criteria(), meta_contract(), DSM-5-TR schizophrenia diagnostic criteria and evaluation engine.  Source: DSM-5, Return the criteria tree, grouped for the UI. Caller must not mutate., Rule contract the browser page consumes for its optimistic display.      The web, meta(), Dashboard discovery seam for the diagnosis module.  This is the read-only disc, Return the criteria tree and the rule contract the UI derives its     optimisti (+1 more)

### Community 24 - "Session"
Cohesion: 0.17
Nodes (11): The slice of an Insight auth session this module consumes.      Never holds a to, Session, audit_log(), csrf_token(), module_routes(), Dashboard module-route discovery.      The larger Insight Dashboard learns how, Audit-log seam — expose persisted audit snapshots for a code.      The future, Mint a signed double-submit CSRF token. Sets the ``csrf`` cookie     and return (+3 more)

## Knowledge Gaps
- **26 isolated node(s):** `1. What this module is`, `2. Repo layout`, `Layer A — the seams (api.py + 3 sub-seams, app.py, __init__.py, __main__.py)`, `Layer C — the repository (store.py)`, `Layer B — the engine (criteria.py)` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_config_selfcheck()` connect `SQLite Persistence Layer` to `HANDOFF Doc`, `auth.py`?**
  _High betweenness centrality (0.106) - this node is a cross-community bridge._
- **Why does `TestPersistence` connect `TestPersistence` to `HANDOFF Doc`, `TestRestContract`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `main()` (e.g. with `test_app_cors_reads_settings()` and `test_auth_module_sourced_from_settings()`) actually correct?**
  _`main()` has 16 INFERRED edges - model-reasoned connections that need verification._
- **What connects `diagnosis module — DSM-5-TR schizophrenia criteria checklist for Insight.  Dee`, `Boot the diagnosis module as a standalone web app.      python -m diagnosis`, `API seam for the diagnosis module — the composed router.  The single ``router`` to the rest of the system?**
  _140 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Diagnosis API Router` be split into smaller, more focused modules?**
  _Cohesion score 0.09915966386554621 - nodes in this community are weakly interconnected._
- **Should `CSRF Test Suite` be split into smaller, more focused modules?**
  _Cohesion score 0.14532019704433496 - nodes in this community are weakly interconnected._
- **Should `Auth Enforcement Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.1476923076923077 - nodes in this community are weakly interconnected._