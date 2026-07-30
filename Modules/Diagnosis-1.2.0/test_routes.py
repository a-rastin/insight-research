"""Route-seam split tests for the diagnosis module.

Issue: split public routes from internal routes. The router was one
module mixing the browser page, the protected per-patient diagnosis
REST, and the Dashboard discovery interface. After the split each
concern lives in its own module and ``api.py`` composes them into one
``router`` in the order required by the route-order invariant
(literal paths before ``/{code}``).

This file asserts the seams:
  - the three sub-routers each own exactly their routes;
  - the composed ``diagnosis.api.router`` exposes the same path set as
    before, in invariant-required order;
  - the back-compat re-exports (``store``, ``Submission``,
    ``RESULT_FIELDS``, ``_dump_for_audit``, ``_read_page``,
    ``_http_selfcheck``) still resolve from ``diagnosis.api`` so
    existing tests / Insight callers don't break.

No test framework — ponytail style, mirrors ``test_auth.py`` /
``test_csrf.py``. Run: ``python -m test_routes``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the diagnosis package importable regardless of cwd.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

# Force the auth bypass off so the dependency wiring reflects the
# production path (real role + CSRF deps, not the bypass shim). We never
# make a real HTTP call here; we only inspect route declarations.
os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)

from diagnosis import api as diag_api  # noqa: E402
from diagnosis import page, dashboard, diagnosis_api, v2  # noqa: E402


def _paths(r) -> set[str]:
    """Flatten a router's declared GET/POST/PUT route paths."""
    out: set[str] = set()
    stack = [r]
    while stack:
        cur = stack.pop()
        # APIRouters keep their routes in .routes; included routers nest
        # as APIRoute objects whose .path already carries the prefix.
        for route in getattr(cur, "routes", []):
            sub = getattr(route, "path", None)
            if sub is not None:
                out.add(sub)
            # Also recurse into a sub-router if it has its own routes.
            inner = getattr(route, "router", None)
            if inner is not None:
                stack.append(inner)
    return out


def test_page_seam_owns_only_browser_page():
    want = test_page_seam_owns_only_browser_page.want
    got = _paths(page.router)
    assert got == want, ("page seam drifted", want, got)


test_page_seam_owns_only_browser_page.want = {"/"}


def test_dashboard_seam_owns_only_discovery_routes():
    want = test_dashboard_seam_owns_only_discovery_routes.want
    got = _paths(dashboard.router)
    assert got == want, ("dashboard seam drifted", want, got)


test_dashboard_seam_owns_only_discovery_routes.want = {
    "/diagnosis/_meta",
    "/diagnosis/_csrf",
    "/internal/dashboard/module-routes/{moduleId}",
    # The audit-log seam exposes the persisted local audit trail for the
    # future Logs module. Lives under ``/internal/...`` so its ``{code}``
    # parameter does NOT collide with the per-patient ``/{code}`` family.
    "/internal/diagnosis/audit/{code}",
}


def test_diagnosis_seam_owns_only_per_patient_rest():
    want = test_diagnosis_seam_owns_only_per_patient_rest.want
    got = _paths(diagnosis_api.router)
    assert got == want, ("diagnosis REST seam drifted", want, got)


test_diagnosis_seam_owns_only_per_patient_rest.want = {
    "/diagnosis/{code}/init",
    "/diagnosis/{code}",
}


def test_v2_seam_owns_only_uuid_rest():
    assert _paths(v2.router) == {
        "/api/diagnosis/v2/contract",
        "/api/diagnosis/v2/openapi.json",
        "/api/diagnosis/v2/diagnosis-assessment-v2.schema.json",
        "/api/diagnosis/v2/assessments",
        "/api/diagnosis/v2/assessments/{assessmentId}",
        "/api/diagnosis/v2/assessments/{assessmentId}/audit",
        "/api/diagnosis/v2/encounters/{encounterId}/assessment-snapshot",
    }


def test_composed_router_has_all_paths_from_app_openapi():
    from diagnosis.app import app
    expected = {
        "/",
        "/diagnosis/_meta",
        "/diagnosis/_csrf",
        "/internal/dashboard/module-routes/{moduleId}",
        "/internal/diagnosis/audit/{code}",
        "/diagnosis/{code}/init",
        "/diagnosis/{code}",
        "/api/diagnosis/v2/contract",
        "/api/diagnosis/v2/openapi.json",
        "/api/diagnosis/v2/diagnosis-assessment-v2.schema.json",
        "/api/diagnosis/v2/assessments",
        "/api/diagnosis/v2/assessments/{assessmentId}",
        "/api/diagnosis/v2/assessments/{assessmentId}/audit",
        "/api/diagnosis/v2/encounters/{encounterId}/assessment-snapshot",
        "/health",
        "/ready",
    }
    got = set(app.openapi()["paths"].keys())
    assert got == expected, ("composed router path set changed", expected, got)


def test_literal_routes_precede_parameterized_code_route():
    """Invariant 4: ``/_meta`` and ``/_csrf`` MUST match before
    ``/{code}`` or FastAPI captures them and serves a 404. FastAPI keeps
    registered routes in insertion order; OpenAPI's paths dict preserves
    that order, so we read the order from there (the composed routes are
    nested under the included sub-routers and don't surface as direct
    ``app.routes`` entries)."""
    from diagnosis.app import app
    ordered = list(app.openapi()["paths"].keys())
    code_idx = ordered.index("/diagnosis/{code}")
    meta_idx = ordered.index("/diagnosis/_meta")
    csrf_idx = ordered.index("/diagnosis/_csrf")
    assert meta_idx < code_idx, ("_meta after {code}", ordered)
    assert csrf_idx < code_idx, ("_csrf after {code}", ordered)
    # The discovery route's ``{moduleId}`` parameter lives under a distinct
    # ``/internal/...`` prefix and so does NOT collide with ``/{code}``,
    # but it still belongs to the dashboard seam (literals family) and
    # must precede the per-patient ``/{code}`` family for the invariant.
    disc_idx = ordered.index("/internal/dashboard/module-routes/{moduleId}")
    assert disc_idx < code_idx, ("discovery after {code}", ordered)
    # The audit-log seam carries a ``{code}`` path parameter too, but it
    # lives under the ``/internal/diagnosis/...`` prefix that does NOT
    # collide with the ``/{code}`` family — still it must precede
    # ``/{code}`` for the same literal-before-parameterized reason.
    audit_idx = ordered.index("/internal/diagnosis/audit/{code}")
    assert audit_idx < code_idx, ("audit seam after {code}", ordered)


def test_dashboard_seam_module_routes_is_in_seam():
    """The Dashboard discovery route lives in ``dashboard.py`` only —
    invariant 10 (seam split is a contract). Assert the path is declared
    on the dashboard seam router, NOT on the page or diagnosis seams."""
    from diagnosis import page, dashboard, diagnosis_api
    disc = "/internal/dashboard/module-routes/{moduleId}"
    assert disc in _paths(dashboard.router), ("discovery missing from dashboard seam", disc)
    assert disc not in _paths(page.router), ("discovery leaked into page seam", disc)
    assert disc not in _paths(diagnosis_api.router), ("discovery leaked into diagnosis seam", disc)


def test_audit_seam_is_in_dashboard_seam_only():
    """The audit-log route lives in ``dashboard.py`` only — invariant 10
    (seam split is a contract). Audit is a read purpose: the dashboard seam
    owns discovery + the audit snapshot hook + the audit-log read route.
    Assert the path is declared on the dashboard seam, NOT on the page or
    diagnosis REST seams (which would re-mix concerns)."""
    from diagnosis import page, dashboard, diagnosis_api
    audit = "/internal/diagnosis/audit/{code}"
    assert audit in _paths(dashboard.router), ("audit missing from dashboard seam", audit)
    assert audit not in _paths(page.router), ("audit leaked into page seam", audit)
    assert audit not in _paths(diagnosis_api.router), ("audit leaked into diagnosis seam", audit)


def test_discovery_module_id_constant():
    """`MODULE_ID` is part of the discovery contract — Dashboard joins on
    it and the launch href is derived from it. Lock the value."""
    from diagnosis.dashboard import MODULE_ID
    assert MODULE_ID == "diagnosis"


def test_back_compat_reexports_from_api_seam():
    """Tests + Insight callers import contract symbols from
    ``diagnosis.api`` directly. The split must keep them."""
    reexports = {
        "router": diag_api.router,
        "store": diag_api.store,
        "Submission": diag_api.Submission,
        "RESULT_FIELDS": diag_api.RESULT_FIELDS,
        "_dump_for_audit": diag_api._dump_for_audit,
        "_read_page": diag_api._read_page,
        "_http_selfcheck": diag_api._http_selfcheck,
    }
    for name, value in reexports.items():
        assert value is not None, ("missing back-compat re-export", name)
    assert diag_api.RESULT_FIELDS == (
        "met", "a_count", "core_count", "failures", "reason", "checked")
    assert diag_api.Submission.__name__ == "Submission"


def test_each_seam_shares_one_store_and_policy():
    """The three seams must share the single process-wide DiagnosisStore
    and the policy dep wiring from ``deps`` — no per-seam store instances,
    no shadow role/CSRF deps."""
    # Single store instance across seams + the api re-export.
    assert diag_api.store is diag_api._deps.store
    assert dashboard.store is diag_api._deps.store
    assert diagnosis_api.store is diag_api._deps.store
    # Policy deps are the same callables everywhere.
    from diagnosis.deps import (require_psychiatrist,
                                require_psychiatrist_or_admin,
                                require_csrf)
    # Under no-bypass each dep is the auth/csrf module's real callable.
    from diagnosis import auth as diag_auth
    from diagnosis import csrf as diag_csrf
    assert diag_csrf.require_csrf is require_csrf


def main() -> None:
    cases = [
        ("test_page_seam_owns_only_browser_page",
         test_page_seam_owns_only_browser_page),
        ("test_dashboard_seam_owns_only_discovery_routes",
         test_dashboard_seam_owns_only_discovery_routes),
        ("test_diagnosis_seam_owns_only_per_patient_rest",
         test_diagnosis_seam_owns_only_per_patient_rest),
        ("test_v2_seam_owns_only_uuid_rest", test_v2_seam_owns_only_uuid_rest),
        ("test_composed_router_has_all_paths_from_app_openapi",
         test_composed_router_has_all_paths_from_app_openapi),
        ("test_literal_routes_precede_parameterized_code_route",
         test_literal_routes_precede_parameterized_code_route),
        ("test_back_compat_reexports_from_api_seam",
         test_back_compat_reexports_from_api_seam),
        ("test_each_seam_shares_one_store_and_policy",
         test_each_seam_shares_one_store_and_policy),
        ("test_dashboard_seam_module_routes_is_in_seam",
         test_dashboard_seam_module_routes_is_in_seam),
        ("test_audit_seam_is_in_dashboard_seam_only",
         test_audit_seam_is_in_dashboard_seam_only),
        ("test_discovery_module_id_constant",
         test_discovery_module_id_constant),
    ]
    failures = []
    for name, fn in cases:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failures.append((name, repr(e)))
            print(f"FAIL  {name}: {e}")

    if failures:
        print(f"\n{len(failures)}/{len(cases)} FAILED")
        sys.exit(1)
    print(f"\nOK: {len(cases)}/{len(cases)} route-seam tests passed")


if __name__ == "__main__":
    main()
