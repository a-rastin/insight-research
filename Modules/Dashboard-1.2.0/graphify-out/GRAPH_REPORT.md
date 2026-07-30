# Graph Report - E:\dashboard\Dashboard  (2026-07-12)

## Corpus Check
- Corpus is ~8,401 words - fits in a single context window. You may not need a graph.

## Summary
- 170 nodes · 358 edges · 10 communities (9 shown, 1 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 14 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Auth & Session Management
- Test Suite
- Database Layer
- API Routes
- Auth REST Client
- Package Config
- Workspace Model
- Architecture Patterns
- Backend Init

## God Nodes (most connected - your core abstractions)
1. `DashboardRepository` - 18 edges
2. `DashboardServer` - 18 edges
3. `DashboardBackendTest` - 16 edges
4. `request_json()` - 15 edges
5. `renderWorkspace()` - 13 edges
6. `SQLiteAdapter` - 13 edges
7. `MockAuthenticationServer` - 11 edges
8. `fetch_auth_identity()` - 10 edges
9. `renderAccess()` - 9 edges
10. `escapeHtml()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `AuthSessionNormalizationTest` --uses--> `SQLiteAdapter`  [INFERRED]
  test_dashboard_backend.py → dashboard_backend/db.py
- `DashboardBackendTest` --uses--> `SQLiteAdapter`  [INFERRED]
  test_dashboard_backend.py → dashboard_backend/db.py
- `DashboardServer` --uses--> `SQLiteAdapter`  [INFERRED]
  test_dashboard_backend.py → dashboard_backend/db.py
- `MockAuthenticationServer` --uses--> `SQLiteAdapter`  [INFERRED]
  test_dashboard_backend.py → dashboard_backend/db.py
- `AuthSessionNormalizationTest` --uses--> `DashboardRepository`  [INFERRED]
  test_dashboard_backend.py → dashboard_backend/repository.py

## Import Cycles
- None detected.

## Communities (10 total, 1 thin omitted)

### Community 0 - "Auth & Session Management"
Cohesion: 0.11
Nodes (35): Authentication Boundary, Authentication REST Client, acceptDisclaimer(), activateDevRole(), api, app, buttonMeta(), clearUrl() (+27 more)

### Community 1 - "Test Suite"
Cohesion: 0.17
Nodes (9): auth_payload(), AuthSessionNormalizationTest, create_session(), DashboardBackendTest, DashboardServer, free_port(), future_iso(), MockAuthenticationServer (+1 more)

### Community 2 - "Database Layer"
Cohesion: 0.11
Nodes (9): Connection, DatabaseAdapter, SQLite adapter. Repository owns SQL, so Postgres can replace adapter later., SQLiteAdapter, DashboardRepository, now_iso(), Any, session_row() (+1 more)

### Community 3 - "API Routes"
Cohesion: 0.17
Nodes (26): accept_disclaimer(), create_dashboard_session(), dashboard_index(), delete_dashboard_session(), display_name_for(), healthz(), http_exception_handler(), json_error() (+18 more)

### Community 4 - "Auth REST Client"
Cohesion: 0.21
Nodes (19): auth_session_url(), AuthSessionError, _blocked_auth_session(), fetch_auth_identity(), _fetch_json(), forwarded_auth_headers(), _has_blocked_status(), _has_truthy_flag() (+11 more)

### Community 5 - "Package Config"
Cohesion: 0.25
Nodes (7): name, private, scripts, start, test, type, version

### Community 6 - "Workspace Model"
Cohesion: 0.53
Nodes (6): ADMIN Role, Disclaimer Acceptance, Module Placeholders, PSYCHIATRIST Role, Role-Scoped Buttons, INSIGHT Workspace

### Community 7 - "Architecture Patterns"
Cohesion: 0.67
Nodes (4): DatabaseAdapter Protocol, Postgres Adapter, Repository Pattern, SQLite Persistence

## Knowledge Gaps
- **16 isolated node(s):** `app`, `params`, `ROLE_META`, `STATUS_META`, `state` (+11 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DashboardRepository` connect `Database Layer` to `Test Suite`, `API Routes`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Why does `SQLiteAdapter` connect `Database Layer` to `Test Suite`, `API Routes`?**
  _High betweenness centrality (0.085) - this node is a cross-community bridge._
- **Why does `DashboardServer` connect `Test Suite` to `Database Layer`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `DashboardRepository` (e.g. with `DatabaseAdapter` and `AuthSessionNormalizationTest`) actually correct?**
  _`DashboardRepository` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `DashboardServer` (e.g. with `SQLiteAdapter` and `DashboardRepository`) actually correct?**
  _`DashboardServer` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `DashboardBackendTest` (e.g. with `SQLiteAdapter` and `DashboardRepository`) actually correct?**
  _`DashboardBackendTest` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `renderWorkspace()` (e.g. with `acceptDisclaimer()` and `signOut()`) actually correct?**
  _`renderWorkspace()` has 2 INFERRED edges - model-reasoned connections that need verification._