# Graph Report - diagnosis  (2026-07-08)

## Corpus Check
- 24 files · ~27,682 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 403 nodes · 784 edges · 19 communities (18 shown, 1 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 35 edges (avg confidence: 0.52)
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

## God Nodes (most connected - your core abstractions)
1. `DiagnosisStore` - 22 edges
2. `evaluate()` - 21 edges
3. `check_readiness()` - 18 edges
4. `TestCriteriaRules` - 18 edges
5. `Session` - 17 edges
6. `TestRestContract` - 17 edges
7. `TestPersistence` - 17 edges
8. `resolve_patient()` - 16 edges
9. `main()` - 16 edges
10. `main()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `TestAuthRejection` --uses--> `Evaluation`  [INFERRED]
  test_unittest.py → diagnosis/criteria.py
- `TestCSRF` --uses--> `Evaluation`  [INFERRED]
  test_unittest.py → diagnosis/criteria.py
- `TestPatientIdentity` --uses--> `Evaluation`  [INFERRED]
  test_unittest.py → diagnosis/criteria.py
- `TestPersistence` --uses--> `Evaluation`  [INFERRED]
  test_unittest.py → diagnosis/criteria.py
- `TestRestContract` --uses--> `Evaluation`  [INFERRED]
  test_unittest.py → diagnosis/criteria.py

## Import Cycles
- 3-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/dashboard.py -> diagnosis/__init__.py`
- 3-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 3-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/page.py -> diagnosis/__init__.py`
- 3-file cycle: `diagnosis/__init__.py -> diagnosis/readiness.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/api.py -> diagnosis/dashboard.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/dashboard.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/api.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/diagnosis_api.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/api.py -> diagnosis/page.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/api.py -> diagnosis/page.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 4-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/readiness.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 5-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/api.py -> diagnosis/dashboard.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 5-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/api.py -> diagnosis/diagnosis_api.py -> diagnosis/deps.py -> diagnosis/__init__.py`
- 5-file cycle: `diagnosis/__init__.py -> diagnosis/app.py -> diagnosis/api.py -> diagnosis/page.py -> diagnosis/deps.py -> diagnosis/__init__.py`

## Communities (19 total, 1 thin omitted)

### Community 0 - "Diagnosis API Router"
Cohesion: 0.10
Nodes (17): _AuthUnavailable, The auth service is unreachable or returned a non-JSON body., _build_patient(), _fetch_patient(), _PatientNotFound, _PatientUnavailable, Patient identity adapter for the diagnosis module.  Aligns the diagnosis module', The registry responded 404 — the code is not a known patient. (+9 more)

### Community 1 - "CSRF Test Suite"
Cohesion: 0.15
Nodes (26): BaseHTTPRequestHandler, _client(), _free_port(), _Handler, main(), _mint_bad_token(), _mint_valid_token(), HTTPServer (+18 more)

### Community 2 - "Auth Enforcement Tests"
Cohesion: 0.15
Nodes (22): _arm_with_csrf(), _client_for(), _exercise(), _free_port(), _Handler, main(), HTTPServer, TestClient (+14 more)

### Community 3 - "SQLite Persistence Layer"
Cohesion: 0.11
Nodes (21): Cursor, _http_selfcheck(), Run the REST-contract unittest cases under the bypass shim.      The inline ``, _demo(), Run the rule-suite unittest cases. Exit non-zero on failure.      Run: ``python, main(), Boot the diagnosis module as a standalone web app.      python -m diagnosis, _patient_selfcheck() (+13 more)

### Community 4 - "CSRF Module"
Cohesion: 0.16
Nodes (16): mint(), Request, Signed double-submit CSRF for the diagnosis module's write routes.  PUT /diagnos, FastAPI dependency. Fail closed (403) on any mismatch.      Mirrors ``auth.requi, Test-only hook (mirrors ``auth.reset_auth_for_tests``). Pin a     known secret s, Attach an HMAC-SHA256 signature to ``raw``. Returns ``raw.sig``., Constant-time check that ``token`` was signed by this secret., Mint a fresh signed token. Callers set it as the CSRF cookie and     surface it (+8 more)

### Community 5 - "Auth Adapter"
Cohesion: 0.06
Nodes (54): BaseModel, API seam for the diagnosis module — the composed router.  The single ``router`, _build_session(), _fetch_session(), Authentication adapter for the diagnosis module.  Delegates trust to the central, FastAPI dependency factory. Returns a dependency that enforces     membership in, Test-only hook: rebind the auth base URL for the lifetime of the     current pro, The slice of an Insight auth session this module consumes.      Never holds a to (+46 more)

### Community 6 - "API Self-Check"
Cohesion: 0.21
Nodes (20): _arm_with_csrf(), _AuthHandler, _client(), _free_port(), main(), _PatientHandler, HTTPServer, TestClient (+12 more)

### Community 7 - "Fake Auth HTTP Handler"
Cohesion: 0.12
Nodes (16): 10. Gotchas that cost time if you don't know, 11. Glossary, 12. If you only read four files, 1. What this module is, 2. Repo layout, 3. The two layers and how to find things, 4. The web page (`static/index.html`), 5. Run it (+8 more)

### Community 8 - "HTTP Server"
Cohesion: 0.17
Nodes (11): Architecture (deep module), CSRF on write routes, Dashboard module-route discovery, `diagnosis` module, Interface (the seam), Module-local readiness (`/ready`), Mount inside Insight (the larger app), Notes (+3 more)

### Community 9 - "HANDOFF Doc"
Cohesion: 0.10
Nodes (13): evaluate(), Evaluation, get_criteria(), meta_contract(), DSM-5-TR schizophrenia diagnostic criteria and evaluation engine.  Source: DSM-5, Pure function: given the clinician's checked criteria, return an     Evaluation., Return the criteria tree, grouped for the UI. Caller must not mutate., Rule contract the browser page consumes for its optimistic display.      The web (+5 more)

### Community 11 - "test_discovery.py"
Cohesion: 0.23
Nodes (13): _client(), _free_port(), _Handler, main(), HTTPServer, TestClient, Dashboard discovery-route tests for the diagnosis module.  Mirrors the ``test_, _start_fake_auth() (+5 more)

### Community 15 - "test_readiness.py"
Cohesion: 0.12
Nodes (39): Any, Standalone FastAPI app for the diagnosis module.  Usage:     python -m diagnosis, ready(), _check_auth(), _check_db(), _check_patient(), check_readiness(), Module-local health/readiness probe for the diagnosis module.  Liveness (``/he (+31 more)

### Community 16 - "TestCSRF"
Cohesion: 0.14
Nodes (4): _fake_request(), Minimal stand-in for ``fastapi.Request`` for dep-level unittests.     ``auth.re, TestAuthRejection, TestCSRF

### Community 18 - "TestRestContract"
Cohesion: 0.12
Nodes (4): _dump_for_audit(), JSON snapshot for audit logging. Persisted to the audit table by     ``store.au, One TestClient for the class so the bypass-shimmed store is reset     between t, TestRestContract

## Knowledge Gaps
- **24 isolated node(s):** `1. What this module is`, `2. Repo layout`, `Layer A — the seams (api.py + 3 sub-seams, app.py, __init__.py, __main__.py)`, `Layer C — the repository (store.py)`, `Layer B — the engine (criteria.py)` (+19 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DiagnosisStore` connect `SQLite Persistence Layer` to `Auth Adapter`, `test_readiness.py`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Why does `TestPersistence` connect `TestPersistence` to `HANDOFF Doc`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `TestRestContract` connect `TestRestContract` to `HANDOFF Doc`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `TestCriteriaRules` (e.g. with `Evaluation` and `Patient`) actually correct?**
  _`TestCriteriaRules` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `diagnosis module — DSM-5-TR schizophrenia criteria checklist for Insight.  Dee`, `Boot the diagnosis module as a standalone web app.      python -m diagnosis`, `API seam for the diagnosis module — the composed router.  The single ``router`` to the rest of the system?**
  _108 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Diagnosis API Router` be split into smaller, more focused modules?**
  _Cohesion score 0.10098522167487685 - nodes in this community are weakly interconnected._
- **Should `CSRF Test Suite` be split into smaller, more focused modules?**
  _Cohesion score 0.14532019704433496 - nodes in this community are weakly interconnected._